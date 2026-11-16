#!/usr/bin/env python3
"""Stage original B02, extract bounded regions, independently check actual files.

This is an additional evidence layer. Exit 2 persists after region comparison
PASS because full Benchmark frontend/VU/ISA-model integration is incomplete.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

try:
    from .benchmark_region_comparison import check_b02
except ImportError:
    from benchmark_region_comparison import check_b02


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "tests/team_pipeline/benchmarks"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")


def run(team, out, clang):
    team, out = team.resolve(), out.resolve()
    if not out.is_relative_to(team) or out.exists():
        raise ValueError("Output must be a fresh directory inside team worktree")
    if not (team / "verification_pipeline/bounded").is_dir():
        raise ValueError("Team bounded-region extractor is unavailable")
    config_file = CONTRACTS / "b02.regions.json"
    config = json.loads(config_file.read_text())
    source_root = ROOT / "benchmarks"
    for filename, expected in config["source_files"].items():
        path = (source_root / filename).resolve()
        if not path.is_relative_to(source_root) or sha(path) != expected:
            raise ValueError(f"Reviewed source pin differs: {filename}")
    out.mkdir(parents=True)
    staged = out / "input"
    for filename, expected in config["source_files"].items():
        destination = staged / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / filename, destination)
        if sha(destination) != expected:
            raise ValueError(f"Staged source differs: {filename}")
    shutil.copyfile(config_file, out / "regions.json")
    for contract in CONTRACTS.glob("*.structure.json"):
        shutil.copyfile(contract, out / contract.name)
    inputs = [source_root / f for f in config["source_files"]] + [config_file, Path(__file__), ROOT / "scripts/benchmark_region_comparison.py"] + list(CONTRACTS.glob("*.structure.json"))
    inputs += sorted((team / "verification_pipeline").rglob("*.py"))
    snapshot = {str(path): sha(path) for path in inputs}
    save(out / "provenance.json", {"schema":"benchmark-region-provenance-1", "inputs": snapshot,
                                  "python":sys.version, "team_root":str(team), "staged_source_files":config["source_files"]})
    command = [sys.executable,"-m","verification_pipeline.bounded","--source",str(staged / "B02_spinlock/benchmark.c"),
               "--input-root",str(staged),"--config",str(out / "regions.json"),"--out",str(out / "regions"),"--clang",clang]
    completed = subprocess.run(command,cwd=team,capture_output=True,text=True,timeout=180)
    (out / "stdout.log").write_text(completed.stdout)
    (out / "stderr.log").write_text(completed.stderr)
    save(out / "invocation.json",{"command":command,"cwd":str(team),"returncode":completed.returncode})
    comparison = check_b02(out / "regions",config)
    save(out / "region_comparison.json",comparison)
    changed = [name for name,expected in snapshot.items() if not Path(name).is_file() or sha(Path(name)) != expected]
    staged_changed = [name for name,expected in config["source_files"].items() if sha(staged/name) != expected]
    manifest_path = out / "regions/manifest.json"
    extraction = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    process = "PASS" if completed.returncode == 2 and extraction.get("status") == "BOUNDARY" and not changed and not staged_changed else "FAIL"
    report = {"schema":"benchmark-region-evidence-1", "case":"B02_spinlock", "process_status":process,
              "region_comparison":comparison["status"],"extraction_status":extraction.get("status","UNKNOWN"),
              "path_count":sum(r["path_count"] for r in extraction.get("regions",[])),
              "returned_paths":sum(r["returned_paths"] for r in extraction.get("regions",[])),
              "boundary_paths":sum(r["boundary_paths"] for r in extraction.get("regions",[])),
              "full_program_frontend":"NOT_IMPLEMENTED","full_program_consistency":"UNKNOWN",
              "architecture_models":{"x86":"NOT_RUN","riscv":"NOT_RUN"},
              "input_version_status":"FAIL" if changed or staged_changed else "PASS",
              "changed_inputs":changed,"changed_staged_inputs":staged_changed,
              "obligations":{oid:{"requirement_status":"DRAFT_UNREVIEWED","full_verification":"UNKNOWN"}
                             for oid in ["B02-MUTEX","B02-HANDOFF","B02-RECORD","B02-BOUNDARY"]}}
    save(out / "summary.json",report)
    (out / "summary.md").write_text("# B02 有界函数区域证据\n\n"
        f"流程 {process}；独立区域比较 {comparison['status']}；路径抽取 {report['extraction_status']}。\n\n"
        f"实际读取原始头文件和 benchmark.c，生成 {report['path_count']} 条函数区域路径，"
        f"其中 {report['returned_paths']} 条返回、{report['boundary_paths']} 条到达边界。符号路径可行性 UNKNOWN。\n\n"
        "这些区域彼此独立，线程实例由配置给定。未执行 main/worker、线程组合、VU 闭包或双架构模型；完整程序一致性 UNKNOWN，退出码 2。\n\n"
        "[独立比较](region_comparison.json) · [实际路径清单](regions/manifest.json) · [来源快照](provenance.json)\n")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-root",type=Path,default=ROOT.parent / "RV-MemoryConsistency-TeamDev")
    parser.add_argument("--out",type=Path)
    parser.add_argument("--clang",default=os.environ.get("PROTOTYPE_CLANG",str(ROOT.parent / ".tools/clang18/bin/clang")))
    args=parser.parse_args()
    out=args.out or args.team_root / ".case-regression-runs" / ("benchmark-regions-"+datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%dT%H%M%S%f"))
    try:
        report=run(args.team_root,out,args.clang)
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        print(str(error),file=sys.stderr)
        return 1
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print(f"Report: {out / 'summary.md'}")
    return 1 if report["process_status"] == "FAIL" or report["region_comparison"] == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
