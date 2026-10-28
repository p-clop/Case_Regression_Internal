"""Validate independent obligations and keep review decisions separate from runs."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from fifo_oracle import FIFO_CONTRACT
from record_oracle import RECORD_CONTRACT
from spinlock_protocol import PROTOCOL_CONTRACT


def aggregate(states):
    states = list(states)
    return "FAIL" if "FAIL" in states else "PASS" if states and all(s == "PASS" for s in states) else "UNKNOWN"


def input_snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()
            and "build" not in p.relative_to(root).parts and "__pycache__" not in p.parts
            and p.suffix in (".c", ".h", ".py", ".json", ".litmus", ".md", ".sh", ".txt")}


def subject_hash(snapshot):
    # Review records are excluded so adding a review does not invalidate itself.
    inputs = {k: v for k, v in snapshot.items() if Path(k).name != "reviews.json"}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def validate_contract(root, case):
    oracle = json.loads((root / case / "oracle.json").read_text())
    if not isinstance(oracle, dict) or oracle.get("schema") != "engineering-benchmark-2" or oracle.get("case") != case:
        raise ValueError(f"{case}: invalid correctness contract version or case identity")
    if not isinstance(oracle.get("projections"), dict) or not oracle["projections"]:
        raise ValueError(f"{case}: missing projection expectations")
    if not all(isinstance(oracle.get(k), str) and oracle[k].strip()
               for k in ("behavior_oracle", "full_program_reason")):
        raise ValueError(f"{case}: missing basis status or verification boundary")
    native = oracle.get("native")
    if case == "B01_spsc_ring" and oracle.get("fifo_contract") != FIFO_CONTRACT:
        raise ValueError(f"{case}: missing or changed independent FIFO formula/trace contract")
    if case == "B02_spinlock":
        if oracle.get("record_contract") != RECORD_CONTRACT:
            raise ValueError(f"{case}: missing or changed independent record formula/trace contract")
        if oracle.get("protocol_contract") != PROTOCOL_CONTRACT:
            raise ValueError(f"{case}: missing or changed bounded protocol contract")
    if not isinstance(native, dict):
        raise ValueError(f"{case}: missing native expectations")
    for key, code, status in (("baseline", 0, "PASS"), ("checker_corruption", 1, "FAIL"),
                              ("invalid_configuration", 2, None)):
        expectation = native.get(key)
        if (not isinstance(expectation, dict) or expectation.get("returncode") != code
                or (status and expectation.get("status") != status)):
            raise ValueError(f"{case}: invalid native expectation {key}")
    references = oracle.get("references", {})
    obligations = oracle.get("obligations", [])
    if not isinstance(references, dict) or not references or not isinstance(obligations, list) or not obligations:
        raise ValueError(f"{case}: independent references and obligations are required")
    for key, ref in references.items():
        if not isinstance(ref, dict) or not all(isinstance(ref.get(k), str) and ref[k].strip()
                   for k in ("title", "url", "version", "sections")):
            raise ValueError(f"{case}: incomplete reference {key}")
    ids, projections = set(), []
    for obligation in obligations:
        if not isinstance(obligation, dict):
            raise ValueError(f"{case}: invalid obligation record")
        oid = obligation.get("id")
        if not isinstance(oid, str) or not oid or oid in ids:
            raise ValueError(f"{case}: missing or duplicate obligation id")
        ids.add(oid)
        for key in ("requirement", "risk", "reasoning", "native_scope", "next_action"):
            if not isinstance(obligation.get(key), str) or not obligation[key].strip():
                raise ValueError(f"{oid}: missing {key}")
        for key in ("preconditions", "allowed", "forbidden", "references", "remaining_gaps"):
            values = obligation.get(key)
            if not isinstance(values, list) or not values or not all(isinstance(v, str) and v.strip() for v in values):
                raise ValueError(f"{oid}: missing or invalid {key}")
        if not set(obligation["references"]) <= references.keys():
            raise ValueError(f"{oid}: unknown reference")
        anchors = obligation.get("source_anchors", [])
        if not anchors:
            raise ValueError(f"{oid}: missing source anchors")
        for anchor in anchors:
            if (not isinstance(anchor, dict) or not isinstance(anchor.get("path"), str)
                    or not isinstance(anchor.get("symbol"), str) or not anchor["symbol"].strip()):
                raise ValueError(f"{oid}: invalid source anchor")
            path = (root / anchor["path"]).resolve()
            if not path.is_relative_to(root.resolve()) or anchor["symbol"] not in path.read_text():
                raise ValueError(f"{oid}: invalid source anchor {anchor}")
        kinds = obligation.get("native_kinds")
        checks = obligation.get("projection_checks")
        if not isinstance(kinds, list) or not set(kinds) <= {"baseline", "checker_control", "invalid_configuration"}:
            raise ValueError(f"{oid}: invalid native check selection")
        if not isinstance(checks, list) or not all(isinstance(c, str) for c in checks):
            raise ValueError(f"{oid}: invalid projection selection")
        projections.extend(checks)
    manifest = json.loads((root / "obligations_manifest.json").read_text())
    required = manifest["cases"][case]
    if manifest.get("schema") != "benchmark-obligations-1" or ids != set(required):
        raise ValueError(f"{case}: missing or unexpected obligation from fixed manifest")
    explanation = (root / case / "oracle.md").read_text()
    if any(oid not in explanation for oid in ids):
        raise ValueError(f"{case}: obligation missing from oracle.md")
    if len(projections) != len(set(projections)) or set(projections) != oracle["projections"].keys():
        raise ValueError(f"{case}: each declared projection must map to exactly one obligation")
    for projection, expectations in oracle["projections"].items():
        if (not isinstance(expectations, dict) or set(expectations) != {"x86", "riscv"}
                or not set(expectations.values()) <= {"Never", "Sometimes", "Always"}):
            raise ValueError(f"{case}: invalid model expectation {projection}")
        for isa in expectations:
            if not (root / case / "model" / f"{projection}.{isa}.litmus").is_file():
                raise ValueError(f"{case}: missing projection {projection}.{isa}")
    if oracle.get("review_file") != "reviews.json":
        raise ValueError(f"{case}: review_file must be reviews.json")
    variants = oracle.get("variants", {})
    if not isinstance(variants, dict) or set(variants) != {"baseline", "checker_corruption", "relaxed", "ordered", "source_problem_fix"}:
        raise ValueError(f"{case}: missing variant roles")
    if not all(isinstance(v, dict) and v.get("role") and v.get("limitation") for v in variants.values()):
        raise ValueError(f"{case}: incomplete variant roles")
    return oracle


def review_state(root, case, subject, target, expected=None, model_files=None):
    """A successful execution never creates a review or confirms its own oracle."""
    result = {"status": "UNKNOWN", "reason": "no_review_record",
              "next_action": "按对应义务复核依据与映射，记录真实评审意见及本次 subject_sha256。"}
    try:
        document = json.loads((root / case / "reviews.json").read_text())
        if (document.get("schema") != "benchmark-reviews-1" or document.get("case") != case
                or not isinstance(document.get("records"), list)):
            raise ValueError("invalid review document")
        records = [r for r in document["records"] if isinstance(r, dict) and r.get("target") == target]
        if not records:
            return result
        if len(records) != 1:
            result["reason"] = "conflicting_review_records"
            return result
        record = records[0]
        if record.get("decision") != "CONFIRMED":
            result["reason"] = "review_not_confirmed"
            return result
        if not all(isinstance(record.get(k), str) and record[k].strip()
                   for k in ("review_id", "reviewer", "reviewed_at", "rationale")):
            raise ValueError("incomplete review identity or rationale")
        reviewed = datetime.fromisoformat(record["reviewed_at"])
        if reviewed.tzinfo is None:
            raise ValueError("review date must include timezone")
        if record.get("subject_sha256") != subject:
            result["reason"] = "stale_review_inputs"
            return result
        if target != "behavior":
            if not model_files:
                result["reason"] = "review_model_not_available"
                return result
            if record.get("expected") != expected or record.get("model_files") != model_files:
                result["reason"] = "review_model_or_expectation_changed"
                return result
        return {"status": "CONFIRMED", "review_id": record["review_id"],
                "reviewer": record["reviewer"], "reviewed_at": record["reviewed_at"],
                "rationale": record["rationale"], "subject_sha256": subject}
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        result.update(reason="invalid_or_missing_review_file", detail=str(exc))
        return result


def attach_correctness(root, case, oracle, record, subject):
    behavior_review = review_state(root, case, subject, "behavior")
    for projection in record["projections"]:
        target = f"{projection['obligation']}.{projection['isa']}"
        review = review_state(root, case, subject, target, projection["expected"], projection.get("model_files"))
        projection.update(comparison_status=projection["status"], oracle_review=review["status"],
                          review=review)
        projection["model_conclusion"] = {
            "status": projection["status"] if review["status"] == "CONFIRMED" else "UNKNOWN",
            "scope": "declared_hardware_projection",
            "reason": (projection.get("reason") or "model_result_differs_from_oracle")
                      if review["status"] == "CONFIRMED" and projection["status"] != "PASS"
                      else (None if review["status"] == "CONFIRMED" else review["reason"])}
    obligations = []
    for obligation in oracle["obligations"]:
        native = [r for r in record["native"] if r["kind"] in obligation["native_kinds"]]
        projections = [p for p in record["projections"] if p["obligation"] in obligation["projection_checks"]]
        obligations.append({
            "id": obligation["id"], "requirement": obligation["requirement"],
            "native_checks": {"status": aggregate(r["status"] for r in native),
                              "scope": obligation["native_scope"],
                              "reason": None if native else "no_dedicated_native_check",
                              "logs": [r["stdout_log"] for r in native]},
            "projection_comparison": {"status": aggregate(p["status"] for p in projections),
                                      "targets": [f"{p['obligation']}.{p['isa']}" for p in projections],
                                      "reason": None if projections else "no_architecture_projection"},
            "full_verification": {"status": "UNKNOWN", "reason": "non_exhaustive_evidence",
                                  "remaining_gaps": obligation["remaining_gaps"],
                                  "next_action": obligation["next_action"]}})
        if obligation["id"] == "B02-MUTEX":
            obligations[-1]["bounded_protocol"] = {
                "comparison_status": record.get("protocol_status", "UNKNOWN"),
                "scope": PROTOCOL_CONTRACT["semantics"],
                "evidence": record.get("protocol", {}),
                "formal_review": "UNKNOWN"}
    record["correctness"] = {
        "subject_sha256": subject,
        "layers": {
            "structure": {"status": "UNKNOWN", "reason": "benchmark_frontend_not_integrated",
                          "next_action": "核心接口稳定后核对完整线程、对象、控制流、原子性及切片语义。"},
            "behavior": {"basis_status": "REVIEWED_WITH_EVIDENCE" if behavior_review["status"] == "CONFIRMED"
                         else oracle["behavior_oracle"], "review": behavior_review,
                         "native_comparison": record["native_status"]},
            "architecture": {"comparison_status": record["projection_status"],
                             "conclusion_status": aggregate(p["model_conclusion"]["status"] for p in record["projections"]),
                             "review_status": "CONFIRMED" if record["projections"] and all(
                                 p["oracle_review"] == "CONFIRMED" for p in record["projections"]) else "UNKNOWN",
                             "scope": "declared_hardware_projections_only"}},
        "obligations": obligations,
        "full_program": {"status": "UNKNOWN", "reason": oracle["full_program_reason"],
                         "next_action": "按义务清单补齐控制流、对象、多轮关系及 C-to-ISA 映射验证。"}}
    if case == "B02_spinlock":
        record["correctness"]["layers"]["behavior"]["bounded_protocol_comparison"] = record.get("protocol_status", "UNKNOWN")
