"""In-memory Bradbury SIOS operating store seeded from synthetic fixtures."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

from sios.model import (
    ApprovalRecord,
    Client,
    ComplianceEvent,
    DocumentMeta,
    Engagement,
    Task,
    TaskEvent,
)
from sios.packs import LIVE_PACKS, checklist_key_for, checklist_steps
from sios.sla import engagement_is_at_risk, filing_status
from sios.synthetic import DISCLAIMER, load_all, summary


class OperatingStore:
    """Mutable operating view. Fixtures remain the seed source of truth."""

    def __init__(self, bundle: dict[str, Any] | None = None):
        self.bundle = bundle or load_all()
        if self.bundle.get("is_synthetic") is not True:
            raise ValueError("OperatingStore refuses non-synthetic bundles")
        self.disclaimer = self.bundle.get("disclaimer") or DISCLAIMER
        self.is_synthetic = True
        self.users = list(self.bundle["org_users"].get("users") or [])
        self.legal_entities = list(self.bundle["org_users"].get("legal_entities") or [])
        self.role_catalog = list(self.bundle["org_users"].get("role_catalog") or [])
        self.clients = [
            Client(
                client_id=row["client_id"],
                name=row["name"],
                industry=row.get("industry") or "",
                jurisdiction=row.get("jurisdiction") or "",
                uen_synthetic=row.get("uen_synthetic") or "",
                contacts=list(row.get("contacts") or []),
                is_synthetic=True,
            )
            for row in self.bundle["clients_engagements"].get("clients") or []
        ]
        self.engagements: list[Engagement] = []
        self.documents: list[DocumentMeta] = []
        self.compliance: list[ComplianceEvent] = []
        self.approvals: list[ApprovalRecord] = []
        self.task_events: list[TaskEvent] = []
        self.deliverable_packages: dict[str, dict[str, Any]] = {}
        self._load_engagements()
        self._load_calendar_docs()
        self.expand_live_pack_checklists()

    def _load_engagements(self) -> None:
        for row in self.bundle["clients_engagements"].get("engagements") or []:
            tasks = [
                Task(
                    task_id=task["task_id"],
                    title=task["title"],
                    assignee=task.get("assignee") or "",
                    due=task.get("due"),
                    status=task.get("status") or "open",
                    needs_review_gate=bool(task.get("needs_review_gate")),
                    human_only=bool(task.get("human_only")),
                    gate_kind=task.get("gate_kind"),
                    eng_id=row["eng_id"],
                    pack=row.get("pack") or "",
                )
                for task in row.get("tasks") or []
            ]
            fee_bits = []
            if row.get("fee_synthetic_sgd_monthly") is not None:
                fee_bits.append(f"S${row['fee_synthetic_sgd_monthly']}/mo (synthetic)")
            if row.get("fee_synthetic_sgd_fixed") is not None:
                fee_bits.append(f"S${row['fee_synthetic_sgd_fixed']} fixed (synthetic)")
            if row.get("fee_synthetic_note"):
                fee_bits.append(str(row["fee_synthetic_note"]))
            self.engagements.append(
                Engagement(
                    eng_id=row["eng_id"],
                    client_id=row["client_id"],
                    pack=row.get("pack") or "",
                    type=row.get("type") or "",
                    owner_user_id=row.get("owner_user_id") or "",
                    status=row.get("status") or "active",
                    legal_entity_id=row.get("legal_entity_id") or "ORG-BC",
                    tasks=tasks,
                    fee_note="; ".join(fee_bits),
                    package_name=row.get("package_name_synthetic") or "",
                    checklist_key=checklist_key_for(row.get("pack") or "", row.get("type") or ""),
                    is_synthetic=True,
                )
            )

    def _load_calendar_docs(self) -> None:
        cal = self.bundle["calendar_kpis_docs"]
        for row in cal.get("compliance_events") or []:
            event = ComplianceEvent(
                event_id=row["event_id"],
                type=row.get("type") or "",
                due_at=row.get("due_at") or "",
                status=row.get("status") or "upcoming",
                client_id=row.get("client_id"),
                eng_id=row.get("eng_id"),
                owner_user_id=row.get("owner_user_id") or "",
                legal_entity_id=row.get("legal_entity_id"),
                needs_review_gate=bool(row.get("needs_review_gate")),
                note=row.get("note") or "",
                is_synthetic=True,
            )
            event.filing_status = filing_status(event, as_of=date(2026, 11, 15))
            self.compliance.append(event)
        for row in cal.get("sample_documents") or []:
            self.documents.append(
                DocumentMeta(
                    doc_id=row["doc_id"],
                    doc_type=row.get("doc_type") or "",
                    eng_id=row.get("eng_id") or "",
                    filename=row.get("filename") or "",
                    status=row.get("status") or "draft",
                    uploaded_by=row.get("uploaded_by") or "",
                    is_synthetic=True,
                )
            )
        self.kpis = list(cal.get("kpis") or [])
        self.document_types = list(cal.get("document_types") or [])

    def expand_live_pack_checklists(self) -> None:
        """Materialize pack checklist steps onto live-pack engagements."""
        for eng in self.engagements:
            if eng.pack not in LIVE_PACKS:
                continue
            key = eng.checklist_key
            if not key:
                continue
            steps = checklist_steps(eng.pack, key)
            existing_by_checklist = {t.checklist_id: t for t in eng.tasks if t.checklist_id}
            existing_titles = {t.title.lower(): t for t in eng.tasks}
            for index, step in enumerate(steps, start=1):
                step_id = step["id"]
                title = step.get("title") or step_id
                if step_id in existing_by_checklist:
                    task = existing_by_checklist[step_id]
                elif title.lower() in existing_titles:
                    task = existing_titles[title.lower()]
                    task.checklist_id = step_id
                else:
                    # Prefer matching seed tasks by ReviewGate flag or shared keywords.
                    matched = None
                    step_tokens = {
                        tok
                        for tok in (step_id.replace("_", " ") + " " + title).lower().replace("/", " ").split()
                        if len(tok) > 2
                    }
                    for task in eng.tasks:
                        if task.checklist_id:
                            continue
                        if step.get("needs_review_gate") and task.needs_review_gate:
                            matched = task
                            break
                        task_tokens = {
                            tok for tok in task.title.lower().replace("/", " ").replace("-", " ").split() if len(tok) > 2
                        }
                        if step_tokens & task_tokens and len(step_tokens & task_tokens) >= 1:
                            # Require a distinctive token (kyc, gst, handbook, etc.) when only one overlap.
                            distinctive = step_tokens & task_tokens
                            if distinctive - {"pack", "draft", "review", "client", "and", "the"}:
                                matched = task
                                break
                    if matched:
                        task = matched
                        task.checklist_id = step_id
                        if not task.title:
                            task.title = title
                    else:
                        task = Task(
                            task_id=f"{eng.eng_id}-CK{index:02d}",
                            title=title,
                            assignee=eng.owner_user_id,
                            due=None,
                            status="open",
                            checklist_id=step_id,
                            eng_id=eng.eng_id,
                            pack=eng.pack,
                        )
                        eng.tasks.append(task)
                task.needs_review_gate = bool(step.get("needs_review_gate") or task.needs_review_gate)
                task.human_only = bool(step.get("human_only") or task.human_only)
                task.gate_kind = step.get("gate_kind") or task.gate_kind
                task.pack = eng.pack
                task.eng_id = eng.eng_id

    def client_map(self) -> dict[str, Client]:
        return {c.client_id: c for c in self.clients}

    def engagement(self, eng_id: str) -> Engagement:
        for eng in self.engagements:
            if eng.eng_id == eng_id:
                return eng
        raise KeyError(eng_id)

    def all_tasks(self) -> list[Task]:
        return [task for eng in self.engagements for task in eng.tasks]

    def live_engagements(self) -> list[Engagement]:
        return [e for e in self.engagements if e.pack in LIVE_PACKS]

    def at_risk(self, *, as_of: date | None = None) -> list[Engagement]:
        return [e for e in self.engagements if engagement_is_at_risk(e, as_of=as_of)]

    def refresh_filing_statuses(self, *, as_of: date | None = None) -> None:
        as_of = as_of or date.today()
        for event in self.compliance:
            event.filing_status = filing_status(event, as_of=as_of)

    def counts(self) -> dict[str, int]:
        base = summary(self.bundle)
        base["tasks"] = len(self.all_tasks())
        base["documents"] = len(self.documents)
        base["approvals"] = len(self.approvals)
        return base

    def snapshot(self) -> dict[str, Any]:
        return {
            "is_synthetic": True,
            "disclaimer": self.disclaimer,
            "counts": self.counts(),
            "deliverable_packages": copy.deepcopy(self.deliverable_packages),
            "approvals": [a.__dict__ for a in self.approvals],
            "task_events": [e.__dict__ for e in self.task_events],
        }


def open_store(bundle: dict[str, Any] | None = None) -> OperatingStore:
    return OperatingStore(bundle)
