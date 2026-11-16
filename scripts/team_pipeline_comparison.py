"""Compare delivered TeamDev artifacts; never rerun an internal slicer as team output."""
from copy import deepcopy
import json
from pathlib import Path

from prototype.pipeline import check_oracle
from prototype.regression import compare_case, canonical_unit

ORDERS = {"Plain": "plain", "Relaxed": "relaxed", "Acquire": "acquire", "Release": "release",
          "AcqRel": "acq_rel", "SeqCst": "seq_cst"}


def read(path):
    return json.loads(Path(path).read_text())


def semantic_graph(graph):
    """Lossless common semantic fields, reconstructed from the native team IR."""
    if graph.get("schema_version") != "bounded-hardware-event-ir-v2":
        raise ValueError("Full comparison requires the explicit extended contract")
    objects = []
    for original in graph["shared_objects"]:
        obj = {k: deepcopy(original[k]) for k in ("id", "initial", "origin", "source_location",
               "base_object", "field_path", "allocation_site") if k in original}
        obj["type"] = original["original_type"]
        obj["source_location"].pop("file", None)
        objects.append(obj)
    threads = []
    for index, thread in enumerate(graph["thread_contexts"]):
        events = []
        # execution_index is checked against authoritative po by TeamDev.
        stream = sorted((e for e in graph["events"] if e["thread"] == thread["id"]), key=lambda e: e["execution_index"])
        edges = [edge for edge in graph["relations"]["program_order"] if edge[0] in {e["id"] for e in stream}]
        expected_po = [[a["id"], b["id"]] for a, b in zip(stream, stream[1:])]
        if sorted(edges) != sorted(expected_po):
            raise ValueError("Native program order differs from execution order")
        for original in stream:
            if original["kind"] != "Fence":
                obj = next(o for o in graph["shared_objects"] if o["name"] == original["object"])
                if original["atomic"] != (obj["original_type"] == "atomic_int"):
                    raise ValueError("Atomic classification differs from object type")
            event = {k: deepcopy(original[k]) for k in ("id", "kind", "object", "function", "source_location")}
            event["source_location"].pop("file", None)
            event["ordering"] = ORDERS[original["ordering"]]
            if original["kind"] == "Store":
                event["value"] = deepcopy(original["value"])
            if original["kind"] == "Load":
                event["target"] = original["target"].removeprefix(thread["id"] + "_")
            events.append(event)
        threads.append({"id": thread["id"], "index": index, "entry": thread["entry_function"], "events": events})
    return {"version": "prototype-1", "source": deepcopy(graph["source"]), "objects": objects, "threads": threads,
            **{k: deepcopy(graph[k]) for k in ("bindings", "calls", "assumptions")}}


def actual_artifacts(directory, oracle):
    graph = read(directory / "frontend/input/event_ir.json")
    program = semantic_graph(graph)
    units = read(directory / "manifest.json")["units"]
    if len(units) != 1:
        raise ValueError("Catalog comparison currently requires exactly one explicitly seeded VU")
    path = directory / "frontend/units" / units[0]["id"]
    delivered = read(path / "event_ir.json")
    for native, map_path in ((graph, directory / "frontend/input/source_map.json"),
                             (delivered, path / "source_map.json")):
        mapping = read(map_path)
        if mapping["source"] != native["source"]["path"]:
            raise ValueError("SourceMap source differs")
        records = {r["event_id"]: r["source_location"] for r in mapping["events"]}
        if len(records) != len(mapping["events"]) or records != {e["id"]: e["source_location"] for e in native["events"]}:
            raise ValueError("SourceMap coverage or location differs")
    unit = semantic_graph(delivered)
    vu = read(path / "verification_unit.json")
    if delivered["verification_unit"] != vu or delivered["candidate"] != read(path / "candidate.json"):
        raise ValueError("Embedded/standalone artifacts differ")
    if set(vu["event_ids"]) != {e["id"] for e in delivered["events"]} or set(vu["objects"]) != {o["name"] for o in delivered["shared_objects"]}:
        raise ValueError("VU membership differs from delivered projection")
    unit["seed_objects"] = delivered["candidate"]["seed_objects"]
    unit["shared_objects"] = sorted(read(directory / "frontend/discovery_evidence.json")["may_shared_objects"])
    unit["slice"] = vu["slice"]
    unit["edges"] = [{"kind": "po" if kind == "program_order" else kind, "from": a, "to": b}
                     for kind, edges in delivered["relations"].items() for a, b in edges]
    observations = []
    for item in oracle["outcome"]:
        if "event" in item:
            observations.append(deepcopy(item))
            continue
        thread = program["threads"][item["thread"]]
        loads = [e for e in thread["events"] if e["kind"] == "Load" and e["object"] == item["object"]]
        observations.append({"thread": item["thread"], "event": loads[item.get("occurrence", 0)]["id"], "value": item["value"]})
    # Observation conditions are caller-supplied oracle queries, not extracted
    # statements. They are checked against actual retained Load IDs below.
    ids = {e["id"] for t in unit["threads"] for e in t["events"] if e["kind"] == "Load"}
    if any(o["event"] not in ids for o in observations):
        raise ValueError("Oracle observation refers to a removed/non-Load event")
    unit["outcome"] = observations
    return program, unit


