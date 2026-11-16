"""Original B02 region extraction and independent semantic corruption controls."""
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

from scripts.benchmark_region_comparison import check_b02
from scripts.run_benchmark_regions import run


ROOT = Path(__file__).resolve().parents[1]
TEAM = ROOT.parent / "RV-MemoryConsistency-TeamDev"
CLANG = os.environ.get("PROTOTYPE_CLANG", str(ROOT.parent / ".tools/clang18/bin/clang"))


def read(path):
    return json.loads(path.read_text())


def save(path,value):
    path.write_text(json.dumps(value,indent=2)+"\n")


@unittest.skipUnless((TEAM / "verification_pipeline/bounded").is_dir() and Path(CLANG).is_file(), "team bounded extractor/Clang unavailable")
class BenchmarkRegionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = TEAM / ".case-regression-runs"
        root.mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=root,prefix="b02-region-tests-")
        cls.root = Path(cls.temp.name)
        cls.original = run(TEAM,cls.root / "seed",CLANG)
        cls.config = read(ROOT / "tests/team_pipeline/benchmarks/b02.regions.json")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.path = self.root / self._testMethodName
        shutil.copytree(self.root / "seed/regions",self.path)

    def mutate(self,edit,file="paths-0.json"):
        document=read(self.path / file)
        edit(document)
        save(self.path / file,document)
        result=check_b02(self.path,self.config)
        self.assertNotEqual(result["status"],"PASS",result)
        return result

    def test_independent_analytical_path_coverage_and_unknown_scope(self):
        self.assertEqual(self.original["process_status"],"PASS")
        self.assertEqual(self.original["region_comparison"],"PASS")
        self.assertEqual((self.original["path_count"],self.original["returned_paths"],self.original["boundary_paths"]),(40,27,13))
        self.assertEqual(self.original["full_program_consistency"],"UNKNOWN")
        self.assertTrue(all(o["full_verification"]=="UNKNOWN" for o in self.original["obligations"].values()))
        self.assertEqual(check_b02(self.path,self.config)["status"],"PASS")

    def test_missing_expected_failure_writeback_is_detected(self):
        def edit(document):
            path=document["paths"][0]
            path["actions"]=[a for a in path["actions"] if a.get("reason")!="cas_expected_writeback"]
            for index,action in enumerate(path["actions"]): action["index"]=index
        self.assertEqual(self.mutate(edit)["status"],"FAIL")

    def test_missing_retry_reset_is_detected(self):
        def edit(document):
            path=next(p for p in document["paths"] if sum(e["kind"]=="CAS" for e in p["events"])==2)
            path["actions"]=[a for a in path["actions"] if a.get("reason")!="assignment"]
            for index,action in enumerate(path["actions"]): action["index"]=index
        self.assertEqual(self.mutate(edit)["status"],"FAIL")

    def test_split_cas_is_detected(self):
        self.mutate(lambda d:d["paths"][0]["events"][0].update(kind="Load",indivisible=False))

    def test_failed_cas_must_not_unconditionally_write(self):
        self.assertEqual(self.mutate(lambda d:d["paths"][0]["events"][0].update(write_condition={"op":"const","type":"Bool","value":1}))["status"],"FAIL")

    def test_changed_memory_order_is_detected(self):
        self.assertEqual(self.mutate(lambda d:d["paths"][0]["events"][0].update(failure_order="Acquire"))["status"],"FAIL")

    def test_missing_live_boundary_path_is_detected(self):
        self.assertEqual(self.mutate(lambda d:d["paths"].__setitem__(slice(None),[p for p in d["paths"] if p["termination"]!="BOUNDARY"]))["status"],"FAIL")

    def test_removed_failure_guard_is_detected(self):
        self.assertEqual(self.mutate(lambda d:d["paths"][0]["guards"].pop(0))["status"],"FAIL")

    def test_event_source_corruption_is_detected(self):
        self.assertEqual(self.mutate(lambda d:d["paths"][0]["events"][0]["source"].update(line=999))["status"],"FAIL")

    def test_feasibility_or_model_promotion_is_detected(self):
        self.assertEqual(self.mutate(lambda d:d["paths"][0].update(feasibility="SAT"))["status"],"FAIL")
        self.assertEqual(self.mutate(lambda d:d.update(full_program_model_verification="PASS"),file="manifest.json")["status"],"FAIL")

    def test_startup_rmw_value_and_exit_guard_are_checked(self):
        self.assertEqual(self.mutate(lambda d:d["paths"][0]["events"][0].update(value={"op":"const","type":"U32","value":1}),file="paths-3.json")["status"],"FAIL")
        self.assertEqual(self.mutate(lambda d:d["paths"][0]["guards"].pop(0),file="paths-8.json")["status"],"FAIL")

    def test_missing_actual_file_never_passes(self):
        (self.path / "paths-0.json").unlink()
        self.assertEqual(check_b02(self.path,self.config)["status"],"UNKNOWN")

    def test_real_source_reset_removal_is_detected_after_explicit_repin(self):
        # Derived control only. Preserve line numbers, and intentionally re-pin
        # changed bytes so this tests extraction/semantics rather than stale pins.
        derived=self.path / "derived"
        shutil.copytree(self.root / "seed/input",derived)
        header=derived / "common/dpdk_spinlock.h"
        original=header.read_text()
        changed=original.replace("\t\texp = 0;","\t\t(void)0;")
        self.assertNotEqual(changed,original)
        header.write_text(changed)
        config=deepcopy(self.config)
        changed_hash=hashlib.sha256(header.read_bytes()).hexdigest()
        config["source_files"]["common/dpdk_spinlock.h"]=changed_hash
        config["loops"][0]["sha256"]=changed_hash
        save(self.path / "derived-config.json",config)
        completed=subprocess.run([sys.executable,"-m","verification_pipeline.bounded","--source",str(derived / "B02_spinlock/benchmark.c"),
                                  "--input-root",str(derived),"--config",str(self.path / "derived-config.json"),"--out",str(self.path / "derived-out"),"--clang",CLANG],
                                 cwd=TEAM,capture_output=True,text=True,timeout=60)
        self.assertEqual(completed.returncode,2,completed.stdout+completed.stderr)
        result=check_b02(self.path / "derived-out",config)
        self.assertEqual(result["status"],"FAIL",result)
        self.assertTrue(any("reset" in message or "0-to-1" in message for message in result["failures"]))

    def test_manual_requirements_cover_all_eight_original_obligations(self):
        manifest=read(ROOT / "benchmarks/obligations_manifest.json")
        for case,wanted in manifest["cases"].items():
            contract=read(ROOT / f"tests/team_pipeline/benchmarks/{case}.structure.json")
            self.assertEqual(set(contract["obligations"]),set(wanted))
            self.assertEqual(contract["review_status"],"DRAFT_UNREVIEWED")
            self.assertTrue(all(o["required"] and o["remaining"] for o in contract["obligations"].values()))


if __name__ == "__main__":
    unittest.main()
