"""Audit delivered files without importing or rerunning the TeamDev pipeline."""
from collections import Counter
from itertools import product
import hashlib
import json
from pathlib import Path
import re


def audit_pipeline_artifacts(directory):
    """Check publication, enumeration, litmus queries and raw model evidence.

    PASS concerns the consistency of the delivered evidence. Independent source
    semantics and architecture expectations remain the other comparators' job.
    Missing/unparseable evidence is UNKNOWN; contradictory evidence is FAIL.
    """
    directory = Path(directory)
    hashes, errors, units = {}, [], []

    def contents(path):
        raw = path.read_bytes()
        hashes[path.relative_to(directory).as_posix()] = hashlib.sha256(raw).hexdigest()
        return raw.decode("utf-8")

    def read(path):
        return json.loads(contents(path))

    def require(condition, message):
        if not condition:
            raise AssertionError(message)

    def check(label, action):
        try:
            return action()
        except AssertionError as error:
            errors.append({"status": "FAIL", "path": label, "reason": str(error)})
        except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
            errors.append({"status": "UNKNOWN", "path": label, "reason": str(error)})

    def frontend():
        report = read(directory / "manifest.json")
        front = read(directory / "frontend/manifest.json")
        require(report["frontend"] == front, "Embedded frontend manifest differs")
        if front["status"] != "PASS":
            errors.append({"status": "UNKNOWN", "path": "frontend", "reason": front.get("reason", front["status"])})
            return
        graph = read(directory / "frontend/input/event_ir.json")
        source_map = read(directory / "frontend/input/source_map.json")
        require(source_map["source"] == graph["source"]["path"], "SourceMap source differs")
        locations = {r["event_id"]: r["source_location"] for r in source_map["events"]}
        require(len(locations) == len(source_map["events"]) and locations == {e["id"]: e["source_location"] for e in graph["events"]}, "Input SourceMap coverage/locations differ")
        require("define " in contents(directory / "frontend/input/program.ll"), "LLVM has no function definition")
        # Empty compiler stderr is valid evidence of a successful invocation.
        for name in ("clang_ast.stderr.txt", "clang_llvm.stderr.txt"):
            contents(directory / "frontend/input" / name)
        read(directory / "frontend/discovery_evidence.json")
        if graph["schema_version"] == "bounded-hardware-event-ir-v2":
            read(directory / "frontend/input/semantic_ir.json")
            read(directory / "frontend/input/capability_report.json")
        identities = [u["id"] for u in report["units"]]
        require(bool(identities) and len(identities) == len(set(identities)), "Missing/duplicate published VU")
        require(identities == [u["id"] for u in front["units"]], "Frontend/backend VU lists differ")
        require(all(isinstance(i, str) and Path(i).name == i and i not in {".", ".."} for i in identities), "Invalid VU identity")
        for item in report["units"]:
            check(item["id"], lambda item=item: unit(report, item))
        if len(units) == len(identities):
            require(report["herd_attempts"] == sum(u["herd_runs"] for u in units), "Pipeline herd count differs")

    def unit(report, item):
        identity = item["id"]
        front = directory / "frontend/units" / identity
        back = directory / "backend" / identity
        documents = {name: read(front / f"{name}.json")
                     for name in ("event_ir", "source_map", "candidate", "verification_unit")}
        graph = documents["event_ir"]
        enumeration = read(back / "outcome_enumeration.json")
        for name, document in documents.items():
            delivered = read(back / f"{name}.json")
            if name == "event_ir":
                require(delivered.pop("outcome_enumeration") == enumeration, "Embedded outcome enumeration differs")
            require(delivered == document, f"Frontend/backend {name} differs")
        require(graph["verification_unit"] == documents["verification_unit"], "Embedded VU differs")
        require(graph["candidate"] == documents["candidate"], "Embedded candidate differs")
        backend = read(back / "manifest.json")
        require(item["backend"] == backend, "Embedded backend manifest differs")
        telemetry = read(back / "telemetry.json")
        require(backend["telemetry"] == telemetry, "Embedded telemetry differs")
        probe = read(back / "herd_probe.json")
        require(backend["herd_probe"] == probe, "Embedded model probe differs")
        write_map = read(back / "write_value_map.json")
        loads = {e["target"]: e for e in graph["events"] if e["kind"] == "Load"}
        domains = enumeration["domains"]
        require(set(domains) == set(loads) == set(write_map["loads"]), "Load/domain coverage differs")
        for target, values in domains.items():
            require(bool(values) and all(type(v) is int for v in values) and values == sorted(set(values)), "Invalid finite Load domain")
            require(write_map["loads"][target]["event_id"] == loads[target]["id"], "Load/value-map identity differs")
        expected = [dict(zip(domains, values)) for values in product(*domains.values())]
        require(enumeration["outcomes"] == expected, "Outcome enumeration is incomplete or reordered")
        queries = read(back / "targeted_queries.json")["queries"]
        require(queries == (read(directory / "queries.json") if report["invocation"].get("queries") else []), "Delivered targeted queries differ")
        targets = {e["id"]: e["target"] for e in loads.values()}
        expected_queries = [{"query_id": q["id"], "outcome": {targets[e]: v for e, v in q["event_values"].items()}} for q in queries]
        matrix = read(back / "outcome_matrix.json")
        rows = matrix["outcomes"]
        require([r["outcome"] for r in rows if "query_id" not in r] == expected, "Matrix enumeration coverage differs")
        require([{k: r[k] for k in ("query_id", "outcome")} for r in rows if "query_id" in r] == expected_queries, "Matrix targeted query coverage differs")
        mappings = read(back / "litmus_register_map.json")
        require(set(mappings) == {f"{arch}_outcome_{i:06d}" for i in range(len(rows)) for arch in ("x86", "riscv")}, "Register-map coverage differs")
        require(telemetry["actual_outcome_count"] == len(expected) and telemetry["targeted_query_count"] == len(queries), "Outcome telemetry differs")
        thread_indices = {t["id"]: i for i, t in enumerate(graph["thread_contexts"])}
        comparisons, ran = [], 0
        for index, row in enumerate(rows):
            states = {}
            for arch, dialect in (("x86", "X86"), ("riscv", "RISCV")):
                key = f"{arch}_outcome_{index:06d}"
                mapping = mappings[key]
                require(row["register_mapping"][arch] == mapping and set(mapping) == set(loads), "Row/register-map coverage differs")
                require(all(mapping[t]["thread"] == loads[t]["thread"] for t in loads), "Register thread differs from Load thread")
                registers = [(m["thread"], m["register"]) for m in mapping.values()]
                require(len(registers) == len(set(registers)), "Distinct Loads share an observation register")
                litmus = contents(back / "litmus" / f"{key}.litmus")
                require(litmus.splitlines()[0] == f"{dialect} VU_{key}", "Litmus architecture/test name differs")
                condition = " /\\ ".join(f"{thread_indices[mapping[t]['thread']]}:{mapping[t]['register']}={v}" for t, v in row["outcome"].items())
                require(litmus.rstrip().endswith(f"\nexists ({condition})"), "Litmus outcome differs from matrix/register map")
                result = row["architectures"][arch]
                raw = contents(back / "herd" / f"{key}.herd.txt")
                require(raw == result["raw_output"], "Raw herd file differs from matrix copy")
                recorded = Path(report["output"]) / "backend" / identity
                require(result["raw_path"] == str(recorded / "herd" / f"{key}.herd.txt"), "Raw log path differs")
                if result["status"] != "RAN":
                    errors.append({"status": "FAIL" if result["status"] == "FAILED" else "UNKNOWN", "path": f"{identity}/{key}", "reason": result.get("reason") or result["status"]})
                    states[arch] = None
                    continue
                observations = re.findall(r"^Observation\s+(\S+)\s+(Never|Sometimes|Always)\s+\d+\s+\d+\s*$", raw, re.MULTILINE)
                require(result["exit_code"] == 0 and observations == [(f"VU_{key}", result["observation"])], "Raw herd observation/exit differs")
                require(not re.search(r"User error|Fatal", raw), "Raw herd output contains a model error")
                require(result["allowed"] is (result["observation"] != "Never"), "Allowed flag differs from raw observation")
                command = result["command"]
                require(bool(command), "Missing model command")
                if matrix["backend"] == "local":
                    require("-model" in command, "Missing model command option")
                    require(command[command.index("-model") + 1] == result["model"] == probe["models"][arch], "Model command differs")
                    require(command[-1] == str(recorded / "litmus" / f"{key}.litmus"), "Model command input differs")
                else:
                    require(result["stdin_input_path"] == str(recorded / "litmus" / f"{key}.litmus"), "Docker model input differs")
                states[arch] = result["allowed"]
                ran += 1
            comparison = ("UNKNOWN" if None in states.values() else
                          {(False, True): "RV_ONLY", (True, False): "X86_ONLY", (True, True): "BOTH_ALLOWED", (False, False): "BOTH_FORBIDDEN"}[(states["x86"], states["riscv"])])
            comparisons.append({"outcome": row["outcome"], "comparison": comparison})
        differential = read(back / "differential_summary.json")
        require(differential["outcomes"] == comparisons and differential["counts"] == dict(Counter(r["comparison"] for r in comparisons)), "Architecture differential summary differs from raw results")
        if ran == 2 * len(rows):
            require(telemetry["herd_runs"] == ran, "Model execution count differs")
        units.append({"id": identity, "enumerated_outcomes": len(expected), "targeted_queries": len(queries),
                      "herd_runs": telemetry["herd_runs"], "verified_model_results": ran})

    check("frontend", frontend)
    status = "FAIL" if any(e["status"] == "FAIL" for e in errors) else "UNKNOWN" if errors or not units else "PASS"
    return {"status": status, "errors": errors, "units": units, "sha256": hashes,
            "scope": "delivered LLVM/diagnostics, EventIR/SourceMap/VU publication, enumeration, litmus conditions/register maps, raw herd results and architecture summaries"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pipeline", type=Path, help="one delivered pipeline directory")
    result = audit_pipeline_artifacts(parser.parse_args().pipeline)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit({"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[result["status"]])