def compare_full(directory, oracle, baseline):
    try:
        program, unit = actual_artifacts(directory, oracle)
        if oracle.get("validation") == "structure":
            independent = compare_case(program, unit, oracle)
        else:
            errors = check_oracle(program, unit, oracle)
            independent = {"status": "FAIL" if errors else "PASS", "errors": errors}
        baseline_program = read(baseline / "eventir.json")
        baseline_unit = read(baseline / "unit.json")
        errors = []
        for prefix, actual, wanted, fields in (
            ("program", program, baseline_program, ("objects", "threads", "bindings", "calls", "assumptions")),
            ("unit", unit, baseline_unit, ("seed_objects", "shared_objects", "objects", "threads", "bindings", "calls", "assumptions", "outcome"))):
            for field in fields:
                if actual[field] != wanted[field]:
                    errors.append({"path": f"{prefix}.{field}", "expected": wanted[field], "actual": actual[field]})
        for field in ("retained_events", "removed_events", "removed_objects"):
            if unit["slice"][field] != baseline_unit["slice"][field]:
                errors.append({"path": f"unit.slice.{field}", "expected": baseline_unit["slice"][field], "actual": unit["slice"][field]})
        sort = lambda edges: sorted(edges, key=lambda e: json.dumps(e, sort_keys=True))
        if sort(unit["edges"]) != sort(baseline_unit["edges"]):
            errors.append({"path": "unit.edges", "expected": sort(baseline_unit["edges"]), "actual": sort(unit["edges"])})
        return {"status": "PASS" if independent["status"] == "PASS" and not errors else "FAIL",
                "independent_oracle": independent, "baseline_differences": errors,
                "scope": "delivered structure, object provenance, bindings/calls/assumptions, slice and VU; explicit hardware projection"}
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        return {"status": "UNKNOWN", "reason": str(error)}


def compare_equivalence(left_dir, left_oracle, right_dir, right_oracle):
    try:
        _, left = actual_artifacts(left_dir, left_oracle)
        _, right = actual_artifacts(right_dir, right_oracle)
        actual, expected = canonical_unit(left), canonical_unit(right)
        return {"status": "PASS" if actual == expected else "FAIL", "actual": actual, "expected": expected,
                "scope": "actual team VUs, source metadata and event IDs normalized"}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"status": "UNKNOWN", "reason": str(error)}


def query_specs(entry, oracle, root):
    if entry["suite"] == "internal":
        arch = read(root / entry["architecture_oracle"])
        # Only unmodified-source queries here; injected fence variants are
        # separate controls, never evidence for the original input.
        return [{"id": q["id"], "event_values": {o["event"]: o["value"] for o in q["target"]},
                 "expected": q["expected"]} for q in arch["queries"] if not arch["variants"][q["variant"]]["fences"]]
    observations = {}
    for item in oracle["outcome"]:
        events = oracle["threads"][item["thread"]]["events"]
        matches = [i for i, e in enumerate(events) if e["kind"] == "Load" and e["object"] == item["object"]]
        index = matches[item.get("occurrence", 0)]
        observations[f"T{item['thread']}:E{index}"] = item["value"]
    return [{"id": "original_target", "event_values": observations, "expected": oracle["expected_observations"]}]


def compare_queries(directory, specs):
    try:
        rows = [row for unit in read(directory / "manifest.json")["units"]
                for row in read(directory / "backend" / unit["id"] / "outcome_matrix.json")["outcomes"]
                if "query_id" in row]
        graph = read(directory / "frontend/input/event_ir.json")
        targets = {e["id"]: e["target"] for e in graph["events"] if e["kind"] == "Load"}
        if len(rows) != len(specs) or {r["query_id"] for r in rows} != {s["id"] for s in specs}:
            return {"status": "FAIL", "reason": "targeted_query_coverage_differs"}
        results = []
        for spec in specs:
            row = next(r for r in rows if r["query_id"] == spec["id"])
            target = {targets[e]: v for e, v in spec["event_values"].items()}
            for arch in ("x86", "riscv"):
                actual = row["architectures"][arch]
                status = ("FAIL" if actual["status"] == "FAILED" else "UNKNOWN" if actual["status"] != "RAN"
                          else "PASS" if actual["observation"] == spec["expected"][arch] and row["outcome"] == target else "FAIL")
                results.append({"query": spec["id"], "architecture": arch, "expected": spec["expected"][arch],
                                "actual": actual.get("observation"), "status": status})
        statuses = [r["status"] for r in results]
        status = "FAIL" if "FAIL" in statuses else "UNKNOWN" if not statuses or "UNKNOWN" in statuses else "PASS"
        return {"status": status, "queries": results, "scope": "original-input targeted hardware projections"}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"status": "UNKNOWN", "reason": str(error)}
