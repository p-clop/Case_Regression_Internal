"""Cross-tool regressions on original sources, including damaged delivered evidence."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from prototype.frontend import extract
from prototype.graph import build_unit
from scripts.team_pipeline_comparison import actual_artifacts, compare_full, compare_queries, query_specs

ROOT = Path(__file__).resolve().parents[1]
TEAM = ROOT.parent / "RV-MemoryConsistency-TeamDev"
CLANG = shutil.which(os.getenv("PROTOTYPE_CLANG", "clang")) or str(ROOT.parent / ".tools/clang18/bin/clang")


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value))


@unittest.skipUnless((TEAM / "verification_pipeline").is_dir() and Path(CLANG).is_file(), "TeamDev/Clang unavailable")
class DeliveredEvidenceTests(unittest.TestCase):
    def setUp(self):
        (TEAM / ".case-regression-runs").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=TEAM / ".case-regression-runs", prefix="comparison-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_case(self, name):
        case = ROOT / "cases" / name
        oracle = read(case / "expected.json")
        source = self.root / "input.c"
        shutil.copyfile(case / "case.c", source)
        command = ["python3", "-m", "verification_pipeline", "--source", str(source), "--out", str(self.root / "pipeline"),
                   "--semantics", "hardware-projection", "--backend", "none", "--clang", CLANG]
        for seed in oracle["seed_objects"]:
            command += ["--seed-object", seed]
        entry = next(e for e in read(ROOT / "correctness_manifest.json")["cases"] if e["id"] == name)
        specs = query_specs(entry, oracle, ROOT)
        save(self.root / "queries.json", [{k: spec[k] for k in ("id", "event_values")} for spec in specs])
        command += ["--queries", str(self.root / "queries.json")]
        result = subprocess.run(command, cwd=TEAM, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(read(self.root / "pipeline/manifest.json")["frontend"]["status"], "PASS")
        baseline = self.root / "baseline"
        baseline.mkdir()
        program = extract(case / "case.c", clang=CLANG)
        unit = build_unit(program, oracle["seed_objects"], oracle["outcome"])
        save(baseline / "eventir.json", program)
        save(baseline / "unit.json", unit)
        return oracle, baseline

    def test_alias_full_structure_passes_then_lost_binding_fails(self):
        oracle, baseline = self.run_case("C05_pointer_alias")
        self.assertEqual(compare_full(self.root / "pipeline", oracle, baseline)["status"], "PASS")
        path = self.root / "pipeline/frontend/units/VU0/event_ir.json"
        graph = read(path)
        graph["bindings"] = []
        save(path, graph)
        self.assertEqual(compare_full(self.root / "pipeline", oracle, baseline)["status"], "FAIL")

    def test_changed_provenance_and_allocation_assumption_fail(self):
        oracle, baseline = self.run_case("C03_heap_escape")
        self.assertEqual(compare_full(self.root / "pipeline", oracle, baseline)["status"], "PASS")
        path = self.root / "pipeline/frontend/input/event_ir.json"
        graph = read(path)
        graph["assumptions"] = []
        graph["shared_objects"][0]["origin"] = "global"
        save(path, graph)
        self.assertEqual(compare_full(self.root / "pipeline", oracle, baseline)["status"], "FAIL")

    def test_actual_slice_preserves_noise_extraction_and_removal(self):
        oracle, baseline = self.run_case("C08_unrelated_code")
        self.assertEqual(compare_full(self.root / "pipeline", oracle, baseline)["status"], "PASS")
        path = self.root / "pipeline/frontend/units/VU0/event_ir.json"
        graph = read(path)
        graph["verification_unit"]["slice"]["removed_events"] = []
        save(path, graph)
        save(path.with_name("verification_unit.json"), graph["verification_unit"])
        self.assertEqual(compare_full(self.root / "pipeline", oracle, baseline)["status"], "FAIL")

    def test_native_source_map_or_po_damage_is_not_hidden_by_normalization(self):
        oracle, baseline = self.run_case("C07_two_objects")
        self.assertEqual(compare_full(self.root / "pipeline", oracle, baseline)["status"], "PASS")
        path = self.root / "pipeline/frontend/input/source_map.json"
        mapping = read(path)
        mapping["events"].pop()
        save(path, mapping)
        self.assertEqual(compare_full(self.root / "pipeline", oracle, baseline)["status"], "UNKNOWN")

    def test_p03_full_structure_preserves_calls_and_value_dependency(self):
        oracle, baseline = self.run_case("P03_release_acquire_relay")
        self.assertEqual(compare_full(self.root / "pipeline", oracle, baseline)["status"], "PASS")
        path = self.root / "pipeline/frontend/units/VU0/event_ir.json"
        graph = read(path)
        graph["events"][3]["value"] = 1
        save(path, graph)
        self.assertEqual(compare_full(self.root / "pipeline", oracle, baseline)["status"], "FAIL")

    def test_unrun_targeted_models_cannot_be_compared_as_pass(self):
        oracle, baseline = self.run_case("P02_atomic_fence")
        specs = query_specs({"suite": "prototype"}, oracle, ROOT)
        self.assertEqual(compare_queries(self.root / "pipeline", specs)["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
