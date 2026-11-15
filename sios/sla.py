"""Deterministic SLA / filing status — no LLM scores."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from sios.model import ComplianceEvent, Engagement, Task

AT_RISK_TASK_STATUSES = {"blocked", "waiting"}
OVERDUE_OPEN_STATUSES = {"open", "in_progress", "blocked", "waiting", "pending_review"}


def _parse_day(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def days_until(due: str | date | None, *, as_of: date | None = None) -> int | None:
    due_day = _parse_day(due)
    if due_day is None:
        return None
    return (due_day - (as_of or date.today())).days


def filing_status(event: ComplianceEvent | dict[str, Any], *, as_of: date | None = None) -> str:
    """Project a compliance/filing status from due date + recorded status only."""
    raw = event.status if isinstance(event, ComplianceEvent) else event.get("status", "")
    raw = (raw or "").lower()
    if raw in {"lodged", "filed", "completed", "done", "sent", "issued"}:
        return raw
    if raw in {"blocked_docs", "blocked"}:
        return "blocked"
    delta = days_until(
        event.due_at if isinstance(event, ComplianceEvent) else event.get("due_at"),
        as_of=as_of,
    )
    if delta is None:
        return "not_established"
    if delta < 0:
        return "overdue"
    if delta <= 7:
        return "due_7"
    if delta <= 14:
        return "due_14"
    if delta <= 30:
        return "due_30"
    return "upcoming"


def due_bucket(due: str | date | None, *, as_of: date | None = None) -> str | None:
    delta = days_until(due, as_of=as_of)
    if delta is None:
        return None
    if delta < 0:
        return "overdue"
    if delta <= 7:
        return "due_7"
    if delta <= 14:
        return "due_14"
    if delta <= 30:
        return "due_30"
    return "later"


def events_in_window(
    events: Iterable[ComplianceEvent],
    *,
    within_days: int,
    as_of: date | None = None,
    include_overdue: bool = True,
) -> list[ComplianceEvent]:
    as_of = as_of or date.today()
    out: list[ComplianceEvent] = []
    for event in events:
        delta = days_until(event.due_at, as_of=as_of)
        if delta is None:
            continue
        if delta > within_days:
            continue
        if delta < 0 and not include_overdue:
            continue
        out.append(event)
    return sorted(out, key=lambda row: row.due_at)


def engagement_is_at_risk(engagement: Engagement, *, as_of: date | None = None) -> bool:
    if engagement.status not in {"active", "proposed"}:
        return False
    as_of = as_of or date.today()
    for task in engagement.tasks:
        if task.status in AT_RISK_TASK_STATUSES:
            return True
        delta = days_until(task.due, as_of=as_of)
        if delta is not None and delta < 0 and task.status in OVERDUE_OPEN_STATUSES:
            return True
    return False


def capacity_by_practice(tasks: Iterable[Task], users: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Simple open-load by practice from assignee → user practice mapping."""
    practice_of = {u["user_id"]: u.get("practice") or "unassigned" for u in users}
    open_statuses = OVERDUE_OPEN_STATUSES | {"ready_for_review", "pending_review"}
    counts: dict[str, int] = {}
    for task in tasks:
        if task.status not in open_statuses:
            continue
        practice = practice_of.get(task.assignee) or task.pack or "unassigned"
        counts[practice] = counts.get(practice, 0) + 1
    return [{"practice": key, "open_tasks": counts[key]} for key in sorted(counts)]
