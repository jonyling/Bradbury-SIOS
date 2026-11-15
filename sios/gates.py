"""SIOS approval gates: ReviewGate DNA + operational TransitionGuard.

Agents propose. Deterministic functions decide. A named human approves.

No LLM / agent actor may transition a filing to LODGED or an invoice to ISSUED.
"""

from __future__ import annotations

from typing import Any

from grit.core.canonical import canonical_hash
from grit.core.review_gate import review_gate

FUNCTION_NAME = "SIOSTransitionGuard"
FUNCTION_VERSION = "1.0.0"

GATE_KINDS = {
    "filing_pack_ready",
    "fs_send",
    "gst_ready",
    "policy_final",
    "invoice_ready",
}

# Operational states for deliverable / filing / invoice packages.
STATES = {
    "DRAFT",
    "IN_PROGRESS",
    "PENDING_REVIEW",
    "APPROVED",
    "READY_TO_LODGE",
    "READY_TO_SEND",
    "LODGED",
    "SENT",
    "ISSUED",
    "REJECTED",
    "RETURNED_FOR_REWORK",
    "HELD",
}

HUMAN_ONLY_TERMINALS = {"LODGED", "SENT", "ISSUED"}
NON_HUMAN_ACTORS = {"LLM", "AGENT", "AUTOMATION", "BOT"}

EDGES = {
    ("DRAFT", "IN_PROGRESS"): "ADVANCE",
    ("IN_PROGRESS", "PENDING_REVIEW"): "ADVANCE",
    ("DRAFT", "PENDING_REVIEW"): "ADVANCE",
    ("PENDING_REVIEW", "APPROVED"): "HUMAN_APPROVAL",
    ("PENDING_REVIEW", "REJECTED"): "HUMAN_APPROVAL",
    ("PENDING_REVIEW", "HELD"): "HUMAN_APPROVAL",
    ("PENDING_REVIEW", "RETURNED_FOR_REWORK"): "HUMAN_APPROVAL",
    ("APPROVED", "READY_TO_LODGE"): "ADVANCE",
    ("APPROVED", "READY_TO_SEND"): "ADVANCE",
    ("READY_TO_LODGE", "LODGED"): "HUMAN_ONLY",
    ("APPROVED", "LODGED"): "HUMAN_ONLY",
    ("READY_TO_SEND", "SENT"): "HUMAN_ONLY",
    ("APPROVED", "SENT"): "HUMAN_ONLY",
    ("APPROVED", "ISSUED"): "HUMAN_ONLY",
    ("READY_TO_SEND", "ISSUED"): "HUMAN_ONLY",
    ("RETURNED_FOR_REWORK", "IN_PROGRESS"): "ADVANCE",
    ("RETURNED_FOR_REWORK", "DRAFT"): "ADVANCE",
    ("HELD", "PENDING_REVIEW"): "ADVANCE",
}

POST_APPROVE_BY_GATE = {
    "filing_pack_ready": "READY_TO_LODGE",
    "fs_send": "READY_TO_SEND",
    "gst_ready": "READY_TO_SEND",
    "policy_final": "APPROVED",
    "invoice_ready": "APPROVED",
}


