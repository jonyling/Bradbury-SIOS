"""Engagement checklist workflow and governed approval / lodge / issue actions."""

from __future__ import annotations

from typing import Any

from sios.gates import (
    HUMAN_ONLY_TERMINALS,
    build_review_context,
    decide_review,
    package_hash,
    post_approve_state,
    transition_guard,
)
from sios.model import ApprovalRecord, TaskEvent
from sios.store import OperatingStore

_EVENT_SEQ = 0
_APPROVAL_SEQ = 0


def _next_event_id() -> str:
    global _EVENT_SEQ
    _EVENT_SEQ += 1
    return f"TE-{_EVENT_SEQ:04d}"


def _next_approval_id() -> str:
    global _APPROVAL_SEQ
    _APPROVAL_SEQ += 1
    return f"AP-{_APPROVAL_SEQ:04d}"


def checklist_progress(store: OperatingStore, eng_id: str) -> dict[str, Any]:
    eng = store.engagement(eng_id)
    steps = []
    done = 0
    for task in eng.tasks:
        if eng.checklist_key and not task.checklist_id and task.pack == eng.pack:
            # Include seed tasks even if not mapped.
            pass
        row = {
            "task_id": task.task_id,
            "checklist_id": task.checklist_id,
            "title": task.title,
            "status": task.status,
            "assignee": task.assignee,
            "due": task.due,
            "needs_review_gate": task.needs_review_gate,
            "human_only": task.human_only,
            "gate_kind": task.gate_kind,
        }
        if task.status == "done" or task.status in {"lodged", "sent", "issued", "approved"}:
            done += 1
        steps.append(row)
    return {
        "eng_id": eng.eng_id,
        "pack": eng.pack,
        "type": eng.type,
        "checklist_key": eng.checklist_key,
        "client_id": eng.client_id,
        "status": eng.status,
        "is_synthetic": True,
        "steps_total": len(steps),
        "steps_done": done,
        "steps": steps,
    }


def complete_task(
    store: OperatingStore,
    *,
    eng_id: str,
    task_id: str,
    actor_id: str,
    actor_type: str = "HUMAN",
) -> dict[str, Any]:
    """Mark a non-terminal checklist task complete. Human-only / ReviewGate steps refuse."""
    eng = store.engagement(eng_id)
    task = next((t for t in eng.tasks if t.task_id == task_id), None)
    if task is None:
        raise KeyError(task_id)
    if task.human_only:
        raise PermissionError("Human-only lodge/send steps cannot be completed via complete_task")
    if task.needs_review_gate and task.status not in {"approved", "ready_to_lodge", "ready_to_send"}:
        raise PermissionError("ReviewGate-required steps must go through submit_for_review / approve")
    if task.status == "done":
        return {"task_id": task_id, "status": "done", "unchanged": True}
    prior = task.status
    task.status = "done"
    store.task_events.append(
        TaskEvent(
            event_id=_next_event_id(),
            task_id=task_id,
            eng_id=eng_id,
            from_status=prior,
            to_status="done",
            actor_id=actor_id,
            actor_type=actor_type,
            reason="complete_task",
        )
    )
    return {"task_id": task_id, "status": "done", "is_synthetic": True}


def submit_for_review(
    store: OperatingStore,
    *,
    eng_id: str,
    task_id: str,
    actor_id: str,
    actor_type: str = "HUMAN",
) -> dict[str, Any]:
    """Create a pending ReviewGate package for a gate-required checklist step."""
    eng = store.engagement(eng_id)
    task = next((t for t in eng.tasks if t.task_id == task_id), None)
    if task is None:
        raise KeyError(task_id)
    if not task.needs_review_gate:
        raise ValueError(f"Task {task_id} does not require ReviewGate")
    gate_kind = task.gate_kind or "filing_pack_ready"
    package_id = f"PKG-{eng_id}-{task_id}"
    payload = {
        "package_id": package_id,
        "eng_id": eng_id,
        "task_id": task_id,
        "gate_kind": gate_kind,
        "client_id": eng.client_id,
        "pack": eng.pack,
        "title": task.title,
        "is_synthetic": True,
    }
    content_hash = package_hash(payload)
    membership_hash = package_hash({"members": [task_id], "eng_id": eng_id})
    prior = task.status
    task.status = "pending_review"
    package = {
        **payload,
        "package_version": 1,
        "package_hash": content_hash,
        "membership_hash": membership_hash,
        "status": "PENDING_REVIEW",
        "submitted_by": actor_id,
        "submitted_actor_type": actor_type,
    }
    store.deliverable_packages[package_id] = package
    store.task_events.append(
        TaskEvent(
            event_id=_next_event_id(),
            task_id=task_id,
            eng_id=eng_id,
            from_status=prior,
            to_status="pending_review",
            actor_id=actor_id,
            actor_type=actor_type,
            reason="submit_for_review",
        )
    )
    return package


