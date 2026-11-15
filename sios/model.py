"""Phase 1 operating-core views over synthetic Bradbury SIOS records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SYNTHETIC_LABEL = "SYNTHETIC"


@dataclass
class Client:
    client_id: str
    name: str
    industry: str = ""
    jurisdiction: str = ""
    uen_synthetic: str = ""
    contacts: list[dict[str, Any]] = field(default_factory=list)
    is_synthetic: bool = True

    @property
    def display_name(self) -> str:
        label = SYNTHETIC_LABEL if self.is_synthetic else ""
        return f"{self.name} [{label}]" if label else self.name


@dataclass
class Task:
    task_id: str
    title: str
    assignee: str = ""
    due: str | None = None
    status: str = "open"
    checklist_id: str | None = None
    needs_review_gate: bool = False
    human_only: bool = False
    gate_kind: str | None = None
    eng_id: str = ""
    pack: str = ""


@dataclass
class Engagement:
    eng_id: str
    client_id: str
    pack: str
    type: str
    owner_user_id: str
    status: str
    legal_entity_id: str = "ORG-BC"
    tasks: list[Task] = field(default_factory=list)
    fee_note: str = ""
    package_name: str = ""
    checklist_key: str | None = None
    is_synthetic: bool = True


@dataclass
class ComplianceEvent:
    event_id: str
    type: str
    due_at: str
    status: str
    client_id: str | None = None
    eng_id: str | None = None
    owner_user_id: str = ""
    legal_entity_id: str | None = None
    needs_review_gate: bool = False
    note: str = ""
    filing_status: str = ""  # deterministic projection
    is_synthetic: bool = True


@dataclass
class DocumentMeta:
    doc_id: str
    doc_type: str
    eng_id: str
    filename: str
    status: str
    uploaded_by: str = ""
    is_synthetic: bool = True


@dataclass
class ApprovalRecord:
    approval_id: str
    package_id: str
    gate_kind: str
    eng_id: str
    reviewer_id: str
    outcome: str
    package_status: str
    canonical_result_hash: str
    actor_type: str = "HUMAN"
    is_synthetic: bool = True


@dataclass
class TaskEvent:
    event_id: str
    task_id: str
    eng_id: str
    from_status: str
    to_status: str
    actor_id: str
    actor_type: str
    reason: str = ""


def row(obj: Any) -> dict[str, Any]:
    """Serialize a dataclass for tables / JSON."""
    return asdict(obj)
