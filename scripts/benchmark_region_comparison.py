"""Independent, manually specified checks on actual B02 region path artifacts.

No team implementation is imported. These checks concern source-derived regions,
not whole-program/thread-instance discovery, VU completeness or CAS ISA lowering.
"""
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def const(type_, value):
    return {"op": "const", "type": type_, "value": value}


def neg(value):
    return {"op": "!", "type": "Bool", "args": [value]}


def relation(op, left, right):
    return {"op": op, "type": "Bool", "args": [left, right]}


def check_b02(directory, expected_config):
    """Expected paths are derived analytically from reviewed loops, not output."""
    failures, hashes = [], {}

    def check(condition, message):
        if not condition:
            failures.append(message)

    def load(name):
        path = directory / name
        hashes[name] = sha(path)
        return read(path)

    def event_source(event, function, file, line):
        source = event.get("source", {})
        check(source.get("function") == function and source.get("file") == file and source.get("line") == line,
              f"wrong source for {event.get('id')}")
        check(source.get("sha256") == expected_config["source_files"].get(file), "stale event source hash")
        check(type(source.get("begin")) is int and type(source.get("end")) is int and source["end"] > source["begin"], "invalid event range")

    def check_cas(event, expected_local):
        check(event.get("kind") == "CAS" and event.get("indivisible") is True and event.get("strong") is True,
              "CAS lost indivisibility/strong identity")
        check(event.get("object") == "ctx.lock.locked" and event.get("type") == "I32" and event.get("atomic") is True,
              "CAS object/type/atomic mismatch")
        check(event.get("success_order") == "Acquire" and event.get("failure_order") == "Relaxed", "CAS orders differ")
        check(event.get("expected") == const("I32", 0) and event.get("desired") == const("I32", 1), "CAS is not 0-to-1")
        read_value = {"op": "symbol", "type": "I32", "name": event["id"]}
        success = relation("==", read_value, const("I32", 0))
        writeback = {"op": "ite", "type": "I32", "args": [success, const("I32", 0), read_value]}
        check(event.get("read") == read_value and event.get("success") == success and event.get("write_condition") == success,
              "CAS comparison/write predicate differs")
        check(event.get("expected_after") == writeback and event.get("expected_local") == expected_local, "CAS failure expected writeback differs")
        return success, writeback

    try:
        report, delivered_config = load("manifest.json"), load("configuration.json")
        check(delivered_config == expected_config, "delivered config differs from independent input")
        check(report.get("schema") == "bounded-region-run-1" and report.get("status") == "BOUNDARY", "expected incomplete bounded extraction")
        check(report.get("full_program_model_verification") == "UNKNOWN" and report.get("whole_program_frontend") == "NOT_IMPLEMENTED", "region result promoted to whole-program verdict")
        check(report.get("architecture_models") == {"x86": "NOT_RUN", "riscv": "NOT_RUN"}, "region output claims architecture verification")
        closure = {str(Path(row["path"]).relative_to(Path(report["source"]).parents[1])): row["sha256"]
                   for row in report["input_closure"] if row["project_input"]}
        check(closure == expected_config["source_files"], "Clang project closure differs from reviewed pins")
        check(report.get("environment_assumptions") == expected_config["environment"], "missing environment assumptions")
        entries = report["regions"]
        check(len(entries) == len(expected_config["regions"]), "missing or duplicate region")
        seen_regions, all_event_ids = set(), set()
        for entry, wanted in zip(entries, expected_config["regions"]):
            check(entry.get("configuration") == wanted, "wrong region entry/instance/arguments")
            name = entry["path_file"]
            check(Path(name).name == name, "unsafe path artifact name")
            if Path(name).name != name:
                continue
            document = load(name)
            check(document.get("schema") == "bounded-region-paths-1" and document.get("region") == wanted, "wrong path schema/region")
            check(wanted["id"] not in seen_regions, "duplicate region identity")
            seen_regions.add(wanted["id"])
            paths, signatures = document["paths"], []
            check(len(paths) == entry["path_count"], "path count cache differs")
            returned = sum(p["termination"] == "RETURN" for p in paths)
            boundary = sum(p["termination"] == "BOUNDARY" for p in paths)
            check(entry["returned_paths"] == returned and entry["boundary_paths"] == boundary, "termination count cache differs")
            for path in paths:
                events, actions = path["events"], path["actions"]
                check(path.get("region") == wanted["id"] and path.get("instance") == wanted["instance"], "path instance identity differs")
                check(path["termination"] in {"RETURN", "BOUNDARY"}, "unexpected termination")
                check(path["feasibility"] == ("UNKNOWN" if path["guards"] else "CONSTANT_PATH"), "symbolic feasibility promoted")
                ids = [e["id"] for e in events]
                check(len(ids) == len(set(ids)), "duplicate event in path")
                check(path["relations"] == {"program_order": [[a,b] for a,b in zip(ids,ids[1:])]}, "path po differs")
                check([a["event"] for a in actions if a["kind"] == "MemoryEvent"] == ids, "event/action stream differs")
                check([a["index"] for a in actions] == list(range(len(actions))), "action order is not contiguous")
                for event in events:
                    check(event["instance"] == wanted["instance"], "event instance differs")
                    check(event["id"].startswith(f"{wanted['instance']}:{wanted['id']}:E"), "event ID omits region/instance")
                    check(event.get("call_stack", [{}])[0].get("function") == wanted["entry"], "event call stack omits entry")
                    check(event.get("loop_iterations") is not None, "event loop vector missing")
                # IDs intentionally repeat across alternative paths of one region.
                if all_event_ids.intersection(ids) and wanted["id"] not in {e.split(":")[1] for e in all_event_ids.intersection(ids)}:
                    check(False, "event ID collides across regions")
                all_event_ids.update(ids)
                guards = [g["predicate"] for g in path["guards"]]
                function = wanted["entry"]
                if function in {"rte_spinlock_lock", "rte_spinlock_trylock"}:
                    cas = [e for e in events if e["kind"] == "CAS"]
                    check(bool(cas), "CAS disappeared")
                    if not cas:
                        continue
                    local = cas[0]["expected_local"]
                    conditions = []
                    for event in cas:
                        event_source(event, function, "common/dpdk_spinlock.h", 46 if function.endswith("_lock") else 93)
                        success, writeback = check_cas(event, local)
                        conditions.append(success)
                        writes = [a for a in actions if a["kind"] == "LocalWrite" and a.get("reason") == "cas_expected_writeback" and a.get("value") == writeback]
                        check(len(writes) == 1 and writes[0].get("local") == local, "CAS writeback action lost")
                    initializers = [a for a in actions if a["kind"] == "LocalWrite" and a.get("reason") == "initializer"]
                    check(len(initializers) == 1 and initializers[0].get("value") == const("I32", 0), "expected initializer lost")
                    if function.endswith("trylock"):
                        check(len(events) == 1 and path["termination"] == "RETURN" and not guards, "trylock path changed")
                        check(path["return_value"] == {"op":"cast","type":"I32","args":[conditions[0]]}, "trylock return is not CAS result")
                        signatures.append("trylock")
                        continue
                    waits = [e for e in events if e["kind"] == "Load"]
                    check(len(cas) in {1,2} and len(events) == len(cas)+len(waits), "CAS split or unexpected memory event")
                    wait_conditions = []
                    for event in waits:
                        event_source(event, "rte_wait_until_equal_32", "common/dpdk_wait.h", 14)
                        check(event.get("object") == "ctx.lock.locked" and event.get("type") == "U32" and event.get("ordering") == "Relaxed" and event.get("atomic") is True, "wait semantics differ")
                        wait_conditions.append(relation("!=", {"op":"symbol","type":"U32","name":event["id"]}, const("U32",0)))
                    reset = [a for a in actions if a["kind"] == "LocalWrite" and a.get("reason") == "assignment"]
                    check(len(reset) == len(cas)-1, "retry reset lost or invented")
                    if reset:
                        check(reset[0].get("value") == const("I32",0) and reset[0].get("local") == local and reset[0]["source"]["line"] == 50, "retry does not reset expected=0")
                        event_positions = [a["index"] for a in actions if a["kind"] == "MemoryEvent"]
                        check(event_positions[-2] < reset[0]["index"] < event_positions[-1], "reset moved outside wait/retry interval")
                    if len(cas) == 1 and not waits:
                        check(guards == [conditions[0]] and path["termination"] == "RETURN", "first success guard lost")
                        signatures.append("first-success")
                    elif len(cas) == 1:
                        check(len(waits) == 4 and path["termination"] == "BOUNDARY", "live wait truncated as return")
                        check(guards == [neg(conditions[0])]+wait_conditions, "wait boundary guard differs")
                        signatures.append("wait-boundary")
                    else:
                        check(1 <= len(waits) <= 4 and events[0] == cas[0] and events[-1] == cas[-1], "retry event order differs")
                        expected_guards = [neg(conditions[0])]+wait_conditions[:-1]+[neg(wait_conditions[-1])]
                        expected_guards += [conditions[-1] if path["termination"] == "RETURN" else neg(conditions[-1])]
                        check(guards == expected_guards, "failed CAS/wait/retry guards differ")
                        signatures.append(f"retry-{len(waits)}-{path['termination']}")
                    if path["termination"] == "BOUNDARY":
                        reason = path.get("reason") or {}
                        check(reason.get("kind") == "loop_bound" and reason.get("pending_guard") is not None, "missing live-successor boundary")
                elif function == "rte_spinlock_unlock":
                    check(len(events) == 1, "unlock event count differs")
                    if events:
                        e=events[0]
                        event_source(e,function,"common/dpdk_spinlock.h",70)
                        check(e.get("kind") == "Store" and e.get("object") == "ctx.lock.locked" and e.get("atomic") is True and e.get("ordering") == "Release" and e.get("value") == const("I32",0), "unlock semantics differ")
                    check(path["termination"] == "RETURN" and not guards, "unlock path changed")
                    signatures.append("unlock")
                elif function in {"await_start", "release_start"}:
                    loads = [e for e in events if e["kind"] == "Load"]
                    release = function == "release_start"
                    check(1 <= len(loads) <= 4 and len(events) == len(loads)+int(release and path["termination"]=="RETURN")+int(not release), "startup event count differs")
                    startup_guards = []
                    for event in loads:
                        event_source(event, function, "common/bench.h",45 if release else 40)
                        type_ = "U32" if release else "Bool"
                        value = {"op":"symbol","type":type_,"name":event["id"]}
                        check(event.get("object") == ("ctx.gate.ready" if release else "ctx.gate.go") and event.get("ordering") == "Acquire" and event.get("atomic") is True and event.get("read") == value, "startup load semantics differ")
                        startup_guards.append(relation("!=", value, const("U32",2)) if release else neg(value))
                    expected_guards = startup_guards if path["termination"] == "BOUNDARY" else startup_guards[:-1]+[neg(startup_guards[-1]) if release else startup_guards[-1]["args"][0]]
                    check(guards == expected_guards, "startup continuation/exit guards differ")
                    if release and path["termination"] == "RETURN":
                        check(events[-1].get("kind") == "Store" and events[-1].get("ordering") == "Release" and events[-1].get("object") == "ctx.gate.go" and events[-1].get("value") == const("Bool",1), "start release lost")
                    if not release:
                        event = events[0]
                        check(event.get("kind") == "FetchAdd" and event.get("indivisible") is True and event.get("object") == "ctx.gate.ready" and event.get("operand") == const("U32",1) and event.get("ordering") == "Release", "startup fetch_add lost")
                        read_value = {"op":"symbol","type":"U32","name":event["id"]}
                        check(event.get("read") == read_value and event.get("value") == {"op":"+","type":"U32","args":[read_value,const("U32",1)]}, "fetch_add lost old-value/data expression")
                    if path["termination"] == "BOUNDARY":
                        check(len(loads) == 4 and path.get("reason",{}).get("kind") == "loop_bound", "startup live loop truncated")
                    signatures.append(f"{len(loads)}-{path['termination']}")
                elif function == "checksum":
                    # Constant is computed independently using the stated U64 formula.
                    value = ((4*11400714819323198485) % (1<<64)) ^ 6510698343141591806
                    check(not events and not guards and path["return_value"] == const("U64",value), "U64 checksum semantics differ")
                    signatures.append("checksum")
                else:
                    check(False, "unexpected region entry")
            function = wanted["entry"]
            if function == "rte_spinlock_lock":
                expected_signatures = ["first-success","wait-boundary"]+[f"retry-{n}-{status}" for n in range(1,5) for status in ["RETURN","BOUNDARY"]]
            elif function in {"await_start", "release_start"}:
                expected_signatures = [f"{n}-RETURN" for n in range(1,5)]+["4-BOUNDARY"]
            else:
                expected_signatures = [{"rte_spinlock_unlock":"unlock","rte_spinlock_trylock":"trylock","checksum":"checksum"}[function]]
            check(sorted(signatures) == sorted(expected_signatures), f"{wanted['id']}: path coverage differs from independent loop calculation")
    except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
        return {"status":"UNKNOWN","reason":str(error),"failures":failures,"artifact_sha256":hashes,
                "full_program_model_verification":"UNKNOWN"}
    return {"status":"FAIL" if failures else "PASS", "scope":"B02 independently specified function-region paths only",
            "failures":failures,"artifact_sha256":hashes,"full_program_model_verification":"UNKNOWN",
            "thread_instance_discovery":"NOT_CHECKED; instances are explicit region configuration"}
