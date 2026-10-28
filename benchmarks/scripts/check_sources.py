#!/usr/bin/env python3
"""Verify pinned upstream bytes and mechanically extracted function bodies."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extracted_headers():
    upstream = ROOT / "vendor/dpdk"
    spin = (upstream / "rte_spinlock.h").read_text()
    notice = spin[:spin.index("*/") + 2]
    body = spin[spin.index("typedef struct __rte_lockable"):
                spin.index("/**\n * Test if the lock is taken.")]
    pause = (upstream / "rte_pause.h").read_text()
    match = re.search(r"static __rte_always_inline void\nrte_wait_until_equal_32\([^;{]+\{.*?^\}",
                      pause, re.DOTALL | re.MULTILINE)
    if not match:
        raise ValueError("upstream 32-bit wait definition not found")
    return {
        "common/dpdk_spinlock.h": notice + '\n/* Mechanically extracted; see scripts/check_sources.py. */\n'
        '#ifndef BENCH_DPDK_SPINLOCK_H\n#define BENCH_DPDK_SPINLOCK_H\n#include "platform.h"\n'
        + body + "\n#endif\n",
        "common/dpdk_wait.h": pause[:pause.index("*/") + 2]
        + '\n/* Mechanically extracted; included after platform definitions. */\n'
        '#ifndef BENCH_DPDK_WAIT_H\n#define BENCH_DPDK_WAIT_H\n'
        + match.group() + "\n#endif\n",
    }


def verify(write=False):
    manifest = json.loads((ROOT / "vendor/manifest.json").read_text())
    for item in manifest["files"]:
        path = ROOT / item["local_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"upstream hash mismatch: {path}")
    for name, expected in extracted_headers().items():
        path = ROOT / name
        if write:
            path.write_text(expected)
        elif not path.exists() or path.read_text() != expected:
            raise ValueError(f"extracted header differs from upstream: {name}")
    return {"status": "PASS", "commit": manifest["commit"],
            "upstream_files": len(manifest["files"]), "extracted_headers": 2}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-extracts", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.write_extracts), ensure_ascii=False))
