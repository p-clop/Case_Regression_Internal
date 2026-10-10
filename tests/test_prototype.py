"""Contract, rejection, and real-model sensitivity tests for the prototype.

Run: python3 -m unittest discover -s tests -v
Set PROTOTYPE_CLANG and PROTOTYPE_HERD7 to select explicit tool installations.
Missing external tools skip their integration tests; no mocked PASS is used.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prototype.frontend import FrontendError, extract
from prototype.graph import GraphError, build_unit
from prototype.litmus import LoweringError, generate
from prototype.pipeline import find_model, find_tool, run_case, verify


CLANG = find_tool('clang', os.environ.get('PROTOTYPE_CLANG'))
HERD = find_tool('herd7', os.environ.get('PROTOTYPE_HERD7'))
MODELS = {arch: find_model(HERD, arch) for arch in ('x86', 'riscv')}
HAVE_MODELS = bool(HERD and all(path and path.is_file() for path in MODELS.values()))
CASE_NAMES = ('P01_pthread_sb', 'P02_atomic_fence', 'P03_release_acquire_relay')


def oracle(name):
    return json.loads((ROOT / 'cases' / name / 'expected.json').read_text())


def fixture(name):
    """Build input events from the independently authored contract, not extraction."""
    expected = oracle(name)
    threads = []
    for index, spec in enumerate(expected['threads']):
        events = [dict(deepcopy(event), id=f'T{index}:E{n}',
                       source_location={'line': 1, 'column': 1})
                  for n, event in enumerate(spec['events'])]
        threads.append({'id': f'T{index}', 'index': index,
                        'entry': spec['entry'], 'events': events})
    program = {'source': {'path': 'independent-manual-oracle'},
               'threads': threads, 'objects': deepcopy(expected['objects'])}
    return program, expected


class GraphAndLoweringTests(unittest.TestCase):
    def test_private_noise_removed_but_both_shared_objects_retained(self):
        program, expected = fixture(CASE_NAMES[0])
        unit = build_unit(program, expected['seed_objects'], expected['outcome'])
        self.assertEqual(unit['shared_objects'], ['x', 'y'])
        self.assertEqual({o['id'] for o in unit['objects']}, {'x', 'y'})
        self.assertEqual(unit['slice']['removed_events'], ['T0:E2'])
        self.assertEqual(unit['slice']['removed_objects'], ['private_noise'])
        self.assertEqual(len(unit['slice']['retained_events']), 4)

    def test_relay_keeps_value_dependency_and_does_not_assert_reads_from(self):
        program, expected = fixture(CASE_NAMES[2])
        unit = build_unit(program, expected['seed_objects'], expected['outcome'])
        self.assertIn({'kind': 'data', 'from': 'T1:E0', 'to': 'T1:E1'}, unit['edges'])
        self.assertEqual(len(unit['slice']['retained_events']), 6)
        self.assertNotIn('reads_from', {e['kind'] for e in unit['edges']})
        self.assertEqual(unit['threads'][1]['events'][1]['value'], {'event': 'T1:E0'})

    def test_unresolved_and_private_seeds_are_rejected(self):
        program, expected = fixture(CASE_NAMES[0])
        for seeds in ([], ['missing'], ['private_noise']):
            with self.subTest(seeds=seeds), self.assertRaises(GraphError):
                build_unit(program, seeds, expected['outcome'])

    def test_unresolved_outcomes_are_rejected(self):
        program, expected = fixture(CASE_NAMES[0])
        for mutation in ({'thread': 99}, {'object': 'missing'},
                         {'occurrence': 99}, {'value': '0'}):
            outcome = deepcopy(expected['outcome'])
            outcome[0].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(GraphError):
                build_unit(program, expected['seed_objects'], outcome)

    def test_cross_thread_value_dependency_is_rejected(self):
        program, expected = fixture(CASE_NAMES[2])
        program['threads'][1]['events'][1]['value'] = {'event': 'T2:E0'}
        with self.assertRaises(GraphError):
            build_unit(program, expected['seed_objects'], expected['outcome'])

    def test_unsupported_lock_or_memory_order_cannot_produce_litmus(self):
        program, expected = fixture(CASE_NAMES[1])
        unit = build_unit(program, expected['seed_objects'], expected['outcome'])
        for arch in ('x86', 'riscv'):
            for mutation in ({'kind': 'Lock'}, {'ordering': 'invented_order'}):
                invalid = deepcopy(unit)
                invalid['threads'][0]['events'][0].update(mutation)
                with self.subTest(architecture=arch, mutation=mutation), self.assertRaises(LoweringError):
                    generate(invalid, arch, 'must_reject')

    def test_removed_outcome_load_is_rejected(self):
        program, expected = fixture(CASE_NAMES[0])
        unit = build_unit(program, expected['seed_objects'], expected['outcome'])
        unit['outcome'][0]['event'] = 'T0:E999'
        with self.assertRaises(LoweringError):
            generate(unit, 'riscv', 'missing_outcome')


class VerificationFailureTests(unittest.TestCase):
    def test_successful_process_without_observation_remains_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            executable = root / 'fake-herd'
            executable.write_text('#!/bin/sh\necho "parse error: unsupported instruction"\nexit 0\n')
            executable.chmod(0o755)
            model, litmus = root / 'model.cat', root / 'input.litmus'
            model.write_text('fake model')
            litmus.write_text('fake input')
            result = verify(litmus, str(executable), model, 'Never', 5)
            self.assertEqual(result['returncode'], 0)
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertIsNone(result['observation'])
            self.assertIn('parse error', Path(result['log']).read_text())

    def test_missing_herd_is_unknown(self):
        result = verify(Path('unused.litmus'), None, None, 'Never', 5)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertIsNone(result['observation'])


@unittest.skipUnless(CLANG, 'Clang unavailable; set PROTOTYPE_CLANG')
class FrontendTests(unittest.TestCase):
    def extract_text(self, text):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'case.c'
            source.write_text(text, encoding='utf-8')
            return extract(source, clang=CLANG)

    def text(self, name=CASE_NAMES[0]):
        return (ROOT / 'cases' / name / 'case.c').read_text()

    def test_source_oracle_structure_for_all_three_cases(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in CASE_NAMES:
                with self.subTest(case=name):
                    result = run_case(ROOT / 'cases' / name, Path(folder) / name,
                                      clang=CLANG, herd=None, models={}, run_herd=False)
                    self.assertEqual(result['structure']['status'], 'PASS', result)
                    self.assertEqual(result['status'], 'UNKNOWN')
                    self.assertTrue((Path(folder) / name / 'source.ll').is_file())

    def test_changed_initializer_fails_independent_oracle(self):
        with tempfile.TemporaryDirectory() as folder:
            case = Path(folder) / CASE_NAMES[1]
            case.mkdir()
            case.joinpath('case.c').write_text(self.text(CASE_NAMES[1]).replace('_Atomic int x = 0;', '_Atomic int x = 1;'))
            case.joinpath('expected.json').write_text(json.dumps(oracle(CASE_NAMES[1])))
            result = run_case(case, Path(folder) / 'output', clang=CLANG, herd=None,
                              models={}, run_herd=False)
            self.assertEqual(result['structure']['status'], 'FAIL', result)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(result['verification'], {})

    def test_branches_unknown_calls_and_pointer_aliases_rejected(self):
        base = self.text()
        variants = {
            'branch': base.replace('x = 1;', 'if (y) { x = 1; }'),
            'external_call': base.replace('int x = 0;', 'extern void mystery(void);\nint x = 0;').replace('x = 1;', 'mystery(); x = 1;'),
            'pointer_alias': base.replace('x = 1;', 'int *p = y ? &x : &y; *p = 1;'),
        }
        for name, text in variants.items():
            with self.subTest(feature=name), self.assertRaises(FrontendError):
                self.extract_text(text)

    def test_main_startup_shared_write_rejected(self):
        text = self.text().replace('pthread_t first, second;', 'pthread_t first, second;\n    x = 1;')
        with self.assertRaises(FrontendError):
            self.extract_text(text)

    def test_atomic_macro_locations_survive_utf8_prefix(self):
        text = self.text(CASE_NAMES[1])
        baseline = self.extract_text(text)
        shifted = self.extract_text('/* 中文前缀：检查字节偏移 */\n' + text)
        for old_thread, new_thread in zip(baseline['threads'], shifted['threads']):
            for old, new in zip(old_thread['events'], new_thread['events']):
                self.assertEqual(new['source_location']['line'], old['source_location']['line'] + 1)
                self.assertEqual(new['source_location']['column'], old['source_location']['column'])
                line = text.splitlines()[old['source_location']['line'] - 1]
                self.assertIn('atomic_', line)

    def test_duplicate_worker_entries_have_distinct_thread_contexts(self):
        text = self.text().replace('pthread_create(&second, 0, reader, 0);', 'pthread_create(&second, 0, writer, 0);')
        program = self.extract_text(text)
        self.assertEqual([t['entry'] for t in program['threads']], ['writer', 'writer'])
        self.assertEqual([t['id'] for t in program['threads']], ['T0', 'T1'])
        ids = [e['id'] for t in program['threads'] for e in t['events']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([len(t['events']) for t in program['threads']], [3, 3])

    def test_atomic_macro_cannot_disguise_exchange_as_store(self):
        text = self.text(CASE_NAMES[1]).replace('#include <stdatomic.h>',
            '#include <stdatomic.h>\n#undef atomic_store_explicit\n'
            '#define atomic_store_explicit(p, v, mo) __c11_atomic_exchange(p, v, mo)')
        with self.assertRaises(FrontendError):
            self.extract_text(text)

    def test_unsequenced_helper_side_effects_rejected(self):
        text = self.text().replace('void *writer(void *arg)',
            'static int a(void) { x = 1; return 1; }\n'
            'static int b(void) { y = 1; return 1; }\n'
            'void *writer(void *arg)').replace('    x = 1;', '    int unused = a() + b(); (void)unused;', 1)
        with self.assertRaises(FrontendError):
            self.extract_text(text)

    def test_narrowing_out_of_range_constant_rejected(self):
        with self.assertRaises(FrontendError):
            self.extract_text(self.text().replace('x = 1;', 'x = (int)4294967295u;'))


@unittest.skipUnless(CLANG and HAVE_MODELS, 'Clang/herd7/models unavailable; set PROTOTYPE_CLANG and PROTOTYPE_HERD7')
class RealModelTests(unittest.TestCase):
    def test_complete_source_to_model_pipeline_matches_all_manual_oracles(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in CASE_NAMES:
                with self.subTest(case=name):
                    result = run_case(ROOT / 'cases' / name, Path(folder) / name,
                                      clang=CLANG, herd=HERD, models=MODELS)
                    self.assertEqual(result['status'], 'PASS', result)
                    for architecture, expected in oracle(name)['expected_observations'].items():
                        self.assertEqual(result['verification'][architecture]['observation'], expected)

    def assert_source_mutation_outcomes(self, name, mutate, architectures):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'case.c'
            source.write_text(mutate((ROOT / 'cases' / name / 'case.c').read_text()))
            program = extract(source, clang=CLANG)
            expected = oracle(name)
            unit = build_unit(program, expected['seed_objects'], expected['outcome'])
            for architecture in architectures:
                text, _ = generate(unit, architecture, 'synchronization_removed')
                litmus = Path(folder) / f'{architecture}.litmus'
                litmus.write_text(text)
                result = verify(litmus, HERD, MODELS[architecture], 'Sometimes', 30)
                self.assertEqual(result['status'], 'PASS', result)
                self.assertEqual(result['observation'], 'Sometimes')
            return unit

    def test_removing_both_fences_allows_store_buffering(self):
        unit = self.assert_source_mutation_outcomes(CASE_NAMES[1],
            lambda text: text.replace('atomic_thread_fence(memory_order_seq_cst);', ''),
            ('x86', 'riscv'))
        self.assertFalse(any(e['kind'] == 'Fence' for t in unit['threads'] for e in t['events']))

    def test_acq_rel_fences_do_not_invent_seq_cst_store_load_order(self):
        self.assert_source_mutation_outcomes(CASE_NAMES[1],
            lambda text: text.replace('memory_order_seq_cst', 'memory_order_acq_rel'),
            ('x86', 'riscv'))

    def test_removing_release_acquire_allows_stale_relay_on_riscv(self):
        unit = self.assert_source_mutation_outcomes(CASE_NAMES[2],
            lambda text: text.replace('memory_order_release', 'memory_order_relaxed')
                             .replace('memory_order_acquire', 'memory_order_relaxed'),
            ('riscv',))
        self.assertIn({'kind': 'data', 'from': 'T1:E0', 'to': 'T1:E1'}, unit['edges'])


if __name__ == '__main__':
    unittest.main()
