"""Independent B01 FIFO observer: consume raw values, never call C message()."""
import argparse
import hashlib
import json
from pathlib import Path


FIFO_CONTRACT = {
    "trace_schema": "b01-fifo-trace-1",
    "sequence_start": 1,
    "checksum_multiplier": 2654435761,
    "checksum_xor": 0xa5a55a5a,
    "sequence_shift": 32,
    "checksum_modulus": 2**32,
}


def check_trace(path, iterations):
    """Check completeness, order and both payload halves for one bounded run."""
    if type(iterations) is not int or not 1 <= iterations <= 10000000:
        raise ValueError("iterations must be an integer in 1..10000000")
    result = {"path": str(path), "status": "UNKNOWN", "expected_count": iterations,
              "observed_count": 0, "mismatch_count": 0, "first_mismatches": [],
              "scope": "recorded consumer values for this bounded execution only"}
    digest = hashlib.sha256()

    def unavailable(reason):
        result["reason"] = reason
        result["status"] = "FAIL" if result["mismatch_count"] else "UNKNOWN"
        return result

    try:
        with Path(path).open("rb") as stream:
            header = stream.readline()
            digest.update(header)
            if json.loads(header) != {"schema": FIFO_CONTRACT["trace_schema"]}:
                return unavailable("invalid_trace_header")
            for position, line in enumerate(stream, 1):
                digest.update(line)
                value = json.loads(line)
                if type(value) is not int or not 0 <= value < 2**64:
                    return unavailable("invalid_uint64_observation")
                result["observed_count"] = position
                # Split the observed word rather than reuse the C encoder.
                sequence, checksum = divmod(value, FIFO_CONTRACT["checksum_modulus"])
                expected_checksum = ((position * FIFO_CONTRACT["checksum_multiplier"])
                                     % FIFO_CONTRACT["checksum_modulus"]) ^ FIFO_CONTRACT["checksum_xor"]
                if sequence != position or checksum != expected_checksum:
                    result["mismatch_count"] += 1
                    if len(result["first_mismatches"]) < 8:
                        result["first_mismatches"].append({
                            "position": position, "actual_sequence": sequence,
                            "actual_checksum": checksum, "expected_checksum": expected_checksum})
    except (OSError, ValueError, UnicodeError) as exc:
        return unavailable(f"trace_unavailable_or_malformed: {exc}")
    result["sha256"] = digest.hexdigest()
    result["status"] = ("PASS" if result["observed_count"] == iterations
                        and result["mismatch_count"] == 0 else "FAIL")
    if result["observed_count"] != iterations:
        result["reason"] = "message_count_mismatch"
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
