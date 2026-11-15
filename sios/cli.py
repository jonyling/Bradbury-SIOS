"""Bradbury SIOS command line. Run from the repository root:

    .venv/bin/python -m sios --help
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from typing import Any

from sios import PRODUCT_NAME, PRODUCT_TAGLINE, RULE
from sios.synthetic import DISCLAIMER, seed, summary


def cmd_seed(args: argparse.Namespace) -> int:
    """Load synthetic Bradbury org + clients. Never invents real client PII."""
    result = seed(write_snapshot=not args.dry_run)
    print(DISCLAIMER)
    print(f"{PRODUCT_NAME} synthetic seed")
    for key, value in result["counts"].items():
        print(f"  {key}: {value}")
    if args.dry_run:
        print("Dry run: no snapshot written.")
    else:
        print(f"Snapshot: {result.get('snapshot')}")
    if args.json:
        print(json.dumps({"is_synthetic": True, "counts": result["counts"]}, indent=2))
    return 0


def cmd_deadlines(args: argparse.Namespace) -> int:
    """List synthetic compliance deadlines (Phase 0 stub over fixtures)."""
    from sios.synthetic import load_all

    bundle = load_all()
    events = list(bundle["calendar_kpis_docs"].get("compliance_events") or [])
    clients = {c["client_id"]: c for c in bundle["clients_engagements"].get("clients") or []}
    today = args.as_of or date.today()
    print(DISCLAIMER)
    print(f"{PRODUCT_NAME} deadlines (synthetic) as of {today.isoformat()}")
    shown = 0
    for event in sorted(events, key=lambda row: row.get("due_at") or ""):
        due = event.get("due_at")
        if not due:
            continue
        due_date = date.fromisoformat(due)
        if args.within_days is not None and (due_date - today).days > args.within_days:
            continue
        if args.within_days is not None and (due_date - today).days < 0 and not args.include_overdue:
            continue
        client_id = event.get("client_id")
        client_name = clients.get(client_id, {}).get("name") if client_id else event.get("legal_entity_id")
        print(
            f"  {due}  {event.get('status', '?'):16}  {event.get('type', '?'):32}  "
            f"{client_name or '—'}  owner={event.get('owner_user_id', '—')}"
        )
        shown += 1
    print(f"{shown} event(s). Phase 0 stub — not ACRA/MOM source of truth.")
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    """Principal digest stub over synthetic engagements and deadlines (no news APIs)."""
    from sios.synthetic import load_all

    bundle = load_all()
    counts = summary(bundle)
    events = bundle["calendar_kpis_docs"].get("compliance_events") or []
    engagements = bundle["clients_engagements"].get("engagements") or []
    at_risk = [
        e for e in engagements
        if e.get("status") == "active"
        and any(t.get("status") in {"blocked", "waiting"} for t in e.get("tasks") or [])
    ]
    upcoming = sorted(
        (e for e in events if e.get("due_at")),
        key=lambda row: row["due_at"],
    )[:5]
    print(DISCLAIMER)
    print(f"{PRODUCT_NAME} principal digest (synthetic)")
    print(f"Generated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}")
    print(f"Clients: {counts['clients']} · Engagements: {counts['engagements']} · Users: {counts['users']}")
    print(f"At-risk engagements (blocked/waiting tasks): {len(at_risk)}")
    for eng in at_risk:
        print(f"  {eng['eng_id']}  pack={eng.get('pack')}  client={eng.get('client_id')}  owner={eng.get('owner_user_id')}")
    print("Upcoming compliance (sample):")
    for event in upcoming:
        print(f"  {event.get('due_at')}  {event.get('type')}  {event.get('status')}  {event.get('client_id') or event.get('legal_entity_id')}")
    print("No news APIs called. Numbers come only from synthetic fixtures.")
    return 0


def cmd_ui(_args: argparse.Namespace) -> int:
    """Start the Streamlit shell (rebranded Phase 0 surface)."""
    from grit.cli import cmd_ui as grit_ui

    return int(grit_ui(_args) or 0)


def cmd_packs(_args: argparse.Namespace) -> int:
    """List Bradbury service-line pack stubs."""
    from pathlib import Path

    from grit.settings import CONFIG_DIR

    root = CONFIG_DIR / "bradbury"
    print(f"{PRODUCT_NAME} pack stubs under {root}")
    if not root.is_dir():
        print("  (missing)")
        return 1
    for path in sorted(root.iterdir()):
        if path.is_dir():
            checklist = path / "checklist.yaml"
            print(f"  {path.name}: {'checklist.yaml' if checklist.is_file() else '(no checklist yet)'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sios",
        description=f"{PRODUCT_NAME}: {PRODUCT_TAGLINE}. {RULE}",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    sub = commands.add_parser("seed", help="Load synthetic Bradbury org + clients (is_synthetic enforced).")
    sub.add_argument("--dry-run", action="store_true", help="Load and print counts without writing a snapshot.")
    sub.add_argument("--json", action="store_true", help="Also print counts as JSON.")
    sub.set_defaults(handler=cmd_seed)

    sub = commands.add_parser("deadlines", help="List synthetic compliance deadlines (Phase 0 stub).")
    sub.add_argument("--as-of", type=date.fromisoformat, help="Reference date YYYY-MM-DD (default today).")
    sub.add_argument("--within-days", type=int, default=45, help="Only events due within N days (default 45).")
    sub.add_argument("--include-overdue", action="store_true", help="Include overdue events.")
    sub.set_defaults(handler=cmd_deadlines)

    commands.add_parser("digest", help="Principal digest from synthetic records (no news APIs).").set_defaults(
        handler=cmd_digest
    )
    commands.add_parser("packs", help="List Bradbury service-line pack stubs.").set_defaults(handler=cmd_packs)
    commands.add_parser("ui", help="Start the Streamlit shell.").set_defaults(handler=cmd_ui)
    return parser


def main(argv: list[str] | None = None) -> int:
    from grit.settings import OUTPUT_DIR, load_local_env

    load_local_env()
    args = build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return int(args.handler(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
