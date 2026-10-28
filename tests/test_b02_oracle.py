"""Independent record evidence and bounded protocol counterexamples for B02."""
from copy import deepcopy
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
from oracle_contract import attach_correctness, validate_contract
from record_oracle import check_trace
from run_suite import native_result
from spinlock_protocol import explore, run_checks


class RecordEvidenceTests(unittest.TestCase):
    CHECKSUMS = [6510698343141591806, 14154211219428849387, 7364606772616180436,
                 9294524224464142017, 2488031261898324650]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.trace = self.root / "updates.jsonl"
        c = self.CHECKSUMS
        # Export groups by worker, not global execution order: 1,3 then 2,4.
        self.rows = [[0, 1, 0, c[0], 1, c[1]], [0, 2, 2, c[2], 3, c[3]],
                     [1, 1, 1, c[1], 2, c[2]], [1, 2, 3, c[3], 4, c[4]]]

    def record(self, rows):
        self.trace.write_text('{"schema":"b02-record-trace-1"}\n'
                              + ''.join(json.dumps(row) + '\n' for row in rows))

    def test_complete_interleaved_chain_from_private_worker_buffers(self):
        self.record(self.rows)
        r = check_trace(self.trace, 2)
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(r["observed_updates"], 4)
        self.assertEqual(r["worker_updates"], [2, 2])
        self.assertEqual(r["missing_committed_counts"], 0)
        self.assertEqual(len(r["sha256"]), 64)

    def test_duplicate_skipped_bad_checksum_and_reversed_worker_progress(self):
        mutations = []
        rows = deepcopy(self.rows)
        rows[2][2:] = rows[0][2:]
        mutations.append(rows)  # Same total rows, but duplicated committed count.
        rows = deepcopy(self.rows)
        rows[0][4] = 2
        mutations.append(rows)  # A jump must not pass on final counts alone.
        rows = deepcopy(self.rows)
        rows[1][3] ^= 1
        mutations.append(rows)  # Bad intermediate before checksum.
        rows = deepcopy(self.rows)
        rows[0][5] ^= 1
        mutations.append(rows)  # Bad intermediate after checksum.
        rows = deepcopy(self.rows)
        rows[0][2:], rows[1][2:] = rows[1][2:], rows[0][2:]
        mutations.append(rows)  # Complete union, but this worker goes backwards.
        for rows in mutations:
            with self.subTest(rows=rows):
                self.record(rows)
                self.assertEqual(check_trace(self.trace, 2)["status"], "FAIL")

    def test_missing_extra_wrong_worker_and_wrong_ordinal(self):
        bad_worker = deepcopy(self.rows)
        bad_worker[0][0] = 2
        bad_ordinal = deepcopy(self.rows)
        bad_ordinal[0][1] = 2
        for rows in ([], self.rows[:-1], self.rows + [self.rows[-1]], bad_worker, bad_ordinal):
            with self.subTest(rows=rows):
                self.record(rows)
                self.assertEqual(check_trace(self.trace, 2)["status"], "FAIL")

    def test_missing_malformed_and_noninteger_observations_are_not_pass(self):
        self.assertEqual(check_trace(self.trace, 2)["status"], "UNKNOWN")
        for text in ('', '{}\n', '{"schema":"b02-record-trace-1"}\nnot-json\n'):
            self.trace.write_text(text)
            self.assertEqual(check_trace(self.trace, 2)["status"], "UNKNOWN")
        for value in (True, 1.0, -1, 2**64):
            rows = deepcopy(self.rows)
            rows[0][2] = value
            self.record(rows)
            self.assertEqual(check_trace(self.trace, 2)["status"], "UNKNOWN")
        self.record([self.rows[0], self.rows[0]])
        with self.trace.open("a") as stream:
            stream.write("malformed\n")
        self.assertEqual(check_trace(self.trace, 2)["status"], "FAIL")

    def test_runner_rejects_bad_intermediate_records_despite_correct_final_values(self):
        actual = dict(case="B02_spinlock", status="PASS", preflight=True, completed=[2, 2],
                      errors=[0, 0], final_count=4, checksum=self.CHECKSUMS[4], locked=0)
        log = self.root / "stdout.txt"
        log.write_text(json.dumps(actual))
        execution = {"stdout_log": str(log), "returncode": 0, "reason": None}
        expected = {"status": "PASS", "returncode": 0}
        args = ["--iterations", "2", "--trace", str(self.trace)]
        self.record(self.rows)
        self.assertEqual(native_result(execution, actual["case"], expected, args)["status"], "PASS")
        self.rows[0][5] ^= 1
        self.record(self.rows)
        self.assertEqual(native_result(execution, actual["case"], expected, args)["status"], "FAIL")
        self.trace.unlink()
        self.assertEqual(native_result(execution, actual["case"], expected, args)["status"], "UNKNOWN")

    @unittest.skipUnless(shutil.which("cc"), "requires C11 compiler")
    def test_shared_intermediate_checksum_bug_evades_c_and_final_check(self):
        copied = self.root / "benchmarks"
        shutil.copytree(ROOT / "benchmarks", copied, ignore=shutil.ignore_patterns("build", "__pycache__"))
        source = copied / "B02_spinlock/benchmark.c"
        original = "return count * UINT64_C(11400714819323198485) ^ UINT64_C(0x5a5aa5a5deadcafe);"
        mutant = ("return (count * UINT64_C(11400714819323198485) ^ UINT64_C(0x5a5aa5a5deadcafe))"
                  " ^ (count == 1 ? UINT64_C(1) : UINT64_C(0));")
        self.assertIn(original, source.read_text())
        source.write_text(source.read_text().replace(original, mutant))
        binary = self.root / "checksum_mutant"
        build = subprocess.run(["bash", str(copied / "B02_spinlock/build.sh"), str(binary)],
                               env={**os.environ, "CC": shutil.which("cc"), "BENCH_INJECT_CORRUPTION": "0"},
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(build.returncode, 0, build.stderr)
        run = subprocess.run([str(binary), "--iterations", "2", "--trace", str(self.trace)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        final = json.loads(run.stdout)
        self.assertEqual(final["status"], "PASS")
        self.assertEqual(final["checksum"], self.CHECKSUMS[4])
        self.assertEqual(check_trace(self.trace, 2)["status"], "FAIL")
        original_trace = self.trace.read_bytes()
        repeated = subprocess.run([str(binary), "--iterations", "2", "--trace", str(self.trace)],
                                  capture_output=True, text=True, timeout=30)
        self.assertEqual(repeated.returncode, 2)
        self.assertEqual(self.trace.read_bytes(), original_trace)


class ProtocolTests(unittest.TestCase):
    def test_atomic_protocol_exhausts_all_finite_states_and_exercises_contention(self):
        for rounds in (1, 2, 3):
            r = explore(rounds)
            self.assertEqual(r["status"], "PASS")
            self.assertGreater(r["terminal_states"], 0)
            for action in ("cas_failure_updates_expected", "wait_observes_zero", "reset_expected", "release_unlock"):
                self.assertGreater(r["actions"].get(action, 0), 0)

    def test_split_cas_and_missing_reset_have_concrete_overlapping_holders(self):
        for variant in ("split_cas", "missing_expected_reset"):
            r = explore(2, variant)
            self.assertEqual(r["status"], "FAIL")
            last = r["counterexample"][-1]["state"]
            holders = [w for w in last["workers"] if w["pc"] in ("critical", "unlock")]
            self.assertEqual(len(holders), 2)
        # Missing reset requires another acquisition; one round is insufficient here.
        self.assertEqual(explore(1, "missing_expected_reset")["status"], "PASS")

    def test_controls_compare_as_pass_but_remain_separate_from_formal_review(self):
        r = run_checks()
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(len(r["checks"]), 5)
        self.assertEqual(r["formal_review"], "UNKNOWN")
        self.assertTrue(all(c["comparison_status"] == "PASS" for c in r["checks"]))
        root = ROOT / "benchmarks"
        oracle = validate_contract(root, "B02_spinlock")
        record = {"native": [], "native_status": "UNKNOWN", "projection_status": "UNKNOWN",
                  "projections": [], "protocol": r, "protocol_status": "PASS"}
        attach_correctness(root, "B02_spinlock", oracle, record, "test-subject")
        mutex = next(o for o in record["correctness"]["obligations"] if o["id"] == "B02-MUTEX")
        self.assertEqual(mutex["bounded_protocol"]["comparison_status"], "PASS")
        self.assertEqual(mutex["full_verification"]["status"], "UNKNOWN")
        self.assertEqual(record["correctness"]["layers"]["architecture"]["review_status"], "UNKNOWN")

    def test_changed_machine_contract_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "benchmarks"
            shutil.copytree(ROOT / "benchmarks", root, ignore=shutil.ignore_patterns("build", "__pycache__"))
            path = root / "B02_spinlock/oracle.json"
            original = json.loads(path.read_text())
            for key in ("record_contract", "protocol_contract"):
                modified = deepcopy(original)
                del modified[key]
                path.write_text(json.dumps(modified))
                with self.assertRaisesRegex(ValueError, "contract"):
                    validate_contract(root, "B02_spinlock")


if __name__ == "__main__":
    unittest.main()
