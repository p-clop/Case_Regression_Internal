#!/usr/bin/env python3
"""Build/run two independent benchmarks and the declared hardware projections."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

from check_sources import verify
from fifo_oracle import check_trace
from record_oracle import check_trace as check_record_trace
from make_models import models
from oracle_contract import aggregate, attach_correctness, input_snapshot, subject_hash, validate_contract
from benchmark_evidence import seal_benchmark_evidence, validate_benchmark_evidence

ROOT = Path(__file__).resolve().parents[1]
CASES = ("B01_spsc_ring", "B02_spinlock")
MATRIX = {
    "B01_spsc_ring": [
        ("single_slot", ["--size", "2", "--batch", "1", "--iterations", "20000"]),
        ("batched", ["--size", "8", "--batch", "5", "--iterations", "100000"]),
        ("index_overflow", ["--size", "8", "--batch", "7", "--iterations", "100000",
                            "--initial-index", "4294967280"]),
        ("larger_ring", ["--size", "64", "--batch", "8", "--iterations", "50000"]),
    ],
    "B02_spinlock": [
        ("contention", ["--iterations", "100000", "--yield-every", "64"]),
        ("no_yield", ["--iterations", "20000", "--yield-every", "0"]),
    ],
}
INVALID = {
    "B01_spsc_ring": [["--size", "3"], ["--size", "8", "--batch", "8"]],
    "B02_spinlock": [["--iterations", "0"]],
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def publish_latest(output, top):
    """Point both entry files at a completed standalone or unified run report."""
    output, top = output.resolve(), top.resolve()
    summary = json.loads((output / "summary.json").read_text())
    report_link = Path(os.path.relpath(output / "summary.md", top)).as_posix()
    write_json(top / "latest.json", {"run_id": summary["run_id"],
                                     "summary": str(output / "summary.json")})
    (top / "summary.md").write_text(
        f"# Benchmark 最近执行报告\n\n"
        f"比较结果：{summary['status']}；[本次报告]({report_link})。\n\n"
        f"原生执行 {summary['native_executions']} 次，模型调用 {summary['model_executions']} 次。\n\n"
        f"完整程序模型验证：{summary['full_program_model_verification']}；"
        f"架构 Oracle 审查：{summary['architecture_oracle_review']}。\n", encoding="utf-8")


def execute(command, directory, label, timeout, env=None):
    started = time.monotonic()
    result = {"command": [str(x) for x in command], "cwd": str(ROOT), "reason": None}
    try:
        completed = subprocess.run(result["command"], cwd=ROOT, env=env,
                                   capture_output=True, text=True, timeout=timeout)
        result.update(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
    except subprocess.TimeoutExpired as exc:
        decode = lambda x: x.decode(errors="replace") if isinstance(x, bytes) else (x or "")
        result.update(returncode=None, stdout=decode(exc.stdout), stderr=decode(exc.stderr), reason="timeout")
    except OSError as exc:
        result.update(returncode=None, stdout="", stderr=str(exc), reason="execution_unavailable")
    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{label}.stdout.txt").write_text(result.pop("stdout"))
    (directory / f"{label}.stderr.txt").write_text(result.pop("stderr"))
    result["stdout_log"] = str(directory / f"{label}.stdout.txt")
    result["stderr_log"] = str(directory / f"{label}.stderr.txt")
    return result


def native_result(execution, case, expected, args):
    actual = None
    fifo_check = None
    record_check = None
    errors = []
    stdout = Path(execution["stdout_log"]).read_text()
    if expected.get("status"):
        try:
            actual = json.loads(stdout)
        except (ValueError, TypeError):
            errors.append("missing or invalid JSON observation")
    if execution["returncode"] != expected["returncode"]:
        errors.append(f"returncode: expected {expected['returncode']}, actual {execution['returncode']}")
    if expected.get("status") and (not isinstance(actual, dict) or actual.get("status") != expected["status"]):
        errors.append("observation does not match independently declared expected status")
    if expected.get("status") == "PASS" and isinstance(actual, dict):
        options = dict(zip(args[::2], args[1::2]))
        n = int(options.get("--iterations", "100000"))
        if actual.get("case") != case or actual.get("preflight") is not True:
            errors.append("wrong case or missing boundary checks")
        if case == "B01_spsc_ring":
            final = (int(options.get("--initial-index", "0")) + n) % (2**32)
            if actual.get("produced") != n or actual.get("consumed") != n or actual.get("final_index") != final:
                errors.append("queue counts or unsigned final index differ from run parameters")
            if actual.get("final_indexes") != [final] * 4:
                errors.append("one or more final queue indexes differ from expectation")
            trace_path = options.get("--trace")
            fifo_check = (check_trace(trace_path, n) if trace_path else
                          {"status": "UNKNOWN", "reason": "missing_consumer_trace"})
            if fifo_check["status"] == "FAIL":
                errors.append("independent FIFO trace check failed")
        else:
            if actual.get("completed") != [n, n] or actual.get("final_count") != 2*n or actual.get("errors") != [0, 0]:
                errors.append("protected update counts or errors differ from expectation")
            checksum = ((2*n * 11400714819323198485) % (2**64)) ^ 0x5a5aa5a5deadcafe
            if actual.get("checksum") != checksum or actual.get("locked") != 0:
                errors.append("protected checksum or final lock state differs from expectation")
            trace_path = options.get("--trace")
            record_check = (check_record_trace(trace_path, n) if trace_path else
                            {"status": "UNKNOWN", "reason": "missing_update_trace"})
            if record_check["status"] == "FAIL":
                errors.append("independent update trace check failed")
    status = "UNKNOWN" if execution["reason"] else ("FAIL" if errors else "PASS")
    if status == "PASS" and any(check and check["status"] == "UNKNOWN"
                                for check in (fifo_check, record_check)):
        status = "UNKNOWN"
    result = {**execution, "status": status, "expected": expected, "actual": actual, "errors": errors}
    if fifo_check is not None:
        result["fifo_check"] = fifo_check
    if record_check is not None:
        result["record_check"] = record_check
    return result


def discover_herd(explicit):
    if explicit:
        resolved = shutil.which(explicit) or explicit
        return str(Path(resolved).resolve()) if os.access(resolved, os.X_OK) else None
    candidates = [explicit, os.environ.get("PROTOTYPE_HERD7"), shutil.which("herd7")]
    candidates += sorted((Path.home() / ".opam").glob("*/bin/herd7"))
    return next((str(Path(x).resolve()) for x in candidates if x and os.access(x, os.X_OK)), None)


def model_hashes(path):
    """Hash the referenced CAT include closure, not only its top-level file."""
    result = {}
    pending = [Path(path)]
    while pending:
        current = pending.pop().resolve()
        if str(current) in result:
            continue
        result[str(current)] = sha(current)
        for name in re.findall(r'\binclude\s+"([^"]+)"', current.read_text()):
            included = current.parent / name
            if included.exists():
                pending.append(included)
            else:
                raise ValueError(f"CAT include missing: {included}")
    return result


def run(args):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = (Path(args.out).resolve() if args.out else ROOT.parent / "results/benchmarks" / run_id)
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output must be a fresh directory (old evidence is preserved): {output}")
    output.mkdir(parents=True, exist_ok=True)
    summary = {"schema": "engineering-benchmark-run-2", "run_id": run_id,
               "time_shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
               "scope": "source fidelity, native bounded workloads, declared hardware projections",
               "platform": platform.platform(), "architecture": platform.machine(),
               "full_program_model_verification": "UNKNOWN",
               "architecture_oracle_review": "UNKNOWN", "output": str(output),
               "compilers": [], "cases": {}, "source_integrity": {}}
    try:
        summary["source_integrity"] = verify()
        for name, expected in models():
            if (ROOT / name).read_text() != expected:
                raise ValueError(f"declared projection differs from its renderer: {name}")
    except (OSError, ValueError) as exc:
        summary["source_integrity"] = {"status": "FAIL", "reason": str(exc)}
        summary["status"] = "FAIL"
        write_json(output / "summary.json", summary)
        print(str(exc), file=sys.stderr)
        return 1
    try:
        oracles = {case: validate_contract(ROOT, case) for case in CASES}
        summary["oracle_contract"] = {"status": "PASS", "obligations": sum(
            len(o["obligations"]) for o in oracles.values())}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        summary["oracle_contract"] = {"status": "UNKNOWN", "reason": str(exc)}
        summary["status"] = "UNKNOWN"
        write_json(output / "summary.json", summary)
        print(str(exc), file=sys.stderr)
        return 2
    snapshot = input_snapshot(ROOT)
    subject = subject_hash(snapshot)
    summary["review_subject_sha256"] = subject
    write_json(output / "inputs.json", snapshot)
    compilers = args.compiler or [shutil.which("gcc") or shutil.which("cc")]
    local_clang = ROOT.parent.parent / ".tools/clang18/bin/clang"
    if not args.compiler and (local_clang.exists() or shutil.which("clang")):
        compilers.append(str(local_clang) if local_clang.exists() else shutil.which("clang"))
    compilers = [x for x in compilers if x]
    for case in CASES:
        summary["cases"][case] = {"native": [], "builds": [], "projections": [],
                                  "oracle_sha256": sha(ROOT / case / "oracle.json")}
    if not compilers:
        summary["native_reason"] = "no_compiler_available"
    for number, compiler in enumerate(compilers):
        compiler = shutil.which(compiler) or compiler
        compiler_id = f"cc{number}"
        version = execute([compiler, "--version"], output / "environment", compiler_id, args.timeout)
        summary["compilers"].append({"id": compiler_id, "executable": compiler, **version})
        if version["returncode"] != 0:
            for case in CASES:
                summary["cases"][case]["builds"].append({**version, "status": "UNKNOWN",
                    "reason": "compiler_unavailable", "compiler": compiler_id})
            print(f"{compiler_id}: compiler unavailable; native checks UNKNOWN", flush=True)
            continue
        for case in CASES:
            oracle = oracles[case]
            record = summary["cases"][case]
            for opt in ("-O0", "-O2"):
                directory = output / case / f"{compiler_id}_{opt[1:]}"
                binary = directory / "bin/benchmark"
                env = {**os.environ, "CC": compiler, "BENCH_OPT": opt, "BENCH_INJECT_CORRUPTION": "0"}
                build = execute(["bash", ROOT / case / "build.sh", binary], directory, "build", args.timeout, env)
                build["build_environment"] = {key: env[key] for key in ("CC", "BENCH_OPT", "BENCH_INJECT_CORRUPTION")}
                build.update(compiler=compiler_id, optimization=opt, kind="baseline")
                build["status"] = "UNKNOWN" if build["reason"] else ("PASS" if build["returncode"] == 0 else "FAIL")
                record["builds"].append(build)
                if build["status"] != "PASS":
                    continue
                build["binary_sha256"] = sha(binary)
                for label, parameters in MATRIX[case]:
                    if case == "B01_spsc_ring":
                        parameters = [*parameters, "--trace", str(directory / f"{label}.messages.jsonl")]
                    elif case == "B02_spinlock":
                        parameters = [*parameters, "--trace", str(directory / f"{label}.updates.jsonl")]
                    execution = execute([binary, *parameters], directory, label, args.timeout)
                    result = native_result(execution, case, oracle["native"]["baseline"], parameters)
                    result.update(label=label, compiler=compiler_id, optimization=opt, kind="baseline")
                    record["native"].append(result)
                if opt == "-O2":
                    for i, parameters in enumerate(INVALID[case]):
                        execution = execute([binary, *parameters], directory, f"invalid_{i}", args.timeout)
                        result = native_result(execution, case, oracle["native"]["invalid_configuration"], parameters)
                        result.update(label=f"invalid_{i}", compiler=compiler_id, optimization=opt, kind="invalid_configuration")
                        record["native"].append(result)
                    negative_binary = directory / "bin/checker_corruption"
                    env["BENCH_INJECT_CORRUPTION"] = "1"
                    build = execute(["bash", ROOT / case / "build.sh", negative_binary], directory,
                                    "build_checker_corruption", args.timeout, env)
                    build["build_environment"] = {key: env[key] for key in ("CC", "BENCH_OPT", "BENCH_INJECT_CORRUPTION")}
                    build.update(compiler=compiler_id, optimization=opt, kind="checker_control")
                    build["status"] = "UNKNOWN" if build["reason"] else ("PASS" if build["returncode"] == 0 else "FAIL")
                    record["builds"].append(build)
                    if build["status"] == "PASS":
                        build["binary_sha256"] = sha(negative_binary)
                        execution = execute([negative_binary, "--iterations", "1000"], directory,
                                            "checker_corruption", args.timeout)
                        result = native_result(execution, case, oracle["native"]["checker_corruption"], ["--iterations", "1000"])
                        result.update(label="checker_corruption", compiler=compiler_id, optimization=opt, kind="checker_control")
                        record["native"].append(result)
            print(f"{case}: {compiler_id} native checks recorded", flush=True)
    herd = discover_herd(args.herd7)
    model_dir = Path(herd).parent.parent / "share/herdtools7/herd" if herd else None
    summary["herd7"] = {"executable": herd}
    if herd and not args.no_models:
        summary["herd7"]["version"] = execute([herd, "-version"], output / "environment", "herd7", args.timeout)
    for case in CASES:
        oracle = oracles[case]
        record = summary["cases"][case]
        if case == "B02_spinlock":
            execution = execute([sys.executable, ROOT / "scripts/spinlock_protocol.py"],
                                output / case, "bounded_protocol", args.timeout)
            protocol = {**execution, "status": "UNKNOWN", "reason": execution["reason"] or "no_protocol_result"}
            try:
                payload = json.loads(Path(execution["stdout_log"]).read_text())
                if (payload.get("schema") == oracle["protocol_contract"]["schema"]
                        and payload.get("status") in ("PASS", "FAIL", "UNKNOWN")
                        and execution["returncode"] == {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[payload["status"]]):
                    protocol.update(payload, reason=None)
            except (OSError, ValueError, AttributeError):
                pass
            record["protocol"] = protocol
            record["protocol_status"] = protocol["status"]
            write_json(output / case / "protocol.json", protocol)
        for obligation, expectations in oracle["projections"].items():
            for isa, expected in expectations.items():
                source = ROOT / case / "model" / f"{obligation}.{isa}.litmus"
                configured = args.x86_model if isa == "x86" else args.riscv_model
                configured = configured or os.environ.get("PROTOTYPE_X86_MODEL" if isa == "x86" else "PROTOTYPE_RISCV_MODEL")
                model = Path(configured) if configured else (model_dir / ("x86tso.cat" if isa == "x86" else "riscv.cat") if model_dir else None)
                item = {"obligation": obligation, "isa": isa, "expected": expected, "actual": None,
                        "status": "UNKNOWN", "source_sha256": sha(source)}
                try:
                    if args.no_models:
                        item["reason"] = "explicitly_not_run"
                    elif not herd or not model or not model.exists():
                        item["reason"] = "herd7_or_model_unavailable"
                    else:
                        item["model_files"] = model_hashes(model)
                        execution = execute([herd, "-model", model, source], output / case / "model",
                                            f"{obligation}.{isa}", args.timeout)
                        item.update(execution)
                        observation = re.findall(r"^Observation\s+\S+\s+(Never|Sometimes|Always)\s+\d+\s+\d+\s*$",
                                                 Path(execution["stdout_log"]).read_text(), re.MULTILINE)
                        if execution["returncode"] == 0 and len(observation) == 1:
                            item["actual"] = observation[0]
                            item["status"] = "PASS" if observation[0] == expected else "FAIL"
                        else:
                            item["reason"] = execution["reason"] or "no_reliable_model_result"
                except (OSError, ValueError) as exc:
                    item["reason"] = str(exc)
                record["projections"].append(item)
        builds, native, projections = record["builds"], record["native"], record["projections"]
        native_states = [x["status"] for x in builds + native]
        record["native_status"] = aggregate(native_states)
        model_states = [x["status"] for x in projections]
        record["projection_status"] = aggregate(model_states)
        record["full_program_model_verification"] = "UNKNOWN"
        seal_benchmark_evidence(record, case, output, [c["id"] for c in summary["compilers"]])
        attach_correctness(ROOT, case, oracle, record, subject)
        write_json(output / case / "result.json", record)
        checked = validate_benchmark_evidence(ROOT, case, output)
        # Persist portable references; use recomputed statuses for both report formats.
        for key in ("native_status", "projection_status", "protocol_status", "correctness", "evidence_validation"):
            if key in checked:
                record[key] = checked[key]
        write_json(output / case / "result.json", record)
    all_states = [x[key] for x in summary["cases"].values() for key in ("native_status", "projection_status")]
    all_states.append(summary["cases"]["B02_spinlock"]["protocol_status"])
    summary["status"] = aggregate(all_states)
    summary["architecture_oracle_review"] = "CONFIRMED" if all(
        r["correctness"]["layers"]["architecture"]["review_status"] == "CONFIRMED"
        for r in summary["cases"].values()) else "UNKNOWN"
    summary["native_executions"] = sum(len(x["native"]) for x in summary["cases"].values())
    summary["model_executions"] = sum("command" in p for x in summary["cases"].values() for p in x["projections"])
    summary["bounded_protocol_checks"] = len(summary["cases"]["B02_spinlock"]["protocol"].get("checks", []))
    summary["material_checks"] = "PASS" if all(x["native_status"] == "PASS" for x in summary["cases"].values()) else "INCOMPLETE"
    write_json(output / "summary.json", summary)
    lines = ["# Benchmark 执行报告", "", "## 验证范围", "",
             f"本次执行：`{run_id}`；北京时间：{summary['time_shanghai']}。", "",
             f"已执行检查比较结果：**{summary['status']}**；原生执行 {summary['native_executions']} 次，模型调用 {summary['model_executions']} 次。", "",
             f"PASS 表示已执行检查与预期一致；架构 Oracle 审查：{summary['architecture_oracle_review']}；完整程序模型验证：UNKNOWN。", "",
             "三层 Oracle、逐项义务及评审失效原因见各例 `correctness` 字段；Sometimes/Never 与比较状态分列。", ""]
    for case, record in summary["cases"].items():
        lines += [f"## {case}", "",
                  f"- 原生构建与行为检查：{record['native_status']}；硬件事件投影比较：{record['projection_status']}。",
                  f"- 结构：UNKNOWN（尚未集成前端）；行为依据：{record['correctness']['layers']['behavior']['basis_status']}；架构审查：{record['correctness']['layers']['architecture']['review_status']}。", "",
                  f"[分项结果]({case}/result.json)；原始日志、命令、预期与实际值均保存在同一目录。", ""]
        for obligation in record["correctness"]["obligations"]:
            lines += [f"### {obligation['id']}：{obligation['requirement']}", "",
                      f"原生分项：{obligation['native_checks']['status']}；投影比较：{obligation['projection_comparison']['status']}；完整义务验证：UNKNOWN。", "",
                      "待补齐：" + "；".join(obligation['full_verification']['remaining_gaps']) + "。", ""]
            if "bounded_protocol" in obligation:
                lines.extend([
                    f"有界 SC 协议及错误对照比较：{obligation['bounded_protocol']['comparison_status']}；正式审查：UNKNOWN。", ""])
        if case == "B01_spsc_ring":
            checked = [item["fifo_check"] for item in record["native"] if "fifo_check" in item]
            lines += ["### 消费记录检查", "",
                      f"逐条消息检查：{aggregate(item['status'] for item in checked)}；记录 {len(checked)} 份消费轨迹。", "",
                      "对照运行参数检查序号、校验值和消息总数；轨迹路径、SHA256 和首个错误见 `result.json` 的 `fifo_check`。", ""]
        if case == "B02_spinlock":
            checked = [item["record_check"] for item in record["native"] if "record_check" in item]
            lines += ["### 更新记录与有界互斥协议", "",
                      f"更新轨迹检查：{aggregate(item['status'] for item in checked)}；记录 {len(checked)} 份轨迹。", "",
                      "按独立公式检查每次更新前后校验、加一关系、线程内顺序及完整的 1..2N 提交计数。", "",
                      f"有界协议及错误对照比较：{record['protocol_status']}；[协议证据](B02_spinlock/protocol.json)。", "",
                      "协议仅覆盖手工映射的两线程 SC 状态机，包含 CAS 成败、等待、重置和解锁；不作为 C11/RVWMO 完整程序证明。", ""]
    lines += ["## 结果范围", "",
              "本次结果仅覆盖记录的编译器、参数、模型与目标条件。源码来源和输入哈希见 `inputs.json`，完整机器记录见 `summary.json`。", ""]
    (output / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    if not args.out:
        publish_latest(output, output.parent)
    print(f"{summary['status']}: {output / 'summary.md'}")
    return {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[summary["status"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="fresh evidence directory; default creates a unique run under results/benchmarks")
    parser.add_argument("--compiler", action="append", help="executable path; repeat to test several compilers")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--herd7")
    parser.add_argument("--x86-model")
    parser.add_argument("--riscv-model")
    parser.add_argument("--no-models", action="store_true")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        return run(args)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
