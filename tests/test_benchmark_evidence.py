"""Collect portable evidence and reject missing, stale or contradictory records."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks/scripts"))
from benchmark_evidence import validate_benchmark_evidence
from oracle_contract import input_snapshot

spec = importlib.util.spec_from_file_location("evidence_reporter", ROOT / "scripts/run_correctness.py")
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


@unittest.skipUnless(shutil.which("gcc"), "requires GCC for native evidence")
class BenchmarkEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="benchmark-evidence-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.model = cls.base / "test.cat"
        cls.include = cls.base / "base.cat"
        cls.model.write_text('include "base.cat"\n')
        cls.include.write_text("(* synthetic model fixture *)\n")
        # Synthetic observations exercise evidence handling; real herd runs are separate.
        herd = cls.base / "fake-herd"
        herd.write_text("#!/usr/bin/env python3\nimport sys\n"
                        "if '-version' in sys.argv: print('test-fixture')\n"
                        "else:\n"
                        " result = 'Sometimes' if '.relaxed.riscv.litmus' in sys.argv[-1] else 'Never'\n"
                        " print('Observation Fixture ' + result + ' 1 1')\n")
        herd.chmod(0o755)
        cls.original = cls.base / "original"
        run = subprocess.run([sys.executable, str(ROOT / "benchmarks/scripts/run_suite.py"),
                              "--compiler", shutil.which("gcc"), "--herd7", str(herd),
                              "--x86-model", str(cls.model), "--riscv-model", str(cls.model),
                              "--out", str(cls.original)], capture_output=True, text=True,
                             env={**os.environ, "BENCH_INJECT_CORRUPTION": "0"}, timeout=60)
        if run.returncode != 0:
            raise AssertionError(run.stdout + run.stderr)

    def setUp(self):
        self.copy = tempfile.TemporaryDirectory(dir=self.base)
        self.addCleanup(self.copy.cleanup)
        self.output = Path(self.copy.name) / "relocated"
        shutil.copytree(self.original, self.output, ignore=shutil.ignore_patterns("bin"))
        self.case = "B01_spsc_ring"
        self.record_path = self.output / self.case / "result.json"
        self.record = json.loads(self.record_path.read_text())

    def save(self):
        self.record_path.write_text(json.dumps(self.record))

    def validate(self):
        self.save()
        return validate_benchmark_evidence(ROOT / "benchmarks", self.case, self.output)

    def rewrite_artifact(self, relative, text):
        path = self.output / relative
        path.write_text(text)
        self.record["evidence"]["artifacts"][relative] = hashlib.sha256(path.read_bytes()).hexdigest()

    def collect(self):
        self.save()
        entry = next(e for e in json.loads((ROOT / "correctness_manifest.json").read_text())["cases"]
                     if e["id"] == self.case)
        return reporter.collect_case(ROOT, entry, self.output)

    def test_relocated_complete_evidence_needs_no_binary(self):
        for case in ("B01_spsc_ring", "B02_spinlock"):
            r = validate_benchmark_evidence(ROOT / "benchmarks", case, self.output)
            self.assertEqual(r["native_status"], "PASS")
            self.assertEqual(r["projection_status"], "PASS")
            self.assertEqual(r["evidence_validation"]["status"], "PASS")
            self.assertEqual(r["correctness"]["layers"]["architecture"]["review_status"], "UNKNOWN")
        self.assertEqual(r["protocol_status"], "PASS")
        self.assertFalse(list(self.output.rglob("bin")))

    def test_only_inputs_and_result_json_cannot_pass(self):
        for child in (self.output / self.case).iterdir():
            if child.is_dir():
                shutil.rmtree(child)
        r = self.collect()
        self.assertEqual(r["evidence"]["status"], "UNKNOWN")
        self.assertEqual(r["execution_comparison"], "UNKNOWN")

    def test_legacy_or_wrong_case_cannot_pass(self):
        original = deepcopy(self.record)
        for change in (lambda: self.record.pop("evidence"),
                       lambda: self.record.update(case="B02_spinlock")):
            self.record = deepcopy(original)
            change()
            self.assertEqual(self.collect()["execution_comparison"], "UNKNOWN")

    def test_missing_or_modified_trace_is_unknown(self):
        relative = self.record["native"][0]["fifo_check"]["path"]
        trace = self.output / relative
        original = trace.read_bytes()
        trace.unlink()
        self.assertEqual(self.validate()["native_status"], "UNKNOWN")
        trace.write_bytes(original + b"1\n")
        self.assertEqual(self.validate()["native_status"], "UNKNOWN")

    def test_missing_stderr_or_manifest_entry_is_unknown(self):
        relative = self.record["native"][0]["stderr_log"]
        (self.output / relative).unlink()
        self.assertEqual(self.validate()["native_status"], "UNKNOWN")
        (self.output / relative).write_text("")
        del self.record["evidence"]["artifacts"][relative]
        self.assertEqual(self.validate()["native_status"], "UNKNOWN")

    def test_stale_snapshot_is_rejected(self):
        snapshot = input_snapshot(ROOT / "benchmarks")
        snapshot["B01_spsc_ring/benchmark.c"] = "old"
        (self.output / "inputs.json").write_text(json.dumps(snapshot))
        self.assertEqual(self.collect()["execution_comparison"], "UNKNOWN")

    def test_changed_model_include_invalidates_comparison(self):
        original = self.include.read_text()
        self.addCleanup(self.include.write_text, original)
        self.include.write_text(original + "(* changed *)\n")
        self.assertEqual(self.validate()["projection_status"], "UNKNOWN")

    def test_missing_model_closure_member_is_unknown(self):
        self.record["projections"][0]["model_files"].pop(str(self.include))
        self.assertEqual(self.validate()["projection_status"], "UNKNOWN")

    def test_missing_and_duplicate_required_checks_are_unknown(self):
        original = deepcopy(self.record)
        for key in ("native", "builds", "projections"):
            for duplicate in (False, True):
                self.record = deepcopy(original)
                if duplicate:
                    self.record[key].append(deepcopy(self.record[key][0]))
                else:
                    self.record[key].pop()
                r = self.validate()
                self.assertEqual(r["projection_status" if key == "projections" else "native_status"], "UNKNOWN")

    def test_native_comparison_ignores_cached_pass_and_detects_wrong_observation(self):
        item = self.record["native"][0]
        actual = json.loads((self.output / item["stdout_log"]).read_text())
        actual["produced"] -= 1
        self.rewrite_artifact(item["stdout_log"], json.dumps(actual))
        r = self.collect()
        self.assertEqual(r["execution_comparison"], "FAIL")
        self.assertEqual(r["layers"]["behavior"]["native_comparison"], "FAIL")

    def test_raw_model_observation_wins_over_cached_pass(self):
        item = self.record["projections"][0]
        self.rewrite_artifact(item["stdout_log"], "Observation Fixture Always 1 0\n")
        r = self.validate()
        self.assertEqual(r["projection_status"], "FAIL")
        self.assertEqual(r["projections"][0]["actual"], "Always")

    def test_reliable_fail_survives_unavailable_other_evidence(self):
        item = self.record["projections"][0]
        self.rewrite_artifact(item["stdout_log"], "Observation Fixture Always 1 0\n")
        (self.output / self.record["native"][0]["fifo_check"]["path"]).unlink()
        r = self.collect()
        self.assertEqual(r["evidence"]["status"], "UNKNOWN")
        self.assertEqual(r["execution_comparison"], "FAIL")

    def test_cached_failure_and_review_are_also_recomputed(self):
        self.record.update(native_status="FAIL", projection_status="FAIL")
        for item in self.record["native"] + self.record["projections"]:
            item["status"] = "FAIL"
        self.record["correctness"]["layers"]["architecture"]["review_status"] = "CONFIRMED"
        r = self.validate()
        self.assertEqual(r["native_status"], "PASS")
        self.assertEqual(r["projection_status"], "PASS")
        self.assertEqual(r["correctness"]["layers"]["architecture"]["review_status"], "UNKNOWN")

    def test_outside_path_and_edited_parameters_are_rejected(self):
        original = deepcopy(self.record)
        self.record["native"][0]["stdout_log"] = str(self.original / self.record["native"][0]["stdout_log"])
        self.assertEqual(self.validate()["native_status"], "UNKNOWN")
        self.record = original
        self.record["native"][0]["command"][2] = "1"
        self.assertEqual(self.validate()["native_status"], "UNKNOWN")

    def test_malformed_execution_does_not_hide_another_reliable_failure(self):
        item = self.record["projections"][0]
        self.rewrite_artifact(item["stdout_log"], "Observation Fixture Always 1 0\n")
        self.record["native"][0]["command"] = []
        self.record["native"].append(None)
        self.record["projections"].append(None)
        self.assertEqual(self.collect()["execution_comparison"], "FAIL")

    def test_missing_binary_hash_and_wrong_model_command_are_unknown(self):
        self.record["builds"][0].pop("binary_sha256")
        self.record["projections"][0]["command"][-1] = "/tmp/unrelated.litmus"
        r = self.validate()
        self.assertEqual(r["native_status"], "UNKNOWN")
        self.assertEqual(r["projection_status"], "UNKNOWN")

    def test_protocol_requires_all_checks_and_raw_logs(self):
        self.case = "B02_spinlock"
        self.record_path = self.output / self.case / "result.json"
        self.record = json.loads(self.record_path.read_text())
        relative = self.record["protocol"]["stdout_log"]
        original = (self.output / relative).read_text()
        payload = json.loads(original)
        payload["checks"].pop()
        self.rewrite_artifact(relative, json.dumps(payload))
        self.assertEqual(self.validate()["protocol_status"], "UNKNOWN")
        self.rewrite_artifact(relative, original)
        (self.output / relative).unlink()
        self.assertEqual(self.validate()["protocol_status"], "UNKNOWN")

    def test_unknown_evidence_can_be_rendered_as_report(self):
        (self.output / self.record["native"][0]["fifo_check"]["path"]).unlink()
        self.save()
        report = self.output / "collected"
        report.mkdir()
        r = reporter.write_report(ROOT, report,
                                  {"benchmarks": self.output, "internal": self.output / "missing",
                                   "prototype": self.output / "missing"}, [])
        self.assertEqual(r["execution_comparison_status"], "UNKNOWN")
        self.assertIn("证据问题", (report / "summary.md").read_text())


if __name__ == "__main__":
    unittest.main()