def review_package(
    store: OperatingStore,
    *,
    package_id: str,
    reviewer_id: str,
    intent: str = "APPROVE",
    reviewer_is_human: bool = True,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run ReviewGate then TransitionGuard; persist only on ALLOW."""
    package = store.deliverable_packages.get(package_id)
    if package is None:
        raise KeyError(package_id)
    if package["status"] != "PENDING_REVIEW":
        raise ValueError(f"Package {package_id} is {package['status']}, not PENDING_REVIEW")

    context = build_review_context(
        package_id=package_id,
        package_version=int(package["package_version"]),
        package_hash=package["package_hash"],
        membership_hash=package["membership_hash"],
        reviewer_id=reviewer_id,
        reviewer_intent=intent,
        gate_kind=package["gate_kind"],
        package_current_status="PENDING_REVIEW",
        reviewer_is_human=reviewer_is_human,
        findings=findings,
    )
    decision = decide_review(context)
    outcome = decision["review_outcome"]
    status_map = {
        "APPROVE": "APPROVED",
        "REJECT": "REJECTED",
        "HOLD": "HELD",
        "RETURN_FOR_REWORK": "RETURNED_FOR_REWORK",
    }
    requested = status_map.get(outcome)
    if requested is None:
        return {"decision": decision, "persisted": False, "reason": "unmapped_outcome"}

    guard = transition_guard(
        {
            "current_state": "PENDING_REVIEW",
            "requested_state": requested,
            "actor_type": "HUMAN" if reviewer_is_human else "LLM",
            "actor_id": reviewer_id,
            "reviewgate_outcome": outcome,
            "approval_eligible": decision.get("approval_eligible"),
            "reviewer_is_human": reviewer_is_human,
            "prior_approval_present": False,
        }
    )
    if guard["decision"] != "ALLOW":
        return {"decision": decision, "guard": guard, "persisted": False}

    package["status"] = requested
    package["review_outcome"] = outcome
    package["canonical_result_hash"] = decision["canonical_result_hash"]

    eng = store.engagement(package["eng_id"])
    task = next(t for t in eng.tasks if t.task_id == package["task_id"])
    prior = task.status
    if outcome == "APPROVE":
        next_state = post_approve_state(package["gate_kind"])
        package["status"] = next_state
        task.status = next_state.lower()
        # Advance READY_* via guard when distinct from APPROVED.
        if next_state != "APPROVED":
            advance = transition_guard(
                {
                    "current_state": "APPROVED",
                    "requested_state": next_state,
                    "actor_type": "HUMAN",
                    "actor_id": reviewer_id,
                    "reviewgate_outcome": "APPROVE",
                    "approval_eligible": True,
                    "reviewer_is_human": True,
                    "prior_approval_present": True,
                }
            )
            if advance["decision"] != "ALLOW":
                package["status"] = "APPROVED"
                task.status = "approved"
        approval = ApprovalRecord(
            approval_id=_next_approval_id(),
            package_id=package_id,
            gate_kind=package["gate_kind"],
            eng_id=package["eng_id"],
            reviewer_id=reviewer_id,
            outcome=outcome,
            package_status=package["status"],
            canonical_result_hash=decision["canonical_result_hash"],
            actor_type="HUMAN",
            is_synthetic=True,
        )
        store.approvals.append(approval)
        package["approval_id"] = approval.approval_id
        package["prior_approval_present"] = True
    elif outcome == "RETURN_FOR_REWORK":
        task.status = "in_progress"
    elif outcome == "REJECT":
        task.status = "rejected"
    else:
        task.status = "held"

    store.task_events.append(
        TaskEvent(
            event_id=_next_event_id(),
            task_id=task.task_id,
            eng_id=eng.eng_id,
            from_status=prior,
            to_status=task.status,
            actor_id=reviewer_id,
            actor_type="HUMAN",
            reason=f"ReviewGate:{outcome}",
        )
    )
    return {"decision": decision, "guard": guard, "package": package, "persisted": True}


def human_terminal_action(
    store: OperatingStore,
    *,
    package_id: str,
    actor_id: str,
    actor_type: str,
    terminal: str,
) -> dict[str, Any]:
    """Mark LODGED / SENT / ISSUED. Refuses non-human actors (including LLM)."""
    terminal = terminal.upper()
    if terminal not in HUMAN_ONLY_TERMINALS:
        raise ValueError(f"Not a human-only terminal: {terminal}")
    package = store.deliverable_packages.get(package_id)
    if package is None:
        raise KeyError(package_id)
    current = package["status"]
    guard = transition_guard(
        {
            "current_state": current,
            "requested_state": terminal,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "reviewer_is_human": actor_type.upper() == "HUMAN",
            "prior_approval_present": bool(
                package.get("prior_approval_present") or package.get("approval_id")
            ),
        }
    )
    if guard["decision"] != "ALLOW":
        return {"guard": guard, "persisted": False, "package_status": current}

    package["status"] = terminal
    eng = store.engagement(package["eng_id"])
    task = next(t for t in eng.tasks if t.task_id == package["task_id"])
    prior = task.status
    task.status = terminal.lower()
    # Mirror onto related compliance event when lodging a filing.
    if terminal == "LODGED":
        for event in store.compliance:
            if event.eng_id == eng.eng_id and "incorporation" in event.type:
                event.status = "lodged"
                event.filing_status = "lodged"
    store.task_events.append(
        TaskEvent(
            event_id=_next_event_id(),
            task_id=task.task_id,
            eng_id=eng.eng_id,
            from_status=prior,
            to_status=task.status,
            actor_id=actor_id,
            actor_type=actor_type,
            reason=f"human_terminal:{terminal}",
        )
    )
    return {"guard": guard, "package": package, "persisted": True}


def ensure_invoice_ready_package(
    store: OperatingStore,
    *,
    eng_id: str,
    actor_id: str,
) -> dict[str, Any]:
    """Light-scope invoice_ready package for retainer/project fee approval demos."""
    eng = store.engagement(eng_id)
    package_id = f"PKG-{eng_id}-INVOICE"
    if package_id in store.deliverable_packages:
        return store.deliverable_packages[package_id]
    # Synthetic task for invoice gate.
    task_id = f"{eng_id}-INV"
    if not any(t.task_id == task_id for t in eng.tasks):
        from sios.model import Task

        eng.tasks.append(
            Task(
                task_id=task_id,
                title="Invoice ready for issue",
                assignee=eng.owner_user_id,
                status="pending_review",
                needs_review_gate=True,
                gate_kind="invoice_ready",
                eng_id=eng_id,
                pack=eng.pack,
            )
        )
    payload = {
        "package_id": package_id,
        "eng_id": eng_id,
        "task_id": task_id,
        "gate_kind": "invoice_ready",
        "client_id": eng.client_id,
        "pack": eng.pack,
        "title": "Invoice ready",
        "is_synthetic": True,
        "fee_note": eng.fee_note,
    }
    package = {
        **payload,
        "package_version": 1,
        "package_hash": package_hash(payload),
        "membership_hash": package_hash({"members": [task_id]}),
        "status": "PENDING_REVIEW",
        "submitted_by": actor_id,
        "submitted_actor_type": "HUMAN",
    }
    store.deliverable_packages[package_id] = package
    return package


def run_incorporation_demo(store: OperatingStore, *, reviewer_id: str = "U-002") -> dict[str, Any]:
    """End-to-end synthetic incorporation checklist on E-505 (vision §9)."""
    eng_id = "E-505"
    progress = checklist_progress(store, eng_id)
    # Complete non-gate, non-human steps that are still open.
    for step in progress["steps"]:
        task_id = step["task_id"]
        if step.get("human_only"):
            continue
        if step.get("needs_review_gate"):
            continue
        if step["status"] in {"done", "approved", "ready_to_lodge", "lodged"}:
            continue
        # Unblock KYC for the demo path.
        eng = store.engagement(eng_id)
        task = next(t for t in eng.tasks if t.task_id == task_id)
        if task.status == "blocked":
            task.status = "open"
        complete_task(store, eng_id=eng_id, task_id=task_id, actor_id="U-009", actor_type="HUMAN")

    # Submit BizFile ReviewGate step.
    eng = store.engagement(eng_id)
    gate_task = next(t for t in eng.tasks if t.needs_review_gate)
    if gate_task.status == "waiting":
        gate_task.status = "open"
    package = submit_for_review(
        store, eng_id=eng_id, task_id=gate_task.task_id, actor_id="U-009", actor_type="HUMAN"
    )
    reviewed = review_package(
        store, package_id=package["package_id"], reviewer_id=reviewer_id, intent="APPROVE"
    )
    lodged = human_terminal_action(
        store,
        package_id=package["package_id"],
        actor_id=reviewer_id,
        actor_type="HUMAN",
        terminal="LODGED",
    )
    # Complete remaining human lodge checklist id if distinct.
    for task in eng.tasks:
        if task.human_only and task.status not in {"lodged", "done"}:
            task.status = "lodged"
    return {
        "eng_id": eng_id,
        "is_synthetic": True,
        "progress_after": checklist_progress(store, eng_id),
        "package": store.deliverable_packages.get(package["package_id"]),
        "reviewed": reviewed,
        "lodged": lodged,
    }
