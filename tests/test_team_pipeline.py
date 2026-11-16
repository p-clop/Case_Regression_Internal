"""Do not turn unsupported, incomplete or mismatched pipeline evidence into PASS."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("team_regression", ROOT / "scripts/run_team_pipeline.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class PipelineEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.oracle = runner.read(ROOT / "tests/team_pipeline/sb.expected.json")

    def write(self, name, value):
        path = self.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        runner.save(path, value)

    def fixture(self):
        graph = {
            "shared_objects": [{"name": "x", "initial": 0}, {"name": "y", "initial": 0}],
            "thread_contexts": [{"id": "T0", "entry_function": "writer"}, {"id": "T1", "entry_function": "reader"}],
            "events": [
                {"thread": "T0", "kind": "Store", "object": "x", "ordering": "Relaxed", "value": 1},
                {"thread": "T0", "kind": "Load", "object": "y", "ordering": "Relaxed"},
                {"thread": "T1", "kind": "Store", "object": "y", "ordering": "Relaxed", "value": 1},
                {"thread": "T1", "kind": "Load", "object": "x", "ordering": "Relaxed"}],
            "relations": {"program_order": [["T0:E0", "T0:E1"], ["T1:E0", "T1:E1"]]}}
        self.write("frontend/input/event_ir.json", graph)
        self.write("manifest.json", {"units": [{"id": "VU0"}]})
        self.write("frontend/units/VU0/verification_unit.json", {
            "objects": ["x", "y"], "event_ids": ["T0:E0", "T0:E1", "T1:E0", "T1:E1"]})
        rows = [{"outcome": {"r0": a, "r1": b}, "architectures": {
            arch: {"status": "RAN", "observation": "Sometimes"} for arch in ("x86", "riscv")}}
            for a, b in ((0, 0), (0, 1), (1, 0), (1, 1))]
        self.write("backend/VU0/outcome_matrix.json", {"outcomes": rows})
        return graph, rows

    def test_unsupported_is_process_success_but_produces_no_structure_pass(self):
        self.write("manifest.json", {"pipeline_status": "UNSUPPORTED", "frontend": {
            "status": "UNSUPPORTED", "reason": "fence not supported"}, "herd_attempts": 0})
        result = runner.inspect_pipeline(self.output, {"returncode": 2})
        self.assertEqual((result["process_status"], result["status"]), ("PASS", "UNSUPPORTED"))
        self.assertEqual(runner.compare_structure(self.output, self.oracle["structure"])["status"], "UNKNOWN")

    def test_wrong_exit_code_or_missing_manifest_cannot_pass(self):
        self.assertEqual(runner.inspect_pipeline(self.output, {"returncode": 0})["process_status"], "UNKNOWN")
        self.write("manifest.json", {"pipeline_status": "UNSUPPORTED"})
        self.assertEqual(runner.inspect_pipeline(self.output, {"returncode": 0})["process_status"], "FAIL")

    def test_missing_or_failed_model_evidence_cannot_pass(self):
        _, rows = self.fixture()
        for state, expected in (("NOT_RUN", "UNKNOWN"), ("FAILED", "FAIL")):
            rows[0]["architectures"]["riscv"].update(status=state, observation=None)
            self.write("backend/VU0/outcome_matrix.json", {"outcomes": rows})
            self.assertEqual(runner.compare_control(self.output, self.oracle)["status"], expected)

    def test_wrong_architecture_observation_or_missing_outcome_fails(self):
        _, rows = self.fixture()
        rows[0]["architectures"]["riscv"]["observation"] = "Never"
        self.write("backend/VU0/outcome_matrix.json", {"outcomes": rows})
        self.assertEqual(runner.compare_control(self.output, self.oracle)["status"], "FAIL")
        self.write("backend/VU0/outcome_matrix.json", {"outcomes": rows[1:]})
        self.assertEqual(runner.compare_control(self.output, self.oracle)["status"], "FAIL")

    def test_dropped_event_changed_value_and_ordering_fail(self):
        graph, _ = self.fixture()
        mutations = [deepcopy(graph) for _ in range(3)]
        mutations[0]["events"].pop()
        mutations[1]["events"][0]["value"] = 2
        mutations[2]["events"][0]["ordering"] = "Plain"
        for changed in mutations:
            self.write("frontend/input/event_ir.json", changed)
            self.assertEqual(runner.compare_structure(self.output, self.oracle["structure"])["status"], "FAIL")

    def test_changed_program_order_or_unit_is_detected(self):
        graph, _ = self.fixture()
        self.assertEqual(runner.compare_control(self.output, self.oracle)["status"], "PASS")
        graph["relations"]["program_order"] = []
        self.write("frontend/input/event_ir.json", graph)
        self.assertEqual(runner.compare_control(self.output, self.oracle)["status"], "FAIL")
        self.fixture()
        self.write("frontend/units/VU0/verification_unit.json", {"objects": ["x"], "event_ids": ["T0:E0"]})
        self.assertEqual(runner.compare_control(self.output, self.oracle)["status"], "FAIL")

    def test_header_staging_and_input_changes_are_checked(self):
        source = self.output / "source"
        source.mkdir()
        for name in ("benchmarks/B/benchmark.c", "benchmarks/B/oracle.json", "benchmarks/B/oracle.md",
                     "benchmarks/common/header.h", "benchmarks/vendor/upstream.h"):
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixed source")
        inventory = runner.stage_inputs(source, self.output / "stage", [{"source": "benchmarks/B/benchmark.c",
            "oracle": "benchmarks/B/oracle.json", "explanation": "benchmarks/B/oracle.md"}])
        self.assertEqual(runner.changed_inputs(source, inventory), [])
        (source / "benchmarks/common/header.h").write_text("modified")
        self.assertEqual(runner.changed_inputs(source, inventory), ["benchmarks/common/header.h"])
        self.assertEqual((self.output / "stage/benchmarks/vendor/upstream.h").read_text(), "fixed source")

    def test_unknown_and_empty_sets_never_aggregate_to_pass(self):
        self.assertEqual(runner.aggregate([]), "UNKNOWN")
        self.assertEqual(runner.aggregate(["PASS", "UNKNOWN"]), "UNKNOWN")
        self.assertEqual(runner.aggregate(["UNKNOWN", "FAIL"]), "FAIL")


if __name__ == "__main__":
    unittest.main()
