"""Principal digest from SIOS records only — never calls news APIs."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sios import PRODUCT_NAME, RULE
from sios.sla import capacity_by_practice, due_bucket, events_in_window
from sios.store import OperatingStore, open_store
from sios.synthetic import DISCLAIMER


def build_digest(store: OperatingStore | None = None, *, as_of: date | None = None) -> dict[str, Any]:
    """Deterministic Principal Monday-style brief over the operating store."""
    store = store or open_store()
    as_of = as_of or date.today()
    store.refresh_filing_statuses(as_of=as_of)
    clients = store.client_map()

    def client_label(client_id: str | None) -> str:
        if not client_id:
            return "—"
        client = clients.get(client_id)
        return client.display_name if client else client_id

    due = {7: [], 14: [], 30: []}
    for event in store.compliance:
        bucket = due_bucket(event.due_at, as_of=as_of)
        row = {
            "event_id": event.event_id,
            "type": event.type,
            "due_at": event.due_at,
            "status": event.status,
            "filing_status": event.filing_status,
            "client": client_label(event.client_id),
            "owner_user_id": event.owner_user_id,
            "is_synthetic": True,
        }
        if bucket == "due_7":
            due[7].append(row)
        if bucket in {"due_7", "due_14"}:
            due[14].append(row)
        if bucket in {"due_7", "due_14", "due_30"}:
            due[30].append(row)

    at_risk = []
    for eng in store.at_risk(as_of=as_of):
        at_risk.append(
            {
                "eng_id": eng.eng_id,
                "pack": eng.pack,
                "client": client_label(eng.client_id),
                "owner_user_id": eng.owner_user_id,
                "blocked_or_waiting": [
                    t.task_id for t in eng.tasks if t.status in {"blocked", "waiting"}
                ],
                "is_synthetic": True,
            }
        )

    pending_gates = [
        {
            "package_id": pkg["package_id"],
            "gate_kind": pkg["gate_kind"],
            "eng_id": pkg["eng_id"],
            "status": pkg["status"],
            "title": pkg.get("title"),
            "is_synthetic": True,
        }
        for pkg in store.deliverable_packages.values()
        if pkg.get("status") == "PENDING_REVIEW"
    ]

    return {
        "product": PRODUCT_NAME,
        "rule": RULE,
        "is_synthetic": True,
        "disclaimer": DISCLAIMER,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "as_of": as_of.isoformat(),
        "counts": store.counts(),
        "due_7": due[7],
        "due_14": due[14],
        "due_30": due[30],
        "at_risk_engagements": at_risk,
        "capacity": capacity_by_practice(store.all_tasks(), store.users),
        "pending_review_gates": pending_gates,
        "news_apis_called": False,
    }


def render_digest_text(digest: dict[str, Any]) -> str:
    lines = [
        digest["disclaimer"],
        f"{digest['product']} principal digest (synthetic)",
        f"Generated (UTC): {digest['generated_at_utc']} · as of {digest['as_of']}",
        (
            f"Clients: {digest['counts'].get('clients', 0)} · "
            f"Engagements: {digest['counts'].get('engagements', 0)} · "
            f"Users: {digest['counts'].get('users', 0)}"
        ),
        f"At-risk engagements: {len(digest['at_risk_engagements'])}",
    ]
    for eng in digest["at_risk_engagements"]:
        lines.append(
            f"  {eng['eng_id']}  pack={eng['pack']}  client={eng['client']}  owner={eng['owner_user_id']}"
        )
    lines.append("Due in 7 days:")
    for row in digest["due_7"] or ["  (none)"]:
        if isinstance(row, str):
            lines.append(row)
        else:
            lines.append(
                f"  {row['due_at']}  {row['type']}  {row['filing_status']}  {row['client']}"
            )
    lines.append("Due in 14 days:")
    for row in digest["due_14"]:
        lines.append(f"  {row['due_at']}  {row['type']}  {row['filing_status']}  {row['client']}")
    lines.append("Due in 30 days:")
    for row in digest["due_30"]:
        lines.append(f"  {row['due_at']}  {row['type']}  {row['filing_status']}  {row['client']}")
    lines.append("Capacity (open tasks by practice):")
    for row in digest["capacity"]:
        lines.append(f"  {row['practice']}: {row['open_tasks']}")
    lines.append("No news APIs called. Numbers come only from synthetic SIOS records.")
    return "\n".join(lines)


def compliance_calendar(
    store: OperatingStore | None = None,
    *,
    as_of: date | None = None,
    within_days: int = 45,
    include_overdue: bool = True,
) -> list[dict[str, Any]]:
    store = store or open_store()
    as_of = as_of or date.today()
    store.refresh_filing_statuses(as_of=as_of)
    clients = store.client_map()
    rows = []
    for event in events_in_window(
        store.compliance, within_days=within_days, as_of=as_of, include_overdue=include_overdue
    ):
        client = clients.get(event.client_id) if event.client_id else None
        rows.append(
            {
                "event_id": event.event_id,
                "due_at": event.due_at,
                "type": event.type,
                "status": event.status,
                "filing_status": event.filing_status,
                "client_id": event.client_id,
                "client_name": client.display_name if client else event.legal_entity_id,
                "owner_user_id": event.owner_user_id,
                "eng_id": event.eng_id,
                "is_synthetic": True,
            }
        )
    return rows
