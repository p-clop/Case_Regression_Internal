"""Independently check B02 per-worker before/after observations after join."""
import argparse
import hashlib
import json
from pathlib import Path


RECORD_CONTRACT = {
    "trace_schema": "b02-record-trace-1",
    "workers": 2,
    "fields": ["worker", "ordinal", "before_count", "before_checksum", "after_count", "after_checksum"],
    "initial_count": 0,
    "increment": 1,
    "checksum_multiplier": 11400714819323198485,
    "checksum_xor": 0x5a5aa5a5deadcafe,
    "checksum_modulus": 2**64,
}


def check_trace(path, iterations):
    if type(iterations) is not int or not 1 <= iterations <= 10000000:
        raise ValueError("iterations must be an integer in 1..10000000")
    total = RECORD_CONTRACT["workers"] * iterations
    result = {"path": str(path), "status": "UNKNOWN", "expected_updates": total,
              "observed_updates": 0, "worker_updates": [0, 0], "mismatch_count": 0,
              "first_mismatches": [], "scope": "recorded bounded updates; not a mutex or weak-memory proof"}
    seen = bytearray(total + 1)
    previous_after = [0, 0]
    digest = hashlib.sha256()

    def mismatch(line, reason):
        result["mismatch_count"] += 1
        if len(result["first_mismatches"]) < 8:
            result["first_mismatches"].append({"line": line, "reason": reason})

    def unavailable(reason):
        result["reason"] = reason
        # Keep an already established counterexample even if later evidence is bad.
        result["status"] = "FAIL" if result["mismatch_count"] else "UNKNOWN"
        return result

    def expected_checksum(count):
        return ((count * RECORD_CONTRACT["checksum_multiplier"])
                % RECORD_CONTRACT["checksum_modulus"]) ^ RECORD_CONTRACT["checksum_xor"]

    try:
        with Path(path).open("rb") as stream:
            header = stream.readline()
            digest.update(header)
            if json.loads(header) != {"schema": RECORD_CONTRACT["trace_schema"]}:
                return unavailable("invalid_trace_header")
            for number, line in enumerate(stream, 2):
                digest.update(line)
                row = json.loads(line)
                if (not isinstance(row, list) or len(row) != 6
                        or any(type(v) is not int or not 0 <= v < 2**64 for v in row)):
                    return unavailable("invalid_uint64_update_record")
                worker, ordinal, before, before_checksum, after, after_checksum = row
                result["observed_updates"] += 1
                if worker not in (0, 1):
                    mismatch(number, "invalid_worker")
                    continue
                result["worker_updates"][worker] += 1
                if ordinal != result["worker_updates"][worker]:
                    mismatch(number, "non_consecutive_worker_ordinal")
                if before < previous_after[worker]:
                    mismatch(number, "worker_progress_went_backwards")
                previous_after[worker] = after
                if after != before + 1:
                    mismatch(number, "update_is_not_plus_one")
                if before_checksum != expected_checksum(before) or after_checksum != expected_checksum(after):
                    mismatch(number, "checksum_mismatch")
                if not 1 <= after <= total:
                    mismatch(number, "update_outside_expected_range")
                elif seen[after]:
                    mismatch(number, "duplicate_committed_count")
                else:
                    seen[after] = 1
    except (OSError, ValueError, UnicodeError) as exc:
        return unavailable(f"trace_unavailable_or_malformed: {exc}")
    result["sha256"] = digest.hexdigest()
    result["missing_committed_counts"] = total - sum(seen)
    if result["worker_updates"] != [iterations, iterations]:
        mismatch(0, "worker_update_count_mismatch")
    if result["observed_updates"] != total or result["missing_committed_counts"]:
        mismatch(0, "incomplete_update_chain")
    result["status"] = "FAIL" if result["mismatch_count"] else "PASS"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--iterations", required=True, type=int)
    args = parser.parse_args()
    try:
        checked = check_trace(args.trace, args.iterations)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(checked, ensure_ascii=False, indent=2))
    raise SystemExit({"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[checked["status"]])
