#!/usr/bin/env python3
"""Run or collect the fixed case catalog; report the three oracle layers separately."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks/scripts"))
from oracle_contract import aggregate
from benchmark_evidence import validate_benchmark_evidence
from run_suite import publish_latest
from prototype.architecture import validate_evidence as validate_architecture_evidence
from prototype.architecture import publish_latest as publish_architecture_latest


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unknown(reason):
    return {"status": "UNKNOWN", "reason": reason,
            "next_action": "按场景声明范围补齐对应依据或本次证据后重新检查；不从其他层的 PASS 推断。"}


def collect_case(root, entry, directory, architecture_directory=None):
    case, suite = entry["id"], entry["suite"]
    result_path = directory / case / "result.json"
    item = {"case": case, "suite": suite, "requirement": entry["requirement"],
            "explanation": str(root / entry["explanation"]), "result": str(result_path),
            "evidence": unknown("result_missing"), "execution_comparison": "UNKNOWN",
            "layers": {"structure": unknown("not_run"), "behavior": unknown("no_behavior_oracle"),
                       "architecture": {"comparison_status": "UNKNOWN", "conclusion_status": "UNKNOWN",
                                        "review_status": "UNKNOWN", "reason": "no_reviewed_model_oracle",
                                        "next_action": "若建立架构验证目标，先独立定义投影、允许结果与依据，再完成审查。"}}}
    try:
        result = json.loads(result_path.read_text())
        if not isinstance(result, dict):
            raise ValueError("invalid_result_document")
        item["result_sha256"] = sha(result_path)
        for key in ("source", "oracle", "explanation"):
            if not (root / entry[key]).is_file():
                raise ValueError(f"catalog_input_missing:{entry[key]}")
        if suite == "benchmarks":
            result = validate_benchmark_evidence(root / "benchmarks", case, directory)
            item["evidence"] = result["evidence_validation"]
            item["layers"] = result["correctness"]["layers"]
            item["obligations"] = result["correctness"]["obligations"]
            item["full_program"] = result["correctness"]["full_program"]
            item["execution_comparison"] = aggregate([result["native_status"], result["projection_status"]])
            if case == "B02_spinlock":
                item["execution_comparison"] = aggregate([
                    item["execution_comparison"], result.get("protocol_status", "UNKNOWN")])
        else:
            if result.get("case") != case:
                raise ValueError("result_case_mismatch")
            provenance = result.get("provenance", {})
            if provenance.get("source_sha256") != sha(root / entry["source"]):
                raise ValueError("stale_source")
            if provenance.get("oracle_sha256") != sha(root / entry["oracle"]):
                raise ValueError("stale_oracle")
            for filename, digest in result.get("artifacts", {}).items():
                if sha(result_path.parent / filename) != digest:
                    raise ValueError(f"artifact_hash_mismatch:{filename}")
            if suite == "internal":
                item["layers"]["structure"] = {"status": result["status"], "scope": result["scope"]}
                item["layers"]["behavior"] = unknown("structure_only_case_no_program_behavior_claim")
            else:
                if provenance.get("llvm_ir_sha256") and sha(result_path.parent / "source.ll") != provenance["llvm_ir_sha256"]:
                    raise ValueError("artifact_hash_mismatch:source.ll")
                item["layers"]["structure"] = result["structure"]
                checks = result.get("verification", {})
                architecture = item["layers"]["architecture"]
                architecture.update(comparison_status=aggregate(checks.get(a, {}).get("status", "UNKNOWN")
                                                               for a in ("x86", "riscv")),
                                    observations=checks, scope=result["scope"],
                                    next_action="独立审查语言前提、硬件映射及目标条件；既有原型只记录顶层模型哈希。")
            item["execution_comparison"] = result["status"]
            if suite == "internal" and architecture_directory is not None:
                try:
                    evidence = validate_architecture_evidence(root / Path(entry["source"]).parent,
                                                             architecture_directory / case)
                    item["architecture_result"] = str(architecture_directory / case / "result.json")
                    item["layers"]["architecture"] = {
                        "comparison_status": evidence["comparison_status"],
                        "conclusion_status": evidence["conclusion_status"],
                        "review_status": evidence["review_status"], "scope": evidence["scope"],
                        "queries": evidence["queries"], "c_program_correctness": "UNKNOWN",
                        "next_action": "审查独立architecture.json的目标、映射及模型闭包；不由比较PASS确认原始C程序。"}
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    item["layers"]["architecture"]["reason"] = str(exc)
                item["execution_comparison"] = aggregate([
                    item["execution_comparison"], item["layers"]["architecture"]["comparison_status"]])
        if suite != "benchmarks":
            item["evidence"] = {"status": "PASS", "scope": "recorded_input_hashes_match_current_inputs"}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        item["evidence"] = unknown(str(exc))
        item["execution_comparison"] = "UNKNOWN"
        item["layers"] = {"structure": unknown("evidence_unavailable_or_stale"),
                          "behavior": unknown("evidence_unavailable_or_stale"),
                          "architecture": {"comparison_status": "UNKNOWN", "conclusion_status": "UNKNOWN",
                                           "review_status": "UNKNOWN", "reason": "evidence_unavailable_or_stale",
                                           "next_action": "补齐当前版本的输入与结果，使用空目录重新执行对应验证。"}}
    return item


def write_report(root, output, directories, executions):
    catalog_path = root / "correctness_manifest.json"
    catalog = json.loads(catalog_path.read_text())
    entries = catalog["cases"]
    ids = [e["id"] for e in entries]
    if catalog.get("schema") != "correctness-catalog-1" or not ids or len(ids) != len(set(ids)):
        raise ValueError("invalid or empty correctness catalog")
    # A shortened catalog must not silently omit a required internal case.
    internal = json.loads((root / "tests/internal_manifest.json").read_text())
    if {e["id"] for e in entries if e["suite"] == "internal"} != {e["id"] for e in internal["cases"]}:
        raise ValueError("correctness catalog differs from internal manifest")
    if {e["id"] for e in entries if e["suite"] == "prototype"} != {
        "P01_pthread_sb", "P02_atomic_fence", "P03_release_acquire_relay"}:
        raise ValueError("correctness catalog must include all three prototype cases")
    if {e["id"] for e in entries if e["suite"] == "benchmarks"} != {"B01_spsc_ring", "B02_spinlock"}:
        raise ValueError("correctness catalog must include both engineering benchmarks")
    cases = [collect_case(root, e, directories[e["suite"]], directories.get("architecture")) for e in entries]
    catalog_inputs = {}
    for e in entries:
        for key in ("source", "oracle", "explanation", "architecture_oracle", "architecture_explanation"):
            if key not in e:
                continue
            path = root / e[key]
            catalog_inputs[e[key]] = sha(path) if path.is_file() else None
    states = [c["execution_comparison"] for c in cases]
    states += [e["status"] for e in executions]
    report = {"schema": "three-layer-correctness-run-1",
              "time_shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "scope": "execution comparisons and separately recorded oracle layers",
              "execution_comparison_status": aggregate(states),
              "architecture_conclusion_status": aggregate(c["layers"]["architecture"]["conclusion_status"] for c in cases),
              "catalog_sha256": sha(catalog_path), "executions": executions, "cases": cases,
              "catalog_inputs": catalog_inputs}
    report["counts"] = {
        "cases": len(cases),
        "execution_comparison": {s: sum(c["execution_comparison"] == s for c in cases)
                                 for s in ("PASS", "FAIL", "UNKNOWN")},
        "structure": {s: sum(c["layers"]["structure"]["status"] == s for c in cases)
                      for s in ("PASS", "FAIL", "UNKNOWN")}}
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    lines = ["# 三层正确性验证报告", "", "## 验证范围", "",
             f"本次时间：{report['time_shanghai']}；固定清单共 {len(cases)} 例。", "",
             f"执行比较：{report['execution_comparison_status']}；架构结论：{report['architecture_conclusion_status']}。", "",
             "执行比较 PASS 表示本次检查符合预期；完整程序正确性及正式审查按各层状态记录。", ""]
    for c in cases:
        layers = c["layers"]
        behavior = layers["behavior"].get("basis_status", layers["behavior"].get("status", "UNKNOWN"))
        explanation_link = Path(os.path.relpath(c['explanation'], output)).as_posix()
        result_link = Path(os.path.relpath(c['result'], output)).as_posix()
        lines += [f"## {c['case']}", "",
                  f"要求：{c['requirement']}。", "",
                  f"- 证据：{c['evidence']['status']}；执行比较：{c['execution_comparison']}；结构：{layers['structure']['status']}；行为依据：{behavior}。",
                  f"- 架构比较：{layers['architecture']['comparison_status']}；架构审查：{layers['architecture']['review_status']}；架构结论：{layers['architecture']['conclusion_status']}。", "",
                  f"[场景依据]({explanation_link})；[分项证据]({result_link})。", ""]
        if c["evidence"]["status"] != "PASS":
            lines.extend(["证据问题：" + c["evidence"]["reason"] + "。", ""])
        if "bounded_protocol_comparison" in layers["behavior"]:
            lines.extend(["手工有限 SC 协议及错误对照比较：" + layers["behavior"]["bounded_protocol_comparison"]
                          + "；完整程序验证仍为 UNKNOWN，详见 Benchmark 分项报告。", ""])
        if c.get("architecture_result"):
            architecture_link = Path(os.path.relpath(c["architecture_result"], output)).as_posix()
            lines.extend([f"[C 系列架构查询证据]({architecture_link})；硬件投影不等于原始 C 正确性。", ""])
    lines += ["## 验收与后续工作", "",
              "本次完成标准是要求、依据、检查和缺口逐项可追溯。下一步依据各例 `next_action` 推进评审及完整语义验证。", ""]
    (output / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="fresh output directory")
    parser.add_argument("--collect", action="store_true", help="collect existing evidence without running suites")
    for suite in ("internal", "prototype", "benchmarks"):
        parser.add_argument(f"--{suite}", type=Path, help="existing suite output (with --collect)")
    parser.add_argument("--architecture", type=Path, help="existing C architecture evidence (optional with --collect)")
    args = parser.parse_args()
    if args.collect and not all(getattr(args, s) for s in ("internal", "prototype", "benchmarks")):
        parser.error("--collect requires --internal, --prototype and --benchmarks")
    if not args.collect and any(getattr(args, s) for s in ("internal", "prototype", "benchmarks", "architecture")):
        parser.error("existing suite paths require --collect")
    output = (args.out or ROOT / "results/correctness" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("output must be a fresh directory")
    output.mkdir(parents=True, exist_ok=True)
    executions, directories = [], {}
    for suite, script in (("internal", "scripts/run_internal_regression.sh"),
                          ("prototype", "scripts/run_prototype.sh"), ("benchmarks", "benchmarks/run.sh"),
                          ("architecture", "scripts/run_c_architecture.sh")):
        if args.collect and suite == "architecture" and args.architecture is None:
            continue
        directories[suite] = getattr(args, suite).resolve() if args.collect else output / suite
        if args.collect:
            continue
        command = ["bash", str(ROOT / script), "--out", str(directories[suite])]
        if suite == "architecture":
            command += ["--internal", str(directories["internal"])]
        print(f"Running {suite} ...", flush=True)
        try:
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
            (output / f"{suite}.stdout.txt").write_text(completed.stdout)
            (output / f"{suite}.stderr.txt").write_text(completed.stderr)
            executions.append({"suite": suite, "command": command, "returncode": completed.returncode,
                               "status": {0: "PASS", 1: "FAIL", 2: "UNKNOWN"}.get(completed.returncode, "UNKNOWN")})
        except (OSError, subprocess.TimeoutExpired) as exc:
            decode = lambda value: value.decode(errors="replace") if isinstance(value, bytes) else value or ""
            (output / f"{suite}.stdout.txt").write_text(decode(getattr(exc, "stdout", None)))
            (output / f"{suite}.stderr.txt").write_text(decode(getattr(exc, "stderr", None)) or str(exc))
            executions.append({"suite": suite, "command": command, "status": "UNKNOWN", "reason": str(exc)})
    report = write_report(ROOT, output, directories, executions)
    if not args.out:
        (output.parent / "latest.json").write_text(json.dumps({"summary": str(output / "summary.json")}, indent=2) + "\n")
        (output.parent / "summary.md").write_text(
            f"# 三层正确性验证最近报告\n\n"
            f"[本次报告]({output.name}/summary.md)；执行比较：{report['execution_comparison_status']}；架构结论：{report['architecture_conclusion_status']}。\n",
            encoding="utf-8")
        benchmark_output = directories["benchmarks"]
        if not args.collect and (benchmark_output / "summary.json").is_file():
            publish_latest(benchmark_output, ROOT / "results/benchmarks")
        architecture_output = directories.get("architecture")
        if not args.collect and architecture_output and (architecture_output / "summary.json").is_file():
            publish_architecture_latest(architecture_output)
    print(f"{report['execution_comparison_status']}: {output / 'summary.md'}")
    return {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[report["execution_comparison_status"]]


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
