"""Real Clang extraction and independent oracle sensitivity for C01--C08.

Run with the tool environment loaded:
    python3 -m unittest discover -s tests -p test_internal_regression.py -v
No model conclusion is inferred from these structural checks.
"""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prototype.frontend import FrontendError, extract
from prototype.graph import build_unit
from prototype.pipeline import find_tool
from prototype.regression import canonical_unit, compare_case


CLANG = find_tool('clang', os.environ.get('PROTOTYPE_CLANG'))
CASE_NAMES = (
    'C01_global', 'C02_thread_argument', 'C03_heap_escape',
    'C04_struct_fields', 'C05_pointer_alias', 'C06_helper_function',
    'C07_two_objects', 'C08_unrelated_code',
)
CHECKS = {'shared_objects', 'events', 'slice', 'verification_unit', 'bindings'}


def source_text(name):
    return (ROOT / 'cases' / name / 'case.c').read_text(encoding='utf-8')


@unittest.skipUnless(CLANG, 'Clang unavailable; set PROTOTYPE_CLANG')
class InternalRegressionTests(unittest.TestCase):
    _cache = {}

    def case(self, name):
        if name not in self._cache:
            directory = ROOT / 'cases' / name
            expected = json.loads((directory / 'expected.json').read_text(encoding='utf-8'))
            program = extract(directory / 'case.c', clang=CLANG)
            unit = build_unit(program, expected['seed_objects'], expected['outcome'])
            self._cache[name] = (program, unit, expected)
        return deepcopy(self._cache[name])

    def assert_oracle_failure(self, program, unit, expected, category):
        result = compare_case(program, unit, expected)
        self.assertEqual(result['status'], 'FAIL', result)
        self.assertEqual(result['checks'][category]['status'], 'FAIL', result)
        self.assertTrue(result['checks'][category]['errors'], result)
        self.assertTrue(result['errors'], result)
        for error in result['errors']:
            self.assertTrue(error['path'], error)
            self.assertIn('expected', error)
            self.assertIn('actual', error)

    def extract_text(self, text):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'case.c'
            source.write_text(text, encoding='utf-8')
            return extract(source, clang=CLANG)

    def run_cli(self, output, *arguments):
        return subprocess.run(
            [sys.executable, '-m', 'prototype.internal', '--clang', CLANG,
             '--out', str(output), *map(str, arguments)],
            cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
        )

    def test_all_eight_real_sources_match_independent_manual_oracles(self):
        for name in CASE_NAMES:
            with self.subTest(case=name):
                program, unit, expected = self.case(name)
                result = compare_case(program, unit, expected)
                self.assertEqual(result['status'], 'PASS', result)
                self.assertEqual(set(result['checks']), CHECKS)
                self.assertEqual(result['errors'], [])
                self.assertTrue(all(check['status'] == 'PASS'
                                    for check in result['checks'].values()), result)

    def test_dropped_extra_and_reordered_events_are_detected(self):
        for mutation in ('drop', 'extra', 'reorder'):
            with self.subTest(mutation=mutation):
                program, unit, expected = self.case('C07_two_objects')
                events = program['threads'][0]['events']
                if mutation == 'drop':
                    events.pop(0)
                elif mutation == 'extra':
                    extra = deepcopy(events[-1])
                    extra['id'] = 'T0:E999'
                    events.append(extra)
                else:
                    events.reverse()
                self.assert_oracle_failure(program, unit, expected, 'events')

    def test_wrong_object_initial_value_and_origin_are_detected(self):
        for field, replacement in (('initial', 1), ('origin', 'global')):
            with self.subTest(field=field):
                program, unit, expected = self.case('C02_thread_argument')
                program['objects'][0][field] = replacement
                self.assert_oracle_failure(program, unit, expected, 'shared_objects')

    def test_malformed_actual_objects_and_threads_return_structured_failure(self):
        for field, category in (('objects', 'shared_objects'), ('threads', 'events')):
            with self.subTest(field=field):
                program, unit, expected = self.case('C01_global')
                program[field] = None
                self.assert_oracle_failure(program, unit, expected, category)

    def test_heap_allocation_identity_is_part_of_object_contract(self):
        program, unit, expected = self.case('C03_heap_escape')
        program['objects'][0]['allocation_site']['id'] = 'main:malloc:other'
        self.assert_oracle_failure(program, unit, expected, 'shared_objects')

    def test_struct_field_provenance_is_part_of_object_contract(self):
        for field, replacement in (('base_object', 'other'), ('field_path', ['other'])):
            with self.subTest(field=field):
                program, unit, expected = self.case('C04_struct_fields')
                program['objects'][0][field] = replacement
                self.assert_oracle_failure(program, unit, expected, 'shared_objects')

    def test_lost_or_incorrect_pointer_bindings_are_detected(self):
        for mutation in ('drop', 'wrong_object'):
            with self.subTest(mutation=mutation):
                program, unit, expected = self.case('C02_thread_argument')
                if mutation == 'drop':
                    program['bindings'].pop()
                else:
                    program['bindings'][0]['object'] = 'different.local'
                self.assert_oracle_failure(program, unit, expected, 'bindings')

    def test_extra_private_noise_is_not_accepted_as_shared(self):
        program, unit, expected = self.case('C08_unrelated_code')
        unit['shared_objects'].append('noise')
        self.assert_oracle_failure(program, unit, expected, 'shared_objects')

    def test_retained_private_noise_is_detected_in_slice(self):
        program, unit, expected = self.case('C08_unrelated_code')
        noise = next(e for e in program['threads'][0]['events'] if e['object'] == 'noise')
        unit['slice']['retained_events'].append(noise['id'])
        unit['slice']['removed_events'].remove(noise['id'])
        self.assert_oracle_failure(program, unit, expected, 'slice')

    def test_missing_shared_event_is_detected_in_slice(self):
        program, unit, expected = self.case('C07_two_objects')
        event_id = unit['slice']['retained_events'].pop(0)
        unit['slice']['removed_events'].append(event_id)
        self.assert_oracle_failure(program, unit, expected, 'slice')

    def test_missing_shared_object_is_detected_in_unit(self):
        program, unit, expected = self.case('C07_two_objects')
        unit['objects'] = [obj for obj in unit['objects'] if obj['id'] != 'data']
        self.assert_oracle_failure(program, unit, expected, 'verification_unit')

    def test_missing_unit_event_and_program_order_edge_are_detected(self):
        for mutation in ('event', 'po'):
            with self.subTest(mutation=mutation):
                program, unit, expected = self.case('C07_two_objects')
                if mutation == 'event':
                    unit['threads'][0]['events'].pop()
                else:
                    removed = next(edge for edge in unit['edges'] if edge['kind'] == 'po')
                    unit['edges'].remove(removed)
                self.assert_oracle_failure(program, unit, expected, 'verification_unit')

    def test_unit_keeps_heap_pointer_bindings_and_allocation_assumption(self):
        for relationship in ('bindings', 'assumptions'):
            with self.subTest(relationship=relationship):
                program, unit, expected = self.case('C03_heap_escape')
                self.assertTrue(unit[relationship])
                unit[relationship].pop()
                self.assert_oracle_failure(program, unit, expected, 'verification_unit')

    def test_c08_retained_unit_equals_c07_despite_noise_event_ids(self):
        _, simple, _ = self.case('C07_two_objects')
        program, noisy, _ = self.case('C08_unrelated_code')
        self.assertTrue(any(e['object'] == 'noise' for t in program['threads'] for e in t['events']))
        self.assertEqual(noisy['slice']['removed_events'], ['T0:E0'])
        self.assertEqual(noisy['slice']['removed_objects'], ['noise'])
        self.assertEqual(canonical_unit(simple), canonical_unit(noisy))
        # An independent projection also verifies object and per-thread order;
        # this does not merely compare canonical_unit to itself.
        def signature(unit):
            return (
                sorted((obj['id'], obj['type'], obj['initial'], obj['origin'])
                       for obj in unit['objects']),
                [[(event['kind'], event['object'], event['ordering'], event.get('value'))
                  for event in thread['events']] for thread in unit['threads']],
            )
        self.assertEqual(signature(simple), signature(noisy))
        noisy['threads'][0]['events'].reverse()
        self.assertNotEqual(canonical_unit(simple), canonical_unit(noisy))

    def test_stack_thread_arguments_and_local_aliases_share_one_object(self):
        program, unit, _ = self.case('C02_thread_argument')
        self.assertEqual([(obj['id'], obj['origin'], obj['initial']) for obj in program['objects']],
                         [('main.local', 'thread_argument', 0)])
        self.assertEqual(unit['shared_objects'], ['main.local'])
        self.assertEqual({event['object'] for thread in program['threads'] for event in thread['events']},
                         {'main.local'})
        bindings = {(binding['kind'], binding['thread'], binding['name'], binding['object'])
                    for binding in program['bindings']}
        self.assertEqual(bindings, {
            ('thread_argument', 'T0', 'arg', 'main.local'),
            ('pointer_alias', 'T0', 'p', 'main.local'),
            ('thread_argument', 'T1', 'arg', 'main.local'),
            ('pointer_alias', 'T1', 'p', 'main.local'),
        })

    def test_heap_allocation_identity_and_zero_initialization_survive_escape(self):
        program, unit, _ = self.case('C03_heap_escape')
        self.assertEqual(len(program['objects']), 1)
        obj = program['objects'][0]
        self.assertEqual((obj['id'], obj['origin'], obj['initial']), ('heap_value', 'heap_escape', 0))
        self.assertEqual(obj['allocation_site']['id'], 'main:malloc:0')
        self.assertEqual(obj['allocation_site']['function'], 'main')
        self.assertGreater(obj['allocation_site']['source_location']['line'], 0)
        self.assertEqual(unit['shared_objects'], ['heap_value'])
        self.assertEqual({event['object'] for thread in program['threads'] for event in thread['events']},
                         {'heap_value'})

    def test_fields_are_distinct_and_unused_padding_does_not_become_an_object(self):
        program, _, _ = self.case('C04_struct_fields')
        self.assertEqual({obj['id'] for obj in program['objects']}, {'state.data', 'state.flag'})
        self.assertEqual({tuple(obj['field_path']) for obj in program['objects']}, {('data',), ('flag',)})
        aliased, unit, _ = self.case('C05_pointer_alias')
        self.assertEqual([obj['id'] for obj in aliased['objects']], ['state.flag'])
        self.assertEqual(unit['shared_objects'], ['state.flag'])
        self.assertTrue(any(binding['kind'] == 'pointer_alias' and binding['name'] == 'p'
                            and binding['object'] == 'state.flag' for binding in aliased['bindings']))

    def test_helper_memory_events_keep_the_correct_thread_and_call_context(self):
        program, _, _ = self.case('C06_helper_function')
        self.assertEqual([(thread['entry'], thread['events'][0]['function']) for thread in program['threads']],
                         [('writer', 'helper_write'), ('reader', 'helper_read')])
        self.assertEqual({(call['thread'], call['caller'], call['callee']) for call in program['calls']}, {
            ('T0', 'writer', 'helper_write'), ('T1', 'reader', 'helper_read'),
        })

    def test_pointer_arithmetic_and_dynamic_alias_choice_are_rejected(self):
        source = source_text('C02_thread_argument')
        variants = {
            'pointer_arithmetic': source.replace('int *p = arg;', 'int *p = arg; p = p + 1;', 1),
            'dynamic_alias': source.replace('int *p = arg;', 'int *p = arg; int other = 0; p = *p ? p : &other;', 1),
        }
        for name, text in variants.items():
            with self.subTest(feature=name), self.assertRaises(FrontendError):
                self.extract_text(text)

    def test_wrong_size_or_uninitialized_heap_allocations_are_rejected(self):
        source = source_text('C03_heap_escape')
        variants = {
            'too_small': source.replace('malloc(sizeof *heap_value)', 'malloc(sizeof(char))'),
            'too_large': source.replace('malloc(sizeof *heap_value)', 'malloc(sizeof *heap_value * 2)'),
            'uninitialized': source.replace('    *heap_value = 0;\n', ''),
            'missing_null_guard': source.replace('    if (!heap_value) return 1;\n', ''),
        }
        for name, text in variants.items():
            with self.subTest(feature=name), self.assertRaises(FrontendError):
                self.extract_text(text)

    def test_heap_free_before_all_joins_is_rejected(self):
        source = source_text('C03_heap_escape').replace('    free(heap_value);\n', '')
        for before in ('pthread_join(first, 0);', 'pthread_join(second, 0);'):
            text = source.replace(before, 'free(heap_value);\n    ' + before)
            with self.subTest(before=before), self.assertRaises(FrontendError):
                self.extract_text(text)

    def test_cli_exports_eight_structural_passes_without_model_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'results'
            process = self.run_cli(output)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            summary = json.loads((output / 'summary.json').read_text())
            self.assertEqual(summary['scope'], 'structure_only')
            self.assertEqual(summary['status'], 'PASS')
            self.assertEqual(summary['counts'], {'PASS': 8, 'FAIL': 0, 'UNKNOWN': 0})
            self.assertEqual({case['case'] for case in summary['cases']}, set(CASE_NAMES))
            for case in summary['cases']:
                self.assertEqual(case['status'], 'PASS', case)
                self.assertEqual(case['scope'], 'structure_only')
                self.assertTrue(all(check['status'] == 'PASS' for check in case['checks'].values()), case)
                self.assertEqual({architecture: result['status']
                                  for architecture, result in case['verification'].items()},
                                 {'x86': 'UNKNOWN', 'riscv': 'UNKNOWN'})
                self.assertTrue((output / case['case'] / 'source.ll').is_file())
                manifest = json.loads((output / case['case'] / 'manifest.json').read_text())
                for artifact in ('eventir.json', 'unit.json', 'slice.json'):
                    actual_hash = hashlib.sha256((output / case['case'] / artifact).read_bytes()).hexdigest()
                    self.assertEqual(manifest['sha256'][artifact], actual_hash)
            noisy = next(case for case in summary['cases'] if case['case'] == 'C08_unrelated_code')
            self.assertEqual(noisy['checks']['equivalence']['status'], 'PASS')
            self.assertTrue((output / 'summary.csv').is_file())
            self.assertTrue((output / 'summary.md').is_file())

    def test_imported_artifacts_reject_stale_sources_and_changed_content(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            case = root / 'inputs' / 'C01_global'
            shutil.copytree(ROOT / 'cases' / case.name, case)
            exported = root / 'exported'
            process = self.run_cli(exported, case)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            imported = root / 'imported'
            process = self.run_cli(imported, case, '--artifacts', exported)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            result = json.loads((imported / case.name / 'result.json').read_text())
            self.assertEqual(result['status'], 'PASS')
            self.assertEqual(result['provenance']['mode'], 'import')
            self.assertTrue(all(value['status'] == 'UNKNOWN' for value in result['verification'].values()))

            source = case / 'case.c'
            original_source = source.read_text()
            source.write_text(original_source + '\n/* source changed after extraction */\n')
            stale_output = root / 'stale'
            process = self.run_cli(stale_output, case, '--artifacts', exported)
            self.assertEqual(process.returncode, 2, process.stdout + process.stderr)
            result = json.loads((stale_output / case.name / 'result.json').read_text())
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertIn('source hash', result['reason'])

            source.write_text(original_source)
            artifact = exported / case.name / 'unit.json'
            unit = json.loads(artifact.read_text())
            unit['objects'][0]['initial'] = 99
            artifact.write_text(json.dumps(unit))
            changed_output = root / 'changed'
            process = self.run_cli(changed_output, case, '--artifacts', exported)
            self.assertEqual(process.returncode, 2, process.stdout + process.stderr)
            result = json.loads((changed_output / case.name / 'result.json').read_text())
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertIn('artifact hash mismatch', result['reason'])


if __name__ == '__main__':
    unittest.main()
