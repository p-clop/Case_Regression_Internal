"""Regression checks for missing evidence, independent checks and review freshness."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks/scripts"))
from oracle_contract import aggregate, attach_correctness, review_state, subject_hash, validate_contract
from run_suite import native_result

spec = importlib.util.spec_from_file_location("correctness_report", ROOT / "scripts/run_correctness.py")
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "benchmarks"
        shutil.copytree(ROOT / "benchmarks", self.root,
                        ignore=shutil.ignore_patterns("build", "__pycache__"))
        self.case = "B01_spsc_ring"
        self.path = self.root / self.case / "oracle.json"
        self.oracle = json.loads(self.path.read_text())

    def save(self):
        self.path.write_text(json.dumps(self.oracle))

    def test_fifo_formula_cannot_silently_change(self):
        self.oracle["fifo_contract"]["checksum_multiplier"] += 2
        self.save()
        with self.assertRaisesRegex(ValueError, "FIFO formula"):
            validate_contract(self.root, self.case)

    def test_missing_projection_obligation_is_rejected(self):
        self.oracle["obligations"] = self.oracle["obligations"][1:]
        self.save()
        with self.assertRaisesRegex(ValueError, "fixed manifest"):
            validate_contract(self.root, self.case)

    def test_missing_native_only_obligation_is_rejected(self):
        self.oracle["obligations"] = [o for o in self.oracle["obligations"] if o["id"] != "B01-FIFO"]
        self.save()
        with self.assertRaisesRegex(ValueError, "fixed manifest"):
            validate_contract(self.root, self.case)

    def test_missing_forbidden_behavior_is_rejected(self):
        self.oracle["obligations"][0]["forbidden"] = []
        self.save()
        with self.assertRaisesRegex(ValueError, "forbidden"):
            validate_contract(self.root, self.case)

    def test_invalid_native_or_document_shape_cannot_start_a_run(self):
        for key, value in (("native", {}), ("references", []), ("projections", [])):
            with self.subTest(key=key):
                changed = deepcopy(self.oracle)
                changed[key] = value
                self.path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    validate_contract(self.root, self.case)

    def test_missing_source_symbol_is_rejected(self):
        self.oracle["obligations"][0]["source_anchors"][0]["symbol"] = "nonexistent_function"
        self.save()
        with self.assertRaisesRegex(ValueError, "source anchor"):
            validate_contract(self.root, self.case)

    def test_missing_architecture_variant_is_rejected(self):
        del self.oracle["projections"]["publication.relaxed"]["riscv"]
        self.save()
        with self.assertRaisesRegex(ValueError, "model expectation"):
            validate_contract(self.root, self.case)

    def test_successful_execution_cannot_confirm_unreviewed_oracle(self):
        record = {"native": [], "native_status": "PASS", "projection_status": "PASS",
                  "projections": [{"obligation": "publication.ordered", "isa": "riscv",
                                   "expected": "Never", "actual": "Never", "status": "PASS"}]}
        attach_correctness(self.root, self.case, self.oracle, record, "subject")
        projection = record["projections"][0]
        self.assertEqual(projection["comparison_status"], "PASS")
        self.assertEqual(projection["oracle_review"], "UNKNOWN")
        self.assertEqual(projection["model_conclusion"]["status"], "UNKNOWN")
        self.assertTrue(all(o["full_verification"]["status"] == "UNKNOWN"
                            for o in record["correctness"]["obligations"]))

    def test_model_mismatch_stays_fail_while_review_is_unknown(self):
        record = {"native": [], "native_status": "PASS", "projection_status": "FAIL",
                  "projections": [{"obligation": "publication.ordered", "isa": "riscv",
                                   "expected": "Never", "actual": "Sometimes", "status": "FAIL"}]}
        attach_correctness(self.root, self.case, self.oracle, record, "subject")
        self.assertEqual(record["projections"][0]["comparison_status"], "FAIL")
        self.assertEqual(record["projections"][0]["oracle_review"], "UNKNOWN")


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = "B01_spsc_ring"
        (self.root / self.case).mkdir()
        self.target = "publication.ordered.riscv"
        # Synthetic records exist only inside this test's temporary directory.
        self.record = {"target": self.target, "decision": "CONFIRMED", "review_id": "test-only",
                       "reviewer": "unit-test-only", "reviewed_at": "2026-10-26T12:00:00+08:00",
                       "rationale": "synthetic review fixture", "subject_sha256": "subject",
                       "expected": "Never", "model_files": {"model.cat": "model-hash"}}

    def review(self, **kwargs):
        document = {"schema": "benchmark-reviews-1", "case": self.case, "records": [self.record]}
        document.update(kwargs)
        (self.root / self.case / "reviews.json").write_text(json.dumps(document))
        return review_state(self.root, self.case, "subject", self.target, "Never", {"model.cat": "model-hash"})

    def test_matching_record_is_accepted(self):
        self.assertEqual(self.review()["status"], "CONFIRMED")

    def test_changed_source_or_oracle_invalidates_review(self):
        self.record["subject_sha256"] = "old-subject"
        self.assertEqual(self.review()["reason"], "stale_review_inputs")

    def test_changed_model_include_invalidates_review(self):
        self.record["model_files"]["model.cat"] = "old-model"
        self.assertEqual(self.review()["reason"], "review_model_or_expectation_changed")

    def test_incomplete_review_identity_stays_unknown(self):
        del self.record["reviewer"]
        self.assertEqual(self.review()["status"], "UNKNOWN")

    def test_duplicate_reviews_stay_unknown(self):
        self.assertEqual(self.review(records=[self.record, deepcopy(self.record)])["reason"],
                         "conflicting_review_records")

    def test_review_from_another_case_stays_unknown(self):
        self.assertEqual(self.review(case="B02_spinlock")["status"], "UNKNOWN")

    def test_review_does_not_invalidate_its_own_subject(self):
        baseline = {"B01/oracle.json": "a", "B01/reviews.json": "empty"}
        changed_review = {**baseline, "B01/reviews.json": "confirmed"}
        changed_source = {**baseline, "common/platform.h": "different"}
        self.assertEqual(subject_hash(baseline), subject_hash(changed_review))
        self.assertNotEqual(subject_hash(baseline), subject_hash(changed_source))


class ObservationTests(unittest.TestCase):
    def test_unrecognized_status_cannot_be_aggregated_as_pass(self):
        self.assertEqual(aggregate(["PASS", "SKIPPED"]), "UNKNOWN")
        self.assertEqual(aggregate([]), "UNKNOWN")
        self.assertEqual(aggregate(["FAIL", "UNKNOWN"]), "FAIL")

    def observation(self, case, actual):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "stdout.txt"
            log.write_text(json.dumps(actual))
            return native_result({"stdout_log": str(log), "returncode": 0, "reason": None}, case,
                                 {"returncode": 0, "status": "PASS"}, ["--iterations", "2"])

    def test_false_pass_cannot_hide_wrong_queue_index(self):
        actual = dict(case="B01_spsc_ring", status="PASS", preflight=True, produced=2, consumed=2,
                      final_index=2, final_indexes=[2, 2, 1, 2])
        self.assertEqual(self.observation("B01_spsc_ring", actual)["status"], "FAIL")

    def test_false_pass_cannot_hide_wrong_checksum_or_held_lock(self):
        actual = dict(case="B02_spinlock", status="PASS", preflight=True, completed=[2, 2],
                      errors=[0, 0], final_count=4, checksum=0, locked=0)
        self.assertEqual(self.observation("B02_spinlock", actual)["status"], "FAIL")
        actual["checksum"] = ((4*11400714819323198485) % (2**64)) ^ 0x5a5aa5a5deadcafe
        actual["locked"] = 1
        self.assertEqual(self.observation("B02_spinlock", actual)["status"], "FAIL")
        actual["locked"] = 0
        self.assertEqual(self.observation("B02_spinlock", actual)["status"], "UNKNOWN")

    def test_missing_result_is_unknown(self):
        entry = dict(id="C01_global", suite="internal", requirement="test", explanation="expected.md")
        with tempfile.TemporaryDirectory() as temp:
            item = reporter.collect_case(Path(temp), entry, Path(temp))
        self.assertEqual(item["execution_comparison"], "UNKNOWN")
        self.assertEqual(item["layers"]["structure"]["status"], "UNKNOWN")

    def test_missing_explanation_is_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "source.c").write_text("source")
            (root / "oracle.json").write_text("{}")
            (root / "C01_global").mkdir()
            (root / "C01_global/result.json").write_text("{}")
            entry = dict(id="C01_global", suite="internal", source="source.c", oracle="oracle.json",
                         explanation="missing.md", requirement="test")
            item = reporter.collect_case(root, entry, root)
            self.assertEqual(item["evidence"]["reason"], "catalog_input_missing:missing.md")
            self.assertEqual(item["execution_comparison"], "UNKNOWN")

    def test_stale_source_is_not_reused_as_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "source.c").write_text("changed source")
            (root / "C01_global").mkdir()
            (root / "C01_global/result.json").write_text(json.dumps({
                "case": "C01_global", "status": "PASS", "provenance": {"source_sha256": "old"}}))
            (root / "oracle.json").write_text("{}")
            (root / "expected.md").write_text("test explanation")
            entry = dict(id="C01_global", suite="internal", source="source.c", oracle="oracle.json",
                         explanation="expected.md", requirement="test")
            item = reporter.collect_case(root, entry, root)
            self.assertEqual(item["evidence"]["reason"], "stale_source")
            self.assertEqual(item["execution_comparison"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
