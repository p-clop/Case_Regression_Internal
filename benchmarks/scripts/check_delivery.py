#!/usr/bin/env python3
"""Check portable builds, provenance rejection and honest UNKNOWN handling."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def check_delivery():
    checks = {}
    executions = []
    gcc = shutil.which("gcc")
    if not gcc:
        return {"status": "UNKNOWN", "reason": "gcc unavailable", "checks": {}}
    with tempfile.TemporaryDirectory(prefix="rv-benchmark-delivery-") as temp:
        temp = Path(temp)
        copied = temp / "benchmarks"
        shutil.copytree(ROOT, copied, ignore=shutil.ignore_patterns("build", "__pycache__"))

        def invoke(command):
            result = subprocess.run([str(x) for x in command], capture_output=True, text=True, timeout=60)
            executions.append({"command": [str(x) for x in command], "returncode": result.returncode,
                               "stdout": result.stdout, "stderr": result.stderr})
            return result

        checker = copied / "scripts/check_sources.py"
        result = invoke(["python3", checker])
        checks["copied_source_integrity"] = result.returncode == 0
        upstream = copied / "vendor/dpdk/rte_ring_c11_pvt.h"
        original = upstream.read_bytes()
        upstream.write_bytes(original + b"\n")
        result = invoke(["python3", checker])
        checks["upstream_tamper_rejected"] = result.returncode != 0 and "hash mismatch" in result.stderr
        upstream.write_bytes(original)
        extracted = copied / "common/dpdk_spinlock.h"
        original = extracted.read_text()
        extracted.write_text(original.replace("rte_memory_order_acquire", "rte_memory_order_relaxed"))
        result = invoke(["python3", checker])
        checks["ordering_tamper_rejected"] = result.returncode != 0 and "differs from upstream" in result.stderr
        extracted.write_text(original)
        result = invoke(["bash", copied / "run.sh", "--compiler", gcc, "--no-models", "--out", temp / "native-only"])
        summary = json.loads((temp / "native-only/summary.json").read_text())
        checks["portable_native_build_and_run"] = all(c["native_status"] == "PASS" for c in summary["cases"].values())
        checks["unexecuted_models_unknown"] = (result.returncode == 2 and summary["model_executions"] == 0
            and all(c["projection_status"] == "UNKNOWN" for c in summary["cases"].values()))
        result = invoke(["bash", copied / "run.sh", "--compiler", temp / "missing-cc", "--no-models", "--out", temp / "missing-tool"])
        summary = json.loads((temp / "missing-tool/summary.json").read_text())
        checks["missing_compiler_unknown"] = (result.returncode == 2
            and all(c["native_status"] == "UNKNOWN" for c in summary["cases"].values()))
        oracle_path = copied / "B01_spsc_ring/oracle.json"
        original = oracle_path.read_text()
        oracle = json.loads(original)
        oracle["obligations"] = [o for o in oracle["obligations"] if o["id"] != "B01-FIFO"]
        oracle_path.write_text(json.dumps(oracle))
        result = invoke(["bash", copied / "run.sh", "--compiler", gcc, "--out", temp / "incomplete-oracle"])
        summary = json.loads((temp / "incomplete-oracle/summary.json").read_text())
        checks["incomplete_oracle_unknown"] = result.returncode == 2 and summary["oracle_contract"]["status"] == "UNKNOWN"
        oracle_path.write_text(original)
        result = invoke(["bash", copied / "run.sh", "--out", temp / "native-only"])
        checks["stale_output_rejected"] = result.returncode == 1 and "fresh directory" in result.stderr
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "executions": executions}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="optional JSON evidence file")
    args = parser.parse_args()
    try:
        result = check_delivery()
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result = {"status": "UNKNOWN", "reason": str(exc)}
    if args.out:
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "executions"}, ensure_ascii=False))
    raise SystemExit({"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[result["status"]])
