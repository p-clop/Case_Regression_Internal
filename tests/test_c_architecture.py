"""C architecture oracle coverage, real models, and evidence failure handling."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prototype.architecture import (ARCHES, build_projection, compare_projection, execute_query,
                                    input_hashes, model_files, review, run_case, subject_hash,
                                    validate_evidence, validate_oracle)
from prototype.internal import check_equivalences, run_internal
from prototype.pipeline import digest, find_model, find_tool, save_json

CLANG = find_tool('clang', os.environ.get('PROTOTYPE_CLANG'))
HERD = find_tool('herd7', os.environ.get('PROTOTYPE_HERD7'))
MODELS = {a: find_model(HERD, a, os.environ.get('PROTOTYPE_X86_MODEL' if a == 'x86' else 'PROTOTYPE_RISCV_MODEL'))
          for a in ARCHES}
CASES = [ROOT / item['directory'] for item in json.loads((ROOT / 'tests/internal_manifest.json').read_text())['cases']]


class ArchitectureContractTests(unittest.TestCase):
    def test_all_eight_have_source_bound_independent_coverage(self):
        oracles = [validate_oracle(case) for case in CASES]
        self.assertEqual(len(oracles), 8)
        self.assertEqual(sum(len(o['queries']) for o in oracles), 28)
        self.assertEqual(sum(o['family'] == 'single_location' for o in oracles), 5)
        for case, oracle in zip(CASES, oracles):
            self.assertEqual(oracle['c_program_correctness'], 'UNKNOWN')
            self.assertEqual(json.loads((case / 'expected.json').read_text())['validation'], 'structure')
            self.assertEqual(json.loads((case / 'architecture_reviews.json').read_text())['records'], [])

    def test_missing_query_collision_stale_source_and_changed_variant_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            case = Path(temp) / 'C04_struct_fields'
            shutil.copytree(ROOT / 'cases' / case.name, case)
            original = json.loads((case / 'architecture.json').read_text())
            variants = []
            changed = deepcopy(original)
            changed['queries'].pop()
            variants.append(changed)
            changed = deepcopy(original)
            changed['projections']['slice']['objects'][1]['symbol'] = 'data'
            variants.append(changed)
            changed = deepcopy(original)
            changed['source_sha256'] = 'stale'
            variants.append(changed)
            changed = deepcopy(original)
            changed['queries'][0]['variant'] = 'fenced'
            variants.append(changed)
            variants.append([])
            for changed in variants:
                (case / 'architecture.json').write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    validate_oracle(case)

    def test_review_is_bound_to_inputs_models_and_actual_review_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            case = Path(temp) / 'C01_global'
            shutil.copytree(ROOT / 'cases' / case.name, case)
            subject = subject_hash(input_hashes(case))
            models = {'test-model.cat': 'test-hash'}
            self.assertEqual(review(case, subject, 'unwritten_value.x86', 'Never', models)['status'], 'UNKNOWN')
            record = {'target': 'unwritten_value.x86', 'decision': 'CONFIRMED', 'review_id': 'test-only',
                      'reviewer': 'synthetic-fixture', 'reviewed_at': '2026-10-26T20:00:00+08:00',
                      'rationale': 'synthetic isolated unit test, not a project review',
                      'subject_sha256': subject, 'expected': 'Never', 'model_files': models}
            document = {'schema': 'c-architecture-reviews-1', 'case': case.name, 'records': [record]}
            (case / 'architecture_reviews.json').write_text(json.dumps(document))
            self.assertEqual(subject_hash(input_hashes(case)), subject)
            self.assertEqual(review(case, subject, record['target'], 'Never', models)['status'], 'CONFIRMED')
            self.assertEqual(review(case, 'different-inputs', record['target'], 'Never', models)['status'], 'UNKNOWN')
            self.assertEqual(review(case, subject, record['target'], 'Never', {'test-model.cat': 'changed'})['status'], 'UNKNOWN')
            self.assertEqual(review(case, subject, record['target'], 'Sometimes', models)['status'], 'UNKNOWN')
            document['records'].append(deepcopy(record))
            (case / 'architecture_reviews.json').write_text(json.dumps(document))
            self.assertEqual(review(case, subject, record['target'], 'Never', models)['status'], 'UNKNOWN')


@unittest.skipUnless(CLANG, 'Clang required')
class ArchitectureStructureTests(unittest.TestCase):
    def test_projection_preserves_field_identities_initializers_and_event_order(self):
        case = ROOT / 'cases/C04_struct_fields'
        oracle = validate_oracle(case)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            result = run_internal(case, output / case.name, clang=CLANG)
            self.assertEqual(result['status'], 'PASS')
            unit = json.loads((output / case.name / 'unit.json').read_text())
            declaration = oracle['projections']['slice']
            self.assertEqual(compare_projection(unit, declaration)['status'], 'PASS')
            for mutation in ('reverse', 'initial', 'merge'):
                changed = deepcopy(unit)
                if mutation == 'reverse':
                    changed['threads'][0]['events'].reverse()
                elif mutation == 'initial':
                    changed['objects'][0]['initial'] = 1
                else:
                    changed['threads'][0]['events'][0]['object'] = 'state.flag'
                self.assertEqual(compare_projection(changed, declaration)['status'], 'FAIL')

    def test_missing_herd_or_models_cannot_be_a_comparison_pass(self):
        case = ROOT / 'cases/C01_global'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_internal(case, root / 'internal' / case.name, clang=CLANG)
            result = run_case(case, root / 'internal', root / 'architecture', herd=None, models={})
            self.assertEqual(result['comparison_status'], 'UNKNOWN')
            self.assertEqual(len(result['queries']), 6)
            self.assertTrue(all(q['status'] == 'UNKNOWN' for q in result['queries']))
            self.assertEqual(result['conclusion_status'], 'UNKNOWN')


@unittest.skipUnless(CLANG and HERD and all(p and p.is_file() for p in MODELS.values()), 'Clang/herd/models required')
class RealArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.structural = cls.root / 'internal'
        structures = [run_internal(case, cls.structural / case.name, clang=CLANG) for case in CASES]
        check_equivalences(structures, cls.structural)
        cls.results = {c.name: run_case(c, cls.structural, cls.root / 'architecture' / c.name,
                                       herd=HERD, models=MODELS) for c in CASES}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_56_model_comparisons_match_and_reviews_remain_unknown(self):
        self.assertEqual(sum(len(r['queries']) for r in self.results.values()), 56)
        for case in CASES:
            result = self.results[case.name]
            self.assertEqual(result['comparison_status'], 'PASS', result)
            self.assertEqual(result['review_status'], 'UNKNOWN')
            self.assertEqual(result['conclusion_status'], 'UNKNOWN')
            self.assertTrue(all(q['actual'] == q['expected'] for q in result['queries']))
            validate_evidence(case, self.root / 'architecture' / case.name)

    def test_c08_noise_projection_has_same_target_outcome_as_slice(self):
        queries = {(q['query'], q['architecture']): q for q in self.results['C08_unrelated_code']['queries']}
        for arch in ARCHES:
            self.assertEqual(queries['stale_payload', arch]['actual'],
                             queries['full_noise_stale_payload', arch]['actual'])

    def test_wrong_expected_result_is_fail_even_without_formal_review(self):
        with tempfile.TemporaryDirectory() as temp:
            case = Path(temp) / 'C07_two_objects'
            shutil.copytree(ROOT / 'cases' / case.name, case)
            oracle = json.loads((case / 'architecture.json').read_text())
            oracle['queries'][0]['expected']['riscv'] = 'Never'
            save_json(case / 'architecture.json', oracle)
            result = run_case(case, self.structural, Path(temp) / 'result', herd=HERD, models=MODELS)
            self.assertEqual(result['comparison_status'], 'FAIL')
            self.assertEqual(result['review_status'], 'UNKNOWN')
            q = next(q for q in result['queries'] if q['query'] == 'stale_payload' and q['architecture'] == 'riscv')
            self.assertEqual(q['actual'], 'Sometimes')
            self.assertEqual(q['status'], 'FAIL')

    def test_removing_riscv_control_fences_restores_stale_payload(self):
        case = ROOT / 'cases/C07_two_objects'
        oracle = validate_oracle(case)
        actual = json.loads((self.structural / case.name / 'unit.json').read_text())
        q = next(q for q in oracle['queries'] if q['id'] == 'fenced_stale_payload')
        from prototype.litmus import generate
        with tempfile.TemporaryDirectory() as temp:
            unit = build_projection(actual, oracle['projections']['slice'], [], q['target'])
            text, _ = generate(unit, 'riscv', 'C07_removed_fences')
            path = Path(temp) / 'removed.litmus'
            path.write_text(text)
            result = execute_query(path, HERD, MODELS['riscv'], 'Never', 30)
            self.assertEqual(result['actual'], 'Sometimes')
            self.assertEqual(result['status'], 'FAIL')

    def test_missing_query_tampered_artifact_and_changed_model_cannot_be_reused(self):
        case = ROOT / 'cases/C01_global'
        original = self.root / 'architecture' / case.name
        with tempfile.TemporaryDirectory() as temp:
            copied = Path(temp) / 'result'
            shutil.copytree(original, copied)
            result = json.loads((copied / 'result.json').read_text())
            result['queries'].pop()
            save_json(copied / 'result.json', result)
            with self.assertRaisesRegex(ValueError, 'omits'):
                validate_evidence(case, copied)
            shutil.copyfile(original / 'result.json', copied / 'result.json')
            result = json.loads((copied / 'result.json').read_text())
            result['artifacts'] = {}
            save_json(copied / 'result.json', result)
            with self.assertRaisesRegex(ValueError, 'evidence'):
                validate_evidence(case, copied)
            shutil.copyfile(original / 'result.json', copied / 'result.json')
            litmus = next(copied.glob('*.litmus'))
            litmus.write_text(litmus.read_text() + '\n')
            with self.assertRaises(ValueError):
                validate_evidence(case, copied)
            shutil.copyfile(original / litmus.name, litmus)
            result = json.loads((copied / 'result.json').read_text())
            model = Path(temp) / 'fixture.cat'
            model.write_text('test model')
            result['queries'][0]['model_files'] = {str(model): digest(model)}
            save_json(copied / 'result.json', result)
            model.write_text('changed model')
            with self.assertRaisesRegex(ValueError, 'CAT'):
                validate_evidence(case, copied)

    def test_missing_architecture_evidence_preserves_structure_pass_and_marks_execution_unknown(self):
        spec = importlib.util.spec_from_file_location('architecture_report_test', ROOT / 'scripts/run_correctness.py')
        reporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reporter)
        entry = json.loads((ROOT / 'correctness_manifest.json').read_text())['cases'][0]
        result = reporter.collect_case(ROOT, entry, self.structural, self.root / 'missing')
        self.assertEqual(result['layers']['structure']['status'], 'PASS')
        self.assertEqual(result['layers']['architecture']['comparison_status'], 'UNKNOWN')
        self.assertEqual(result['execution_comparison'], 'UNKNOWN')

    def test_timeout_and_unrecognized_success_output_stay_unknown(self):
        path = self.root / 'timeout-test.litmus'
        path.write_text('not executed')
        with patch('prototype.architecture.subprocess.run', side_effect=subprocess.TimeoutExpired('herd7', 1)):
            self.assertEqual(execute_query(path, HERD, MODELS['x86'], 'Never', 1)['status'], 'UNKNOWN')
        with patch('prototype.architecture.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'no observation', '')):
            self.assertEqual(execute_query(path, HERD, MODELS['x86'], 'Never', 1)['status'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
