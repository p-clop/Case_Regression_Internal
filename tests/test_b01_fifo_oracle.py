"""Check independent B01 evidence against faults shared by both C workers."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks/scripts"))
from fifo_oracle import check_trace
from run_suite import native_result


class FifoEvidenceTests(unittest.TestCase):
    # Fixed arithmetic vectors; do not generate these by calling the checker.
    WORDS = [5294400491, 11170195768, 15015819081]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.trace = self.directory / "messages.jsonl"

    def record(self, values):
        self.trace.write_text('{"schema":"b01-fifo-trace-1"}\n'
                              + ''.join(json.dumps(value) + '\n' for value in values))

    def test_known_vectors_and_complete_trace(self):
        self.record(self.WORDS)
        result = check_trace(self.trace, 3)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["observed_count"], 3)
        self.assertEqual(len(result["sha256"]), 64)

    def test_count_preserving_sequence_and_payload_faults_are_rejected(self):
        a, b, c = self.WORDS
        faults = {"duplicate": [a, a, c], "reordered": [b, a, c],
                  "stale_slot": [a, b, a], "checksum": [a, b ^ 1, c],
                  "wrong_encoder_both_workers": [word ^ 2 for word in self.WORDS]}
        for name, values in faults.items():
            with self.subTest(name=name):
                self.record(values)
                self.assertEqual(check_trace(self.trace, 3)["status"], "FAIL")

    def test_lost_extra_and_empty_messages_are_rejected(self):
        for values in (self.WORDS[:-1], self.WORDS + [self.WORDS[-1]], []):
            with self.subTest(values=values):
                self.record(values)
                self.assertEqual(check_trace(self.trace, 3)["status"], "FAIL")

    def test_missing_or_malformed_evidence_stays_unknown(self):
        self.assertEqual(check_trace(self.trace, 3)["status"], "UNKNOWN")
        for text in ('', '{}\n', '{"schema":"b01-fifo-trace-1"}\nnot-json\n'):
            self.trace.write_text(text)
            self.assertEqual(check_trace(self.trace, 3)["status"], "UNKNOWN")
        for value in (True, -1, 2**64, 1.0):
            self.record([value])
            self.assertEqual(check_trace(self.trace, 1)["status"], "UNKNOWN")

    def test_runner_cannot_trust_false_pass_with_correct_final_counts(self):
        actual = dict(case="B01_spsc_ring", status="PASS", preflight=True,
                      produced=3, consumed=3, final_index=3, final_indexes=[3]*4)
        stdout = self.directory / "stdout.txt"
        stdout.write_text(json.dumps(actual))
        execution = {"stdout_log": str(stdout), "returncode": 0, "reason": None}
        expected = {"returncode": 0, "status": "PASS"}
        args = ["--iterations", "3", "--trace", str(self.trace)]
        self.record([self.WORDS[0]] * 3)
        self.assertEqual(native_result(execution, actual["case"], expected, args)["status"], "FAIL")
        self.record(self.WORDS)
        self.assertEqual(native_result(execution, actual["case"], expected, args)["status"], "PASS")
        self.trace.unlink()
        self.assertEqual(native_result(execution, actual["case"], expected, args)["status"], "UNKNOWN")

    def test_confirmed_mismatch_survives_later_malformed_evidence(self):
        for tail in ("not-json", "true", "-1"):
            self.trace.write_text('{"schema":"b01-fifo-trace-1"}\n5294400490\n' + tail + '\n')
            result = check_trace(self.trace, 2)
            self.assertEqual(result["mismatch_count"], 1)
            self.assertEqual(result["status"], "FAIL")

    @unittest.skipUnless(shutil.which("cc"), "requires a C11 compiler")
    def test_shared_c_encoder_bug_passes_c_but_fails_independent_oracle(self):
        copied = self.directory / "benchmarks"
        shutil.copytree(ROOT / "benchmarks", copied,
                        ignore=shutil.ignore_patterns("build", "__pycache__"))
        source = copied / "B01_spsc_ring/benchmark.c"
        source.write_text(source.read_text().replace("UINT32_C(2654435761)", "UINT32_C(2654435763)"))
        binary = self.directory / "encoder_mutant"
        build = subprocess.run(["bash", str(copied / "B01_spsc_ring/build.sh"), str(binary)],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(build.returncode, 0, build.stderr)
        run = subprocess.run([str(binary), "--iterations", "20", "--trace", str(self.trace)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["status"], "PASS")
        self.assertEqual(check_trace(self.trace, 20)["status"], "FAIL")
        # A pre-existing trace must never be overwritten by a second run.
        before = self.trace.read_bytes()
        repeated = subprocess.run([str(binary), "--iterations", "20", "--trace", str(self.trace)],
                                  capture_output=True, text=True, timeout=30)
        self.assertEqual(repeated.returncode, 2)
        self.assertEqual(self.trace.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
