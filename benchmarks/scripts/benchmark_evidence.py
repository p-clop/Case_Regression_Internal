"""Seal portable run artifacts and recompute comparisons when collecting evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from oracle_contract import aggregate, attach_correctness, input_snapshot, subject_hash, validate_contract

SCHEMA = "benchmark-evidence-1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal_benchmark_evidence(record, case, output, compiler_ids):
    """Keep commands as executed; make artifact references relative to the run root."""
    output = output.resolve()
    artifacts = {}

    def register(value):
        path = Path(value).resolve()
        relative = path.relative_to(output).as_posix()
        artifacts[relative] = sha(path) if path.is_file() else None
        return relative

    def visit(value):
        if isinstance(value, dict):
            for key in ("stdout_log", "stderr_log"):
                if key in value:
                    value[key] = register(value[key])
            for key in ("fifo_check", "record_check"):
                if key in value:
                    value[key]["path"] = register(value[key]["path"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(record)
    if case == "B02_spinlock":
        register(output / case / "protocol.json")
    record.update(case=case, evidence={"schema": SCHEMA, "output_root": str(output),
                                      "compiler_ids": compiler_ids, "artifacts": artifacts})


def validate_benchmark_evidence(root, case, output):
    """Return fresh layered results; absent/unreliable items cannot contribute PASS."""
    # Lazy import shares the live runner's matrix and observation checks without a cycle.
    from run_suite import INVALID, MATRIX, model_hashes, native_result

    root, output = root.resolve(), output.resolve()
    snapshot = json.loads((output / "inputs.json").read_text())
    if snapshot != input_snapshot(root):
        raise ValueError("stale_benchmark_inputs")
    oracle = validate_contract(root, case)
    record = json.loads((output / case / "result.json").read_text())
    if not isinstance(record, dict) or record.get("case") != case:
        raise ValueError("benchmark_result_case_mismatch")
    if record.get("oracle_sha256") != sha(root / case / "oracle.json"):
        raise ValueError("stale_oracle")
    evidence = record.get("evidence", {})
    if not isinstance(evidence, dict) or evidence.get("schema") != SCHEMA or not isinstance(evidence.get("artifacts"), dict):
        raise ValueError("legacy_result_without_benchmark_evidence")
    artifacts = evidence["artifacts"]
    origin = Path(evidence["output_root"])
    if not origin.is_absolute():
        raise ValueError("invalid_evidence_output_root")
    problems = []

    def artifact(name):
        path = (output / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(output):
            raise ValueError(f"artifact_path_outside_run:{name}")
        if name not in artifacts or not artifacts[name] or sha(path) != artifacts[name]:
            raise ValueError(f"artifact_missing_or_changed:{name}")
        return path

    def execution(item):
        checked = deepcopy(item)
        for key in ("stdout_log", "stderr_log"):
            checked[key] = str(artifact(item[key]))
        if (not isinstance(item.get("command"), list) or not item["command"]
                or not all(isinstance(x, str) for x in item["command"])
                or "reason" not in item or "returncode" not in item):
            raise ValueError("incomplete_execution_record")
        return checked

    def unavailable(exc, item=None):
        problems.append(str(exc))
        item = item if isinstance(item, dict) else {}
        return {"kind": "unknown", "stdout_log": "", **(item or {}), "status": "UNKNOWN", "reason": str(exc)}

    compilers = evidence.get("compiler_ids")
    if (not isinstance(compilers, list)
            or any(not isinstance(c, str) or not re.fullmatch(r"cc\d+", c) for c in compilers)
            or len(compilers) != len(set(compilers))):
        raise ValueError("invalid_compiler_plan")
    builds, native = record.get("builds", []), record.get("native", [])
    if any(not isinstance(items, list) for items in (builds, native, record.get("projections", []))):
        raise ValueError("invalid_execution_lists")
    checked_builds, checked_native = [], []
    build_keys, native_keys = set(), set()
    for item in builds:
        try:
            key = (item["compiler"], item["optimization"], item["kind"])
            if key in build_keys or key[0] not in compilers:
                raise ValueError("duplicate_or_unplanned_build")
            build_keys.add(key)
            checked = execution(item)
            binary = "checker_corruption" if key[2] == "checker_control" else "benchmark"
            directory = f"{case}/{key[0]}_{key[1][1:]}"
            if (checked["command"] != ["bash", str(Path(item["cwd"]) / case / "build.sh"),
                                       str(origin / directory / "bin" / binary)]
                    or item["build_environment"]["BENCH_OPT"] != key[1]
                    or item["build_environment"]["BENCH_INJECT_CORRUPTION"] != ("1" if key[2] == "checker_control" else "0")):
                raise ValueError("build_command_or_environment_mismatch")
            checked["status"] = ("UNKNOWN" if checked["reason"] else
                                 "PASS" if checked["returncode"] == 0 else "FAIL")
            if checked["status"] == "PASS" and not re.fullmatch(r"[0-9a-f]{64}", item.get("binary_sha256", "")):
                raise ValueError("missing_binary_build_hash")
            checked_builds.append(checked)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checked_builds.append(unavailable(exc, item))
    for item in native:
        try:
            key = (item["compiler"], item["optimization"], item["label"])
            if key in native_keys or key[0] not in compilers:
                raise ValueError("duplicate_or_unplanned_native_check")
            native_keys.add(key)
            baseline = dict(MATRIX[case])
            invalid = {f"invalid_{i}": p for i, p in enumerate(INVALID[case])}
            if item["label"] in baseline:
                parameters, kind, expected = baseline[item["label"]], "baseline", oracle["native"]["baseline"]
            elif item["label"] in invalid and item["optimization"] == "-O2":
                parameters, kind = invalid[item["label"]], "invalid_configuration"
                expected = oracle["native"]["invalid_configuration"]
            elif item["label"] == "checker_corruption" and item["optimization"] == "-O2":
                parameters, kind = ["--iterations", "1000"], "checker_control"
                expected = oracle["native"]["checker_corruption"]
            else:
                raise ValueError("unexpected_native_check")
            if item["kind"] != kind:
                raise ValueError("native_check_kind_mismatch")
            checked_execution = execution(item)
            binary = "checker_corruption" if kind == "checker_control" else "benchmark"
            if item["command"][0] != str(origin / case / f"{key[0]}_{key[1][1:]}" / "bin" / binary):
                raise ValueError("native_binary_path_mismatch")
            args = list(item["command"][1:])
            local_args = list(args)
            if kind == "baseline":
                trace_key = "fifo_check" if case == "B01_spsc_ring" else "record_check"
                suffix = "messages" if case == "B01_spsc_ring" else "updates"
                trace = f"{case}/{key[0]}_{key[1][1:]}/{key[2]}.{suffix}.jsonl"
                if args != parameters + ["--trace", str(origin / trace)] or item[trace_key]["path"] != trace:
                    raise ValueError("native_parameters_or_trace_mismatch")
                try:
                    local_args[-1] = str(artifact(trace))
                except (OSError, ValueError) as exc:
                    problems.append(str(exc))
                    # Still check reliable stdout; omit the untrusted trace.
                    local_args = list(parameters)
            elif args != parameters:
                raise ValueError("native_parameters_mismatch")
            checked = native_result(checked_execution, case, expected, local_args)
            checked.update(compiler=key[0], optimization=key[1], label=key[2], kind=kind)
            checked_native.append(checked)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checked_native.append(unavailable(exc, item))
    required_builds = {(c, opt, "baseline") for c in compilers for opt in ("-O0", "-O2")}
    required_builds |= {(c, "-O2", "checker_control") for c in compilers}
    required_native = {(c, opt, label) for c in compilers for opt in ("-O0", "-O2") for label, _ in MATRIX[case]}
    required_native |= {(c, "-O2", f"invalid_{i}") for c in compilers for i in range(len(INVALID[case]))}
    required_native |= {(c, "-O2", "checker_corruption") for c in compilers}
    coverage = "PASS"
    if build_keys != required_builds or native_keys != required_native or not compilers:
        problems.append("incomplete_native_check_coverage")
        coverage = "UNKNOWN"
    record.update(builds=checked_builds, native=checked_native,
                  native_status=aggregate([coverage] + [x["status"] for x in checked_builds + checked_native]))

    projections, seen = [], set()
    for item in record.get("projections", []):
        placeholder = {"obligation": "", "isa": "", "expected": None, "model_files": {}}
        if not isinstance(item, dict):
            projections.append(unavailable("invalid_projection_record", placeholder))
            continue
        checked = {**placeholder, **item, "status": "UNKNOWN", "actual": None, "model_files": {}}
        try:
            key = (item["obligation"], item["isa"])
            if key in seen or key[0] not in oracle["projections"] or key[1] not in ("x86", "riscv"):
                raise ValueError("duplicate_or_unplanned_projection")
            seen.add(key)
            checked["expected"] = oracle["projections"][key[0]][key[1]]
            source = root / case / "model" / f"{key[0]}.{key[1]}.litmus"
            if item["source_sha256"] != sha(source):
                raise ValueError("stale_projection_source")
            if "command" not in item:
                raise ValueError(item.get("reason") or "model_not_run")
            if len(item["command"]) != 4 or item["command"][1] != "-model":
                raise ValueError("invalid_model_command")
            if item["command"][-1] != str(Path(item["cwd"]) / case / "model" / source.name):
                raise ValueError("model_command_source_mismatch")
            current_models = model_hashes(item["command"][2])
            if not current_models or current_models != item.get("model_files"):
                raise ValueError("model_closure_missing_or_changed")
            checked.update(execution(item), model_files=current_models)
            checked.update(expected=oracle["projections"][key[0]][key[1]], actual=None, status="UNKNOWN")
            observations = re.findall(r"^Observation\s+\S+\s+(Never|Sometimes|Always)\s+\d+\s+\d+\s*$",
                                      Path(checked["stdout_log"]).read_text(), re.MULTILINE)
            if checked["reason"] or checked["returncode"] != 0 or len(observations) != 1:
                raise ValueError("unreliable_model_output")
            checked.update(actual=observations[0], status="PASS" if observations[0] == checked["expected"] else "FAIL")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checked = unavailable(exc, checked)
        projections.append(checked)
    required = {(p, isa) for p in oracle["projections"] for isa in ("x86", "riscv")}
    coverage = "PASS" if seen == required else "UNKNOWN"
    if coverage == "UNKNOWN":
        problems.append("incomplete_projection_coverage")
    record.update(projections=projections, projection_status=aggregate([coverage] + [p["status"] for p in projections]))

    if case == "B02_spinlock":
        try:
            artifact(f"{case}/protocol.json")
            protocol = execution(record["protocol"])
            payload = json.loads(Path(protocol["stdout_log"]).read_text())
            contract = oracle["protocol_contract"]
            required = {("atomic_cas", n) for n in contract["baseline_rounds"]}
            required |= {(v, contract["control_rounds"]) for v in ("split_cas", "missing_expected_reset")}
            checks = payload["checks"]
            if (payload["schema"] != contract["schema"] or len(checks) != len(required)
                    or {(c["variant"], c["rounds_per_worker"]) for c in checks} != required):
                raise ValueError("incomplete_protocol_checks")
            states = ["UNKNOWN" if c["status"] not in ("PASS", "FAIL") else
                      "PASS" if c["status"] == contract["expected"][c["variant"]] else "FAIL" for c in checks]
            for check, state in zip(checks, states):
                check.update(expected=contract["expected"][check["variant"]], comparison_status=state)
            status = aggregate(states)
            if protocol["reason"] or protocol["returncode"] != {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[status]:
                raise ValueError("unreliable_protocol_output")
            record["protocol"] = {**protocol, **payload, "status": status}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            record["protocol"] = unavailable(exc)
        record["protocol_status"] = record["protocol"]["status"]
    attach_correctness(root, case, oracle, record, subject_hash(snapshot))
    record["evidence_validation"] = {"status": "UNKNOWN" if problems else "PASS", "issues": problems,
                                     "reason": "; ".join(problems) if problems else None,
                                     "scope": "current inputs, artifact hashes and recomputed comparisons"}
    return record
