"""Phase 1 MVP operating core — vision §9 acceptance."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from sios import PHASE
from sios.digest import build_digest, compliance_calendar
from sios.gates import decide_review, build_review_context, package_hash, transition_guard
from sios.packs import LIVE_PACKS, list_live_packs, load_pack
from sios.sla import filing_status
from sios.store import open_store
from sios.workflow import (
    checklist_progress,
    ensure_invoice_ready_package,
    human_terminal_action,
    review_package,
    run_incorporation_demo,
    submit_for_review,
)


AS_OF = date(2026, 11, 15)


def test_phase_constant() -> None:
    assert PHASE.startswith("1")


def test_three_live_packs_load() -> None:
    rows = list_live_packs()
    assert {r["pack"] for r in rows} == set(LIVE_PACKS)
    for pack_id in LIVE_PACKS:
        data = load_pack(pack_id)
        assert data["checklists"]
        assert data.get("is_synthetic_playbook") is True


def test_store_expands_incorporation_checklist() -> None:
    store = open_store()
    eng = store.engagement("E-505")
    assert eng.pack == "corp-sec"
    assert eng.checklist_key == "incorporation_package"
    ids = {t.checklist_id for t in eng.tasks if t.checklist_id}
    assert "name_availability" in ids
    assert "bizfile_pack_review_gate" in ids
    assert "lodge_human" in ids
    assert any(t.needs_review_gate for t in eng.tasks)
    assert any(t.human_only for t in eng.tasks)


def test_clients_labeled_synthetic() -> None:
    store = open_store()
    assert store.is_synthetic is True
    for client in store.clients:
        assert client.is_synthetic is True
        assert "SYN" in client.name.upper()
        assert "SYNTHETIC" in client.display_name


def test_corp_sec_calendar_agm_ar_gst() -> None:
    store = open_store()
    rows = compliance_calendar(store, as_of=AS_OF, within_days=60)
    types = {r["type"] for r in rows}
    assert "annual_return" in types
    assert "agm" in types
    assert "gst_submission" in types
    by_id = {r["event_id"]: r for r in rows}
    assert by_id["CE-01"]["due_at"] == "2026-11-30"
    assert by_id["CE-02"]["due_at"] == "2026-12-15"
    assert by_id["CE-03"]["due_at"] == "2026-11-28"
    assert by_id["CE-01"]["filing_status"] in {"due_14", "due_30", "due_7"}


def test_filing_status_deterministic() -> None:
    from sios.model import ComplianceEvent

    event = ComplianceEvent(
        event_id="X", type="annual_return", due_at="2026-11-20", status="upcoming"
    )
    assert filing_status(event, as_of=AS_OF) == "due_7"
    event.status = "lodged"
    assert filing_status(event, as_of=AS_OF) == "lodged"


def test_incorporation_end_to_end_on_synthetic() -> None:
    store = open_store()
    result = run_incorporation_demo(store, reviewer_id="U-002")
    assert result["is_synthetic"] is True
    assert result["lodged"]["persisted"] is True
    package = result["package"]
    assert package["status"] == "LODGED"
    assert package["gate_kind"] == "filing_pack_ready"
    progress = checklist_progress(store, "E-505")
    assert progress["steps_total"] >= 8
    lodged_event = next(e for e in store.compliance if e.event_id == "CE-04")
    assert lodged_event.status == "lodged"


def test_llm_cannot_mark_filing_lodged() -> None:
    store = open_store()
    run_incorporation_demo(store, reviewer_id="U-002")
    # Reset package to READY_TO_LODGE to retry with LLM
    package_id = next(iter(store.deliverable_packages))
    store.deliverable_packages[package_id]["status"] = "READY_TO_LODGE"
    denied = human_terminal_action(
        store,
        package_id=package_id,
        actor_id="llm-bot",
        actor_type="LLM",
        terminal="LODGED",
    )
    assert denied["persisted"] is False
    assert denied["guard"]["reason_code"] == "LLM_CANNOT_MARK_TERMINAL"


def test_llm_cannot_mark_invoice_issued() -> None:
    store = open_store()
    package = ensure_invoice_ready_package(store, eng_id="E-502", actor_id="U-005")
    reviewed = review_package(
        store, package_id=package["package_id"], reviewer_id="U-003", intent="APPROVE"
    )
    assert reviewed["persisted"] is True
    denied = human_terminal_action(
        store,
        package_id=package["package_id"],
        actor_id="agent-1",
        actor_type="AGENT",
        terminal="ISSUED",
    )
    assert denied["persisted"] is False
    assert denied["guard"]["decision"] == "DENY"
    allowed = human_terminal_action(
        store,
        package_id=package["package_id"],
        actor_id="U-003",
        actor_type="HUMAN",
        terminal="ISSUED",
    )
    assert allowed["persisted"] is True
    assert allowed["package"]["status"] == "ISSUED"


def test_principal_digest_no_news_apis() -> None:
    digest = build_digest(open_store(), as_of=AS_OF)
    assert digest["is_synthetic"] is True
    assert digest["news_apis_called"] is False
    assert "due_7" in digest and "due_14" in digest and "due_30" in digest
    assert digest["at_risk_engagements"]
    # Digest module must not import quarantined acquisition.
    import sios.digest as digest_mod

    source = Path(digest_mod.__file__).read_text(encoding="utf-8")
    assert "grit.acquisition" not in source
    assert "brave" not in source.lower()
    assert "gdelt" not in source.lower()


def test_hr_and_accounting_packs_expand() -> None:
    store = open_store()
    hr = store.engagement("E-504")
    assert hr.checklist_key == "policy_suite"
    assert any(t.checklist_id == "draft_handbook" for t in hr.tasks)
    assert any(t.gate_kind == "policy_final" for t in hr.tasks if t.needs_review_gate)
    acct = store.engagement("E-502")
    assert acct.checklist_key == "monthly_close"
    assert any(t.checklist_id for t in acct.tasks)


def test_reviewgate_adapter_approve() -> None:
    payload = {"package_id": "PKG-X", "gate_kind": "filing_pack_ready", "is_synthetic": True}
    ph = package_hash(payload)
    mh = package_hash({"members": ["T-1"]})
    ctx = build_review_context(
        package_id="PKG-X",
        package_version=1,
        package_hash=ph,
        membership_hash=mh,
        reviewer_id="U-002",
        reviewer_intent="APPROVE",
        gate_kind="filing_pack_ready",
    )
    decision = decide_review(ctx)
    assert decision["review_outcome"] == "APPROVE"
    guard = transition_guard(
        {
            "current_state": "PENDING_REVIEW",
            "requested_state": "APPROVED",
            "actor_type": "HUMAN",
            "reviewgate_outcome": "APPROVE",
            "approval_eligible": True,
            "reviewer_is_human": True,
        }
    )
    assert guard["decision"] == "ALLOW"


def test_submit_accounting_fs_send_gate() -> None:
    store = open_store()
    eng = store.engagement("E-502")
    gate_task = next(t for t in eng.tasks if t.needs_review_gate)
    package = submit_for_review(
        store, eng_id="E-502", task_id=gate_task.task_id, actor_id="U-005", actor_type="HUMAN"
    )
    assert package["status"] == "PENDING_REVIEW"
    assert package["gate_kind"] in {"fs_send", "gst_ready", "filing_pack_ready"}
