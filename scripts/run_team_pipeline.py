#!/usr/bin/env python3
"""Run unchanged catalog inputs through the TeamDev pipeline and a fresh baseline."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from time import monotonic
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prototype.pipeline import find_model, find_tool
from scripts.team_pipeline_comparison import compare_full, compare_queries, query_specs, compare_equivalence
from scripts.team_pipeline_artifacts import audit_pipeline_artifacts


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_inputs(root, inventory):
    return [name for name, digest in inventory.items()
            if not (root / name).is_file() or sha(root / name) != digest]


def revision(root):
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, timeout=10)
    return result.stdout.strip() if result.returncode == 0 else None


def aggregate(states):
    states = list(states)
    return "FAIL" if "FAIL" in states else "PASS" if states and all(s == "PASS" for s in states) else "UNKNOWN"


def case_consistency(item):
    """Require successful execution and actual files as well as cached comparisons."""
    return aggregate([item["pipeline"]["status"], item["pipeline"]["process_status"],
                      item["structure_comparison"]["status"], item["artifact_comparison"]["status"],
                      item["full_structure_comparison"]["status"], item["query_comparison"]["status"],
                      item["baseline"]["execution_comparison"],
                      item.get("equivalence_comparison", {"status": "PASS"})["status"]])


def execute(command, cwd, directory, timeout, env):
    directory.mkdir(parents=True, exist_ok=True)
    started = monotonic()
    record = {"command": [str(x) for x in command], "cwd": str(cwd), "returncode": None}
    # Stream to disk so partial logs survive timeouts and interrupted runs.
    with (directory / "stdout.txt").open("w") as stdout, (directory / "stderr.txt").open("w") as stderr:
        try:
            completed = subprocess.run(record["command"], cwd=cwd, env=env, stdout=stdout,
                                       stderr=stderr, timeout=timeout, check=False)
            record["returncode"] = completed.returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            record["error"] = str(error)
    record["runtime_seconds"] = monotonic() - started
    save(directory / "execution.json", record)
    return record


def stage_inputs(root, destination, entries):
    """Preserve relative includes and record hashes of source, headers and oracles."""
    sources = set()
    for entry in entries:
        for field in ("source", "oracle", "explanation", "architecture_oracle", "architecture_explanation"):
            if field in entry:
                sources.add(root / entry[field])
    for folder in ("benchmarks/common", "benchmarks/vendor"):
        sources.update(p for p in (root / folder).rglob("*") if p.is_file())
    inventory = {}
    for source in sorted(sources):
        relative = source.relative_to(root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        original, copied = sha(source), sha(target)
        if original != copied:
            raise ValueError(f"staging hash mismatch: {relative}")
        inventory[relative.as_posix()] = original
    save(destination / "inputs.json", inventory)
    return inventory


def structure(graph, expected=False):
    """Narrow common fields only; never manufacture binding or alias evidence."""
    objects = graph["objects"] if expected else graph["shared_objects"]
    result = {"objects": sorted([
        {"id": o["id"] if expected else o["name"], "initial": o["initial"]} for o in objects
    ], key=lambda o: o["id"]), "threads": []}
    threads = graph["threads"] if expected else graph["thread_contexts"]
    for thread in threads:
        events = thread["events"] if expected else [e for e in graph["events"] if e["thread"] == thread["id"]]
        normalized = []
        for event in events:
            item = {k: event[k] for k in ("kind", "object") if k in event and event[k] is not None}
            item["ordering"] = {"SeqCst": "seq_cst", "AcqRel": "acq_rel"}.get(event["ordering"], event["ordering"].lower())
            if event["kind"] == "Store":
                item["value"] = event["value"]
            normalized.append(item)
        result["threads"].append({"entry": thread["entry"] if expected else thread["entry_function"],
                                  "events": normalized})
    return result


def inspect_pipeline(directory, execution):
    result = {"status": "NOT_RUN", "frontend_status": "NOT_RUN", "reason": execution.get("error", "manifest_missing"),
              "process_status": "UNKNOWN", "herd_attempts": 0}
    try:
        manifest = read(directory / "manifest.json")
        state = manifest["pipeline_status"]
        frontend = manifest.get("frontend", {})
        expected_code = 0 if state in {"PASS", "NO_CANDIDATE"} else 2 if state in {"UNSUPPORTED", "NOT_RUN"} else 1
        result.update(status=state, frontend_status=frontend.get("status", "NOT_RUN"),
                      reason=frontend.get("reason") or manifest.get("reason") or "",
                      herd_attempts=manifest.get("herd_attempts"),
                      process_status="PASS" if execution["returncode"] == expected_code and not execution.get("error") else "FAIL")
        if state not in {"PASS", "NO_CANDIDATE", "UNSUPPORTED", "NOT_RUN", "BOUNDARY"}:
            result["process_status"] = "FAIL"
        for unit in manifest.get("units", []):
            reason = unit["backend"].get("reason")
            if reason:
                result["reason"] += f" {unit['id']}: {reason}"
    except (OSError, ValueError, KeyError, TypeError) as error:
        result["reason"] = execution.get("error") or str(error)
    return result


def compare_structure(directory, oracle):
    path = directory / "frontend/input/event_ir.json"
    if not path.is_file():
        return {"status": "UNKNOWN", "reason": "no_extracted_event_ir"}
    try:
        wanted, actual = structure(oracle, True), structure(read(path))
        return {"status": "PASS" if actual == wanted else "FAIL", "expected": wanted, "actual": actual,
                "scope": "object names/initial values, thread entries and ordered event kind/object/ordering/store-value only"}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"status": "UNKNOWN", "reason": str(error)}


def compare_control(directory, oracle):
    try:
        graph = read(directory / "frontend/input/event_ir.json")
        checks = {"structure": compare_structure(directory, oracle["structure"])}
        units, rows = [], []
        for unit in read(directory / "manifest.json")["units"]:
            vu = read(directory / "frontend/units" / unit["id"] / "verification_unit.json")
            units.append({k: vu[k] for k in ("objects", "event_ids")})
            rows.extend(read(directory / "backend" / unit["id"] / "outcome_matrix.json")["outcomes"])
        for key, actual, wanted in (("program_order", graph["relations"]["program_order"], oracle["program_order"]),
                                    ("units", units, oracle["units"])):
            checks[key] = {"status": "PASS" if actual == wanted else "FAIL", "expected": wanted, "actual": actual}
        actual = [{"outcome": row["outcome"], **{a: row["architectures"][a].get("observation")
                                                for a in ("x86", "riscv")}} for row in rows]
        order = lambda row: json.dumps(row["outcome"], sort_keys=True)
        failed = any(row["architectures"][a]["status"] == "FAILED" for row in rows for a in ("x86", "riscv"))
        ran = bool(rows) and all(row["architectures"][a]["status"] == "RAN"
                                for row in rows for a in ("x86", "riscv"))
        model_status = "FAIL" if failed else "UNKNOWN" if not ran else "PASS" if sorted(actual, key=order) == sorted(oracle["outcomes"], key=order) else "FAIL"
        checks["models"] = {"status": model_status, "expected": oracle["outcomes"], "actual": actual}
        return {"status": aggregate(c["status"] for c in checks.values()), "checks": checks}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"status": "UNKNOWN", "reason": str(error)}


def write_report(output, report):
    save(output / "summary.json", report)
    control = report["control"]
    lines = ["# 内部输入与团队验证流水线集成报告", "",
             f"时间：{report['time_shanghai']}。清单 {len(report['cases'])} 例；SB 正向控制另计。", "",
             f"流程检查：{report['process_status']}；原始输入结果一致性：{report['consistency_status']}。", "",
             f"SB 控制：流水线 {control['pipeline']['status']}；独立结构/VU/模型比较 {control['comparison']['status']}。", "",
             f"输入与团队代码版本检查：{report['input_version_status']}；团队 HEAD：`{report['team_revision']}`。", "",
             "流程 PASS 表示调用、退出码及诊断符合协议；UNSUPPORTED 仍表示覆盖缺口，不能当作结果一致。", "",
             "一致性 PASS 的范围为有界结构与原始输入的指定硬件投影，不表示 C11 或完整程序正确性。", "",
             "| 输入 | 内部执行比较 | 团队前端 | 团队流水线 | 中间产物/原始日志 | 公共字段 | 完整结构/VU | 原始目标模型 | 范围内一致性 |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for case in report["cases"]:
        lines.append(f"| [{case['id']}](cases/{case['id']}/result.json) | {case['baseline']['execution_comparison']} | "
                     f"{case['pipeline']['frontend_status']} | {case['pipeline']['status']} | {case['artifact_comparison']['status']} | "
                     f"{case['structure_comparison']['status']} | {case.get('full_structure_comparison', {}).get('status', 'UNKNOWN')} | "
                     f"{case['query_comparison']['status']} | {case['consistency_status']} |")
    negative = report["p02_without_fences"]
    lines += ["", f"P02 删除 fence 对照：流水线 {negative['pipeline']['status']}，结构 {negative['structure']['status']}，"
              f"中间产物 {negative['artifact_comparison']['status']}，模型目标比较 {negative['comparison']['status']}（两架构预期 Sometimes）。", ""]
    audits = [c["artifact_comparison"] for c in report["cases"]] + [control["artifact_comparison"], negative["artifact_comparison"]]
    lines += [f"本次独立核对 {sum(len(a['sha256']) for a in audits)} 个产物文件，"
              f"从原始日志复核 {sum(u['verified_model_results'] for a in audits for u in a['units'])} 个模型结果。"
              "逐例文件 SHA256、缺失项和差异见 `artifact_comparison.json`。", ""]
    if "benchmark_regions" in report:
        regions = report["benchmark_regions"]
        lines += [f"B02 [独立函数区域证据](benchmark_regions/summary.md)：流程 {regions.get('process_status','UNKNOWN')}，"
                  f"区域比较 {regions.get('region_comparison','UNKNOWN')}，"
                  f"路径 {regions.get('path_count',0)} 条、边界 {regions.get('boundary_paths',0)} 条。"
                  "区域实例由配置指定，尚未执行 main/worker、VU 或 ISA 模型，不改变上表 Benchmark 的 UNSUPPORTED/UNKNOWN。", ""]
    lines += ["", "## 拒绝原因与差异", ""]
    for case in report["cases"]:
        lines.append(f"- {case['id']}：{case['pipeline']['reason'] or '详见该例产物及比较记录'}。")
        for error in case["artifact_comparison"]["errors"]:
            if case["pipeline"]["status"] not in {"UNSUPPORTED", "NOT_RUN"}:
                lines.append(f"  产物 {error['status']}：`{error['path']}`，{error['reason']}。")
        if case["suite"] == "benchmarks" and case.get("capability_report"):
            counts = case["capability_report"]["counts"]
            lines.append(f"  [可达 AST 特征](cases/{case['id']}/pipeline/frontend/input/capability_report.json)："
                         f"函数 {counts['functions']}、循环 {counts['loops']}、分支 {counts['branches']}、CAS 语法点 {counts['cas_sites']}。"
                         "此处含不可行分支的过近似，不能解读为实际运行或模型验证。")
    if report["changed_inputs"] or report["changed_team_code"]:
        lines += ["", f"运行期间发生变化的输入：{report['changed_inputs']}；团队代码：{report['changed_team_code']}。"]
    lines += ["", "## 证据与范围", "",
              "[内部本次三层报告](baseline/summary.md)；[SB 控制比较](control/comparison.json)；[输入哈希](input/inputs.json)。", "",
              "每例保留 staging 原始源码、Oracle、pipeline 产物、stdout/stderr 和执行命令。Benchmark 的相对头文件与 vendor 文件保持原样。", "",
              "C/P 系列完整比较读取团队原生 EventIR/VU，覆盖来源、字段/分配点、绑定、调用、路径假设、切片与关系，并与独立 Oracle 和本次内部基线比较；未调用内部切片器生成团队产物。", "",
              "中间产物检查独立读取 LLVM/编译诊断、前后端交付包、值域枚举、litmus 查询条件/寄存器映射及原始 herd 日志；核对矩阵缓存、命令输入和架构差异汇总。缺失证据为 UNKNOWN，证据矛盾为 FAIL，均不能汇总成一致性 PASS。此检查不构成一般 lowering 等价性证明。", "",
              "模型目标通过 --queries 交给团队后端，含超出写值域的禁止读值；C 系列这里只比较原始源码对应的无注入 fence 目标。C08 另比较两个实际团队 VU 的等价性。", "",
              "B01/B02 尚无完整前端结构 Oracle 和有界路径后端，保持 UNKNOWN；frontend/input/capability_report.json 仅列出可达 AST 特征，不表示路径可行性或程序验证。", "",
              "内部 baseline 的 PASS 表示其声明的执行检查符合预期；架构审查与完整程序结论仍以 baseline 分层状态为准。", ""]
    (output / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-root", type=Path, default=ROOT.parent / "RV-MemoryConsistency-TeamDev")
    parser.add_argument("--out", type=Path, help="fresh path inside team worktree")
    parser.add_argument("--clang")
    parser.add_argument("--herd7")
    parser.add_argument("--x86-model")
    parser.add_argument("--riscv-model")
    parser.add_argument("--backend", choices=("auto", "local", "docker", "none"), default="auto")
    parser.add_argument("--timeout", type=int, default=120, help="per pipeline process seconds")
    args = parser.parse_args(argv)
    team = args.team_root.resolve()
    if not (team / "verification_pipeline/__main__.py").is_file():
        parser.error("team-root does not contain verification_pipeline")
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    output = (args.out or team / ".case-regression-runs" / now.strftime("%Y%m%dT%H%M%S%f")).resolve()
    if not output.is_relative_to(team) or output.exists():
        parser.error("out must be a fresh path inside the team worktree")
    catalog_path = ROOT / "correctness_manifest.json"
    catalog = read(catalog_path)
    entries = catalog["cases"]
    fixed = {e["id"] for e in read(ROOT / "tests/internal_manifest.json")["cases"]} | {
        "P01_pthread_sb", "P02_atomic_fence", "P03_release_acquire_relay", "B01_spsc_ring", "B02_spinlock"}
    if catalog.get("schema") != "correctness-catalog-1" or len(entries) != len(fixed) or {e["id"] for e in entries} != fixed:
        parser.error("catalog must include all thirteen unique inputs")
    local_clang = ROOT.parent / ".tools/clang18/bin/clang"
    clang = find_tool("clang", args.clang or os.getenv("PROTOTYPE_CLANG") or (str(local_clang) if local_clang.is_file() else None))
    herd = find_tool("herd7", args.herd7 or os.getenv("PROTOTYPE_HERD7"))
    models = {a: find_model(herd, a, getattr(args, f"{a}_model") or os.getenv(f"PROTOTYPE_{a.upper()}_MODEL"))
              for a in ("x86", "riscv")}
    env = os.environ.copy()
    for key, value in {"PROTOTYPE_CLANG": clang, "PROTOTYPE_HERD7": herd,
                       **{f"PROTOTYPE_{a.upper()}_MODEL": p for a, p in models.items()}}.items():
        if value:
            env[key] = str(value)
    output.mkdir(parents=True)
    inventory = stage_inputs(ROOT, output / "input", entries)
    save(output / "catalog.json", catalog)
    team_inventory = {p.relative_to(team).as_posix(): sha(p) for folder in ("verification_pipeline", "src")
                      for p in (team / folder).rglob("*.py")}
    internal_inventory = {p.relative_to(ROOT).as_posix(): sha(p) for folder in ("scripts", "prototype", "tests/team_pipeline")
                          for p in (ROOT / folder).rglob("*") if p.is_file() and (p.suffix in {".py", ".sh", ".c", ".json"})}
    provenance = {"team_revision": revision(team), "internal_revision": revision(ROOT),
                  "runner_sha256": sha(Path(__file__)), "catalog_sha256": sha(catalog_path),
                  "team_code_sha256": team_inventory,
                  "internal_code_sha256": internal_inventory,
                  "tools": {"python": sys.version, "clang": clang, "herd7": herd,
                            "models": {a: {"path": str(p), "sha256": sha(p)} if p and p.is_file() else None
                                       for a, p in models.items()}}}
    save(output / "provenance.json", provenance)
    pipeline_args = ["--backend", args.backend, "--clang", clang or "clang"]
    if herd:
        pipeline_args += ["--herd7", herd]
    for arch, model in models.items():
        if model:
            pipeline_args += [f"--{arch}-model", str(model)]

    def run(source, directory, seeds=None, specs=None, semantics="hardware-projection"):
        directory.mkdir(parents=True, exist_ok=True)
        extra = ["--semantics", semantics]
        for seed in seeds or []:
            extra += ["--seed-object", seed]
        if specs is not None:
            save(directory / "queries.json", [{"id": s["id"], "event_values": s["event_values"]} for s in specs])
            extra += ["--queries", str(directory / "queries.json")]
        record = execute([sys.executable, "-m", "verification_pipeline", "--source", source,
                          "--out", directory / "pipeline", *pipeline_args, *extra], team, directory / "logs", args.timeout, env)
        return inspect_pipeline(directory / "pipeline", record)

    def audit(directory):
        result = audit_pipeline_artifacts(directory / "pipeline")
        save(directory / "artifact_comparison.json", result)
        return result

    cases = []
    for entry in entries:
        print(f"Team pipeline: {entry['id']}", flush=True)
        directory = output / "cases" / entry["id"]
        oracle = read(output / "input" / entry["oracle"])
        specs = query_specs(entry, oracle, output / "input") if entry["suite"] != "benchmarks" else None
        state = run(output / "input" / entry["source"], directory, oracle.get("seed_objects"), specs)
        comparison = ({"status": "UNKNOWN", "reason": "no_frontend_structure_oracle_for_benchmark"}
                      if entry["suite"] == "benchmarks" else compare_structure(directory / "pipeline", read(output / "input" / entry["oracle"])))
        item = {"id": entry["id"], "suite": entry["suite"], "pipeline": state,
                "source_sha256": inventory[entry["source"]], "structure_comparison": comparison,
                "artifact_comparison": audit(directory),
                "query_comparison": compare_queries(directory / "pipeline", specs) if specs is not None else {"status": "UNKNOWN", "reason": "benchmark_frontend_not_integrated"},
                "consistency_status": "FAIL" if comparison["status"] == "FAIL" else "UNKNOWN"}
        capability_path = directory / "pipeline/frontend/input/capability_report.json"
        if capability_path.is_file():
            item["capability_report"] = read(capability_path)
        save(directory / "result.json", item)
        cases.append(item)
        print(f"  {state['status']}: {state['reason']}", flush=True)

    print("Team pipeline: independent relaxed SB control", flush=True)
    control_dir = output / "control"
    control_dir.mkdir()
    for name in ("sb.c", "sb.expected.json"):
        shutil.copyfile(ROOT / "tests/team_pipeline" / name, control_dir / name)
    control = {"pipeline": run(control_dir / "sb.c", control_dir, semantics="atomic")}
    control["input_sha256"] = {name: sha(control_dir / name) for name in ("sb.c", "sb.expected.json")}
    control["comparison"] = compare_control(control_dir / "pipeline", read(control_dir / "sb.expected.json"))
    control["artifact_comparison"] = audit(control_dir)
    control["comparison"]["status"] = aggregate([control["comparison"]["status"], control["artifact_comparison"]["status"], control["pipeline"]["status"]])
    save(control_dir / "comparison.json", control["comparison"])

    # Run the actual team compiler/lowering/model path for the fence-deletion
    # control. The original source and Oracle remain byte-for-byte unchanged.
    from copy import deepcopy
    p02_entry = next(e for e in entries if e["id"] == "P02_atomic_fence")
    negative_oracle = deepcopy(read(output / "input" / p02_entry["oracle"]))
    for thread in negative_oracle["threads"]:
        thread["events"] = [e for e in thread["events"] if e["kind"] != "Fence"]
    negative_oracle["expected_observations"] = {a: "Sometimes" for a in ("x86", "riscv")}
    negative_dir = output / "p02_without_fences"
    negative_dir.mkdir()
    original = output / "input" / p02_entry["source"]
    (negative_dir / "case.c").write_text("\n".join(line for line in original.read_text().splitlines()
        if "atomic_thread_fence(" not in line) + "\n")
    negative_specs = query_specs(p02_entry, negative_oracle, output / "input")
    negative = {"scope": "derived fence deletion control; not the original input",
                "original_sha256": sha(original), "derived_sha256": sha(negative_dir / "case.c"),
                "pipeline": run(negative_dir / "case.c", negative_dir, negative_oracle["seed_objects"], negative_specs)}
    negative["comparison"] = compare_queries(negative_dir / "pipeline", negative_specs)
    negative["structure"] = compare_structure(negative_dir / "pipeline", negative_oracle)
    negative["artifact_comparison"] = audit(negative_dir)
    negative["comparison"]["status"] = aggregate([negative["comparison"]["status"], negative["artifact_comparison"]["status"], negative["pipeline"]["status"]])
    save(negative_dir / "comparison.json", negative)

    print("Team bounded regions: original B02 lock/startup functions (separate evidence layer)", flush=True)
    region_execution = execute([sys.executable, ROOT / "scripts/run_benchmark_regions.py", "--team-root",team,
                                "--out",output / "benchmark_regions","--clang",clang or "clang"],
                               ROOT,output / "benchmark_region_logs",args.timeout,env)
    try:
        benchmark_regions = read(output / "benchmark_regions/summary.json")
    except (OSError, ValueError):
        benchmark_regions = {"process_status":"UNKNOWN","region_comparison":"UNKNOWN","reason":"region_summary_missing"}
    region_process = aggregate([benchmark_regions["process_status"],benchmark_regions["region_comparison"]]) if region_execution["returncode"] == 2 else "FAIL"

    print("Internal baseline: fresh structure/prototype/benchmark/architecture checks", flush=True)
    baseline_execution = execute([sys.executable, ROOT / "scripts/run_correctness.py", "--out", output / "baseline"],
                                 ROOT, output / "baseline_logs", 900, env)
    try:
        baseline = read(output / "baseline/summary.json")
    except (OSError, ValueError):
        baseline = {}
    by_id = {row["case"]: row for row in baseline.get("cases", [])}
    for item in cases:
        item["baseline"] = by_id.get(item["id"], {"execution_comparison": "UNKNOWN", "reason": "baseline_result_missing"})
        entry = next(e for e in entries if e["id"] == item["id"])
        if entry["suite"] != "benchmarks":
            suite_dir = "internal" if entry["suite"] == "internal" else "prototype"
            item["full_structure_comparison"] = compare_full(output / "cases" / item["id"] / "pipeline",
                read(output / "input" / entry["oracle"]), output / "baseline" / suite_dir / item["id"])
            item["consistency_scope"] = "bounded structure and original-source targeted hardware projections; not C11 or whole-program correctness"
            oracle = read(output / "input" / entry["oracle"])
            reference = oracle.get("equivalent_unit_to")
            if reference:
                ref_entry = next(e for e in entries if e["id"] == reference)
                item["equivalence_comparison"] = compare_equivalence(output / "cases" / item["id"] / "pipeline", oracle,
                    output / "cases" / reference / "pipeline", read(output / "input" / ref_entry["oracle"]))
            item["consistency_status"] = case_consistency(item)
        save(output / "cases" / item["id"] / "result.json", item)
    process_states = [c["pipeline"]["process_status"] for c in cases] + [control["pipeline"]["process_status"], control["comparison"]["status"],
        negative["pipeline"]["process_status"], negative["comparison"]["status"], negative["structure"]["status"],region_process]
    baseline_status = baseline.get("execution_comparison_status", "UNKNOWN")
    baseline_rc = {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[baseline_status]
    process_states += [baseline_status if baseline_execution["returncode"] == baseline_rc else "UNKNOWN"]
    input_changes = changed_inputs(ROOT, {**inventory, **internal_inventory})
    team_changes = changed_inputs(team, team_inventory)
    input_version_status = "UNKNOWN" if input_changes or team_changes or sha(catalog_path) != provenance["catalog_sha256"] else "PASS"
    process_states.append(input_version_status)
    report = {"schema": "team-pipeline-integration-1", "time_shanghai": now.isoformat(), "team_root": str(team),
              "catalog_sha256": provenance["catalog_sha256"], "team_revision": provenance["team_revision"],
              "input_version_status": input_version_status, "changed_inputs": input_changes, "changed_team_code": team_changes,
              "control": control, "p02_without_fences": negative, "baseline_execution": baseline_execution,
              "benchmark_regions":benchmark_regions,"benchmark_region_execution":region_execution,
              "process_status": aggregate(process_states), "consistency_status": aggregate(c["consistency_status"] for c in cases),
              "counts": dict(Counter(c["pipeline"]["status"] for c in cases)), "cases": cases}
    write_report(output, report)
    print(f"Process {report['process_status']}; consistency {report['consistency_status']}: {output / 'summary.md'}", flush=True)
    return 1 if "FAIL" in (report["process_status"], report["consistency_status"]) else 0 if report["process_status"] == report["consistency_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
