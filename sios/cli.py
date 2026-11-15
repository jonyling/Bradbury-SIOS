"""Bradbury SIOS command line. Run from the repository root:

    python -m sios --help
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any

from sios import PRODUCT_NAME, PRODUCT_TAGLINE, RULE
from sios.synthetic import DISCLAIMER, seed


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
    """List synthetic compliance deadlines with deterministic filing status."""
    from sios.digest import compliance_calendar
    from sios.store import open_store

    store = open_store()
    today = args.as_of or date.today()
    rows = compliance_calendar(
        store,
        as_of=today,
        within_days=args.within_days if args.within_days is not None else 45,
        include_overdue=args.include_overdue,
    )
    print(DISCLAIMER)
    print(f"{PRODUCT_NAME} deadlines (synthetic) as of {today.isoformat()}")
    for row in rows:
        print(
            f"  {row['due_at']}  {row['filing_status']:12}  {row['type']:32}  "
            f"{row['client_name'] or '—'}  owner={row['owner_user_id']}"
        )
    print(f"{len(rows)} event(s). Not ACRA/MOM source of truth.")
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    """Principal digest over synthetic SIOS records (no news APIs)."""
    from sios.digest import build_digest, render_digest_text
    from sios.store import open_store

    store = open_store()
    digest = build_digest(store, as_of=args.as_of)
    print(render_digest_text(digest))
    if args.json:
        print(json.dumps(digest, indent=2, default=str))
    return 0


def cmd_ui(_args: argparse.Namespace) -> int:
    """Start the Phase 1 Streamlit Principal dashboard."""
    import subprocess
    from pathlib import Path

    app = Path(__file__).resolve().parent / "ui" / "app.py"
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(app), "--server.headless", "true"])


def cmd_packs(_args: argparse.Namespace) -> int:
    """List live Bradbury service-line packs."""
    from sios.packs import list_live_packs

    print(f"{PRODUCT_NAME} live packs")
    for row in list_live_packs():
        print(
            f"  {row['pack']}: {row['label']} v{row['version']} "
            f"checklists={','.join(row['checklists'])} gates={','.join(row['review_gates'])}"
        )
    return 0


def cmd_checklist(args: argparse.Namespace) -> int:
    """Show pack-driven checklist progress for an engagement."""
    from sios.store import open_store
    from sios.workflow import checklist_progress, run_incorporation_demo

    store = open_store()
    if args.demo_incorporation:
        result = run_incorporation_demo(store, reviewer_id=args.reviewer or "U-002")
        print(DISCLAIMER)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("lodged", {}).get("persisted") else 1
    progress = checklist_progress(store, args.eng_id)
    print(DISCLAIMER)
    print(json.dumps(progress, indent=2))
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    """Submit / ReviewGate / human-terminal actions for a deliverable package."""
    from sios.store import open_store
    from sios.workflow import human_terminal_action, review_package, submit_for_review

    store = open_store()
    if args.action == "submit":
        package = submit_for_review(
            store,
            eng_id=args.eng_id,
            task_id=args.task_id,
            actor_id=args.actor or "U-009",
            actor_type=args.actor_type,
        )
        print(json.dumps(package, indent=2))
        return 0
    if args.action == "review":
        result = review_package(
            store,
            package_id=args.package_id,
            reviewer_id=args.actor or "U-002",
            intent=args.intent,
            reviewer_is_human=args.actor_type.upper() == "HUMAN",
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("persisted") else 1
    if args.action == "terminal":
        result = human_terminal_action(
            store,
            package_id=args.package_id,
            actor_id=args.actor or "U-002",
            actor_type=args.actor_type,
            terminal=args.terminal,
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("persisted") else 1
    print("Unknown action", file=sys.stderr)
    return 2


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

    sub = commands.add_parser("deadlines", help="List synthetic compliance deadlines with SLA filing status.")
    sub.add_argument("--as-of", type=date.fromisoformat, help="Reference date YYYY-MM-DD (default today).")
    sub.add_argument("--within-days", type=int, default=45, help="Only events due within N days (default 45).")
    sub.add_argument("--include-overdue", action="store_true", help="Include overdue events.")
    sub.set_defaults(handler=cmd_deadlines)

    sub = commands.add_parser("digest", help="Principal digest from synthetic records (no news APIs).")
    sub.add_argument("--as-of", type=date.fromisoformat, default=None)
    sub.add_argument("--json", action="store_true")
    sub.set_defaults(handler=cmd_digest)

    commands.add_parser("packs", help="List live Bradbury service-line packs.").set_defaults(handler=cmd_packs)
    commands.add_parser("ui", help="Start the Streamlit Principal dashboard.").set_defaults(handler=cmd_ui)

    sub = commands.add_parser("checklist", help="Show or demo pack-driven engagement checklist.")
    sub.add_argument("--eng-id", default="E-505", help="Engagement id (default E-505 incorporation).")
    sub.add_argument("--demo-incorporation", action="store_true", help="Run E-505 end-to-end including human lodge.")
    sub.add_argument("--reviewer", default="U-002")
    sub.set_defaults(handler=cmd_checklist)

    sub = commands.add_parser("approve", help="ReviewGate / human terminal actions.")
    sub.add_argument("action", choices=["submit", "review", "terminal"])
    sub.add_argument("--eng-id")
    sub.add_argument("--task-id")
    sub.add_argument("--package-id")
    sub.add_argument("--intent", default="APPROVE")
    sub.add_argument("--terminal", default="LODGED", choices=["LODGED", "SENT", "ISSUED"])
    sub.add_argument("--actor", default=None)
    sub.add_argument("--actor-type", default="HUMAN")
    sub.set_defaults(handler=cmd_approve)
    return parser


def main(argv: list[str] | None = None) -> int:
    from grit.settings import OUTPUT_DIR, load_local_env

    load_local_env()
    args = build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return int(args.handler(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