def build_review_context(
    *,
    package_id: str,
    package_version: int,
    package_hash: str,
    membership_hash: str,
    reviewer_id: str,
    reviewer_intent: str,
    gate_kind: str,
    package_current_status: str = "PENDING_REVIEW",
    reviewer_is_human: bool = True,
    reviewer_is_eligible: bool = True,
    separation_of_duties_passed: bool = True,
    findings: list[dict[str, Any]] | None = None,
    correlation_id: str = "sios-review",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    if gate_kind not in GATE_KINDS:
        raise ValueError(f"Unknown gate_kind: {gate_kind}")
    return {
        "review_package_id": package_id,
        "review_package_version": package_version,
        "review_package_hash": package_hash,
        "reviewer_id": reviewer_id,
        "reviewer_intent": reviewer_intent,
        "review_findings": findings or [],
        "review_timestamp_utc": "1970-01-01T00:00:00Z",
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key or f"{package_id}:{package_version}:{reviewer_intent}",
        "authoritative_package_hash": package_hash,
        "authoritative_membership_hash": membership_hash,
        "submitted_membership_hash": membership_hash,
        "package_current_status": package_current_status,
        "package_completeness_known": True,
        "missing_signal_ids": [],
        "reviewer_is_human": reviewer_is_human,
        "reviewer_is_eligible": reviewer_is_eligible,
        "separation_of_duties_passed": separation_of_duties_passed,
        "policy_is_active": True,
        "approval_policy_version": "sios-1",
        "configuration_version": "sios-1",
        "function_version": "1.0.0",
        "gate_kind": gate_kind,
    }


def decide_review(context: dict[str, Any]) -> dict[str, Any]:
    """Invoke grit ReviewGate — sole business approval gate for SIOS deliverable packs."""
    result = review_gate(context)
    result = dict(result)
    result["gate_kind"] = context.get("gate_kind")
    return result


def package_hash(payload: dict[str, Any]) -> str:
    return canonical_hash(payload)


def transition_guard(envelope: dict[str, Any]) -> dict[str, Any]:
    """Pure SIOS TransitionGuard. Does not read or write store state."""
    current = envelope.get("current_state")
    requested = envelope.get("requested_state")
    actor_type = str(envelope.get("actor_type") or "").upper()
    edge = (current, requested)
    input_hash = canonical_hash({k: envelope.get(k) for k in sorted(envelope) if k != "invocation_id"})

    def deny(reason_code: str) -> dict[str, Any]:
        return {
            "function_name": FUNCTION_NAME,
            "function_version": FUNCTION_VERSION,
            "decision": "DENY",
            "reason_code": reason_code,
            "current_state": current,
            "requested_state": requested,
            "input_hash": input_hash,
            "canonical_result_hash": canonical_hash(
                {"decision": "DENY", "reason_code": reason_code, "edge": list(edge)}
            ),
        }

    if current not in STATES or requested not in STATES:
        return deny("UNKNOWN_STATE")
    if edge not in EDGES:
        return deny("EDGE_NOT_PERMITTED")

    if requested in HUMAN_ONLY_TERMINALS:
        if actor_type in NON_HUMAN_ACTORS:
            return deny("LLM_CANNOT_MARK_TERMINAL")
        if actor_type != "HUMAN":
            return deny("HUMAN_REQUIRED_FOR_TERMINAL")
        if envelope.get("reviewer_is_human") is False:
            return deny("HUMAN_REQUIRED_FOR_TERMINAL")

    transition_class = EDGES[edge]
    if transition_class == "HUMAN_APPROVAL":
        if envelope.get("reviewgate_outcome") is None:
            return deny("REVIEWGATE_REQUIRED")
        outcome = envelope.get("reviewgate_outcome")
        expected = {
            "APPROVED": "APPROVE",
            "REJECTED": "REJECT",
            "HELD": "HOLD",
            "RETURNED_FOR_REWORK": "RETURN_FOR_REWORK",
        }.get(requested)
        if expected and outcome != expected:
            return deny("REVIEWGATE_OUTCOME_MISMATCH")
        if requested == "APPROVED" and envelope.get("approval_eligible") is not True:
            return deny("APPROVAL_NOT_ELIGIBLE")

    if transition_class == "HUMAN_ONLY" and actor_type != "HUMAN":
        return deny("HUMAN_REQUIRED_FOR_TERMINAL")

    # Filing lodge / invoice issue require prior approval evidence when leaving APPROVED/READY_*.
    if requested in {"LODGED", "ISSUED", "SENT"}:
        if envelope.get("prior_approval_present") is not True:
            return deny("PRIOR_APPROVAL_REQUIRED")

    return {
        "function_name": FUNCTION_NAME,
        "function_version": FUNCTION_VERSION,
        "decision": "ALLOW",
        "reason_code": "PERMITTED",
        "current_state": current,
        "requested_state": requested,
        "transition_class": transition_class,
        "input_hash": input_hash,
        "canonical_result_hash": canonical_hash(
            {"decision": "ALLOW", "edge": list(edge), "transition_class": transition_class}
        ),
    }


def post_approve_state(gate_kind: str) -> str:
    return POST_APPROVE_BY_GATE.get(gate_kind, "APPROVED")
