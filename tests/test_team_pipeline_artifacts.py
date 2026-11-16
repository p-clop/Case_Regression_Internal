"""Mutate actual delivered files while retaining cached PASS summaries."""
from copy import deepcopy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from prototype.pipeline import find_tool
from scripts.run_team_pipeline import case_consistency, read, save
from scripts.team_pipeline_artifacts import audit_pipeline_artifacts

ROOT = Path(__file__).resolve().parents[1]
TEAM = ROOT.parent / "RV-MemoryConsistency-TeamDev"
CLANG = find_tool("clang", os.getenv("PROTOTYPE_CLANG") or str(ROOT.parent / ".tools/clang18/bin/clang"))
HERD = find_tool("herd7", os.getenv("PROTOTYPE_HERD7"))


class ConsistencyTests(unittest.TestCase):
    def test_cached_comparisons_require_files_and_successful_execution(self):
        good = {key: {"status": "PASS"} for key in ("structure_comparison", "artifact_comparison", "full_structure_comparison", "query_comparison")}
        good.update(pipeline={"status": "PASS", "process_status": "PASS"}, baseline={"execution_comparison": "PASS"})
        self.assertEqual(case_consistency(good), "PASS")
        for field, status in (("artifact_comparison", "UNKNOWN"), ("artifact_comparison", "FAIL"), ("pipeline", "UNSUPPORTED")):
            changed = deepcopy(good)
            changed[field]["status"] = status
            self.assertEqual(case_consistency(changed), "FAIL" if status == "FAIL" else "UNKNOWN")


@unittest.skipUnless((TEAM / "verification_pipeline").is_dir() and CLANG and HERD, "TeamDev/Clang/herd7 unavailable")
class ArtifactEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (TEAM / ".case-regression-runs").mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=TEAM / ".case-regression-runs", prefix="artifact-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        source = cls.root / "case.c"
        shutil.copyfile(ROOT / "cases/P02_atomic_fence/case.c", source)
        save(cls.root / "queries.json", [{"id": "original_target", "event_values": {"T0:E2": 0, "T1:E2": 0}}])
        cls.command = [sys.executable, "-m", "verification_pipeline", "--source", str(source),
                       "--semantics", "hardware-projection", "--seed-object", "x", "--queries", str(cls.root / "queries.json"),
                       "--clang", CLANG, "--herd7", HERD]
        # P02's independent Oracle supplies its actual seed name.
        cls.command[cls.command.index("--seed-object") + 1] = read(ROOT / "cases/P02_atomic_fence/expected.json")["seed_objects"][0]
        cls.original = cls.root / "original"
        run = subprocess.run([*cls.command, "--out", str(cls.original), "--backend", "local"], cwd=TEAM, capture_output=True, text=True, timeout=60)
        if run.returncode != 0:
            raise AssertionError(run.stdout + run.stderr)

    def setUp(self):
        self.output = self.root / self._testMethodName
        shutil.copytree(self.original, self.output)

    def audit(self):
        return audit_pipeline_artifacts(self.output)

    def edit(self, relative, change):
        path = self.output / relative
        value = read(path)
        change(value)
        save(path, value)

    def test_complete_relocated_evidence_passes_and_records_hashes(self):
        result = self.audit()
        self.assertEqual(result["status"], "PASS", result["errors"])
        self.assertEqual(result["units"][0]["verified_model_results"], 10)
        self.assertIn("frontend/input/program.ll", result["sha256"])
        self.assertIn("backend/VU0/herd/riscv_outcome_000004.herd.txt", result["sha256"])

    def test_missing_intermediate_or_raw_files_cannot_pass(self):
        for name in ("frontend/input/program.ll", "frontend/input/clang_ast.stderr.txt", "backend/VU0/candidate.json",
                     "backend/VU0/litmus/x86_outcome_000000.litmus", "backend/VU0/herd/riscv_outcome_000004.herd.txt"):
            with self.subTest(name=name):
                path = self.output / name
                original = path.read_bytes()
                path.unlink()
                self.assertEqual(self.audit()["status"], "UNKNOWN")
                path.write_bytes(original)

    def test_raw_log_disagreement_with_cached_matrix_fails(self):
        path = self.output / "backend/VU0/herd/riscv_outcome_000004.herd.txt"
        path.write_text(path.read_text().replace("Never", "Sometimes"))
        self.assertEqual(self.audit()["status"], "FAIL")

    def test_wrong_test_identity_even_in_matching_raw_copies_fails(self):
        path = self.output / "backend/VU0/herd/riscv_outcome_000004.herd.txt"
        raw = path.read_text().replace("VU_riscv_outcome_000004", "OTHER_TEST")
        path.write_text(raw)
        self.edit("backend/VU0/outcome_matrix.json", lambda m: m["outcomes"][-1]["architectures"]["riscv"].update(raw_output=raw))
        self.assertEqual(self.audit()["status"], "FAIL")

    def test_changed_litmus_condition_fails(self):
        path = self.output / "backend/VU0/litmus/riscv_outcome_000004.litmus"
        path.write_text(path.read_text().replace("exists (0:x4=0", "exists (0:x4=1"))
        self.assertEqual(self.audit()["status"], "FAIL")

    def test_lost_enumerated_row_fails_even_with_targeted_result_preserved(self):
        self.edit("backend/VU0/outcome_matrix.json", lambda m: m["outcomes"].pop(0))
        self.assertEqual(self.audit()["status"], "FAIL")

    def test_mismatched_backend_handoff_fails(self):
        self.edit("backend/VU0/event_ir.json", lambda g: g["events"].pop())
        self.assertEqual(self.audit()["status"], "FAIL")

    def test_false_architecture_summary_fails(self):
        self.edit("backend/VU0/differential_summary.json", lambda m: m["outcomes"][-1].update(comparison="BOTH_ALLOWED"))
        self.assertEqual(self.audit()["status"], "FAIL")

    def test_wrong_model_command_input_fails(self):
        self.edit("backend/VU0/outcome_matrix.json", lambda m: m["outcomes"][-1]["architectures"]["riscv"]["command"].__setitem__(-1, "other.litmus"))
        self.assertEqual(self.audit()["status"], "FAIL")

    def test_backend_none_produces_artifacts_but_remains_unknown(self):
        destination = self.root / "no_models"
        run = subprocess.run([*self.command, "--out", str(destination), "--backend", "none"], cwd=TEAM, capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        result = audit_pipeline_artifacts(destination)
        self.assertEqual(result["status"], "UNKNOWN", result["errors"])
        self.assertEqual(result["units"][0]["verified_model_results"], 0)


if __name__ == "__main__":
    unittest.main()
