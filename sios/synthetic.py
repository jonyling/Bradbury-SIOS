"""Load Bradbury SIOS synthetic fixtures. All demo data must be is_synthetic=true."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from grit.settings import OUTPUT_DIR, ROOT

SYNTHETIC_ENV = "SIOS_SYNTHETIC_DIR"
DEFAULT_DIR = ROOT / "data" / "synthetic"
REQUIRED_FILES = (
    "org-users.json",
    "clients-engagements.json",
    "calendar-kpis-docs.json",
)
DISCLAIMER = (
    "ALL FIXTURES ARE FAKE / SYNTHETIC. Not real Bradbury clients, candidates, fees, or filings."
)


class SyntheticDataError(ValueError):
    """Raised when a fixture is missing, invalid, or not marked synthetic."""


def synthetic_dir() -> Path:
    override = os.environ.get(SYNTHETIC_ENV, "").strip()
    return Path(override).expanduser() if override else DEFAULT_DIR


def _load_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SyntheticDataError(f"Missing synthetic fixture: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SyntheticDataError(f"{path.name}: expected a JSON object")
    if data.get("is_synthetic") is not True:
        raise SyntheticDataError(
            f"{path.name}: refuses to load — is_synthetic must be true (got {data.get('is_synthetic')!r})"
        )
    return data


def load_all(directory: Path | None = None) -> dict[str, Any]:
    """Load every required synthetic fixture. Enforces is_synthetic=true on each file."""
    root = directory or synthetic_dir()
    loaded = {name: _load_file(root / name) for name in REQUIRED_FILES}
    return {
        "is_synthetic": True,
        "disclaimer": DISCLAIMER,
        "org_users": loaded["org-users.json"],
        "clients_engagements": loaded["clients-engagements.json"],
        "calendar_kpis_docs": loaded["calendar-kpis-docs.json"],
    }


def summary(bundle: dict[str, Any]) -> dict[str, int]:
    org = bundle["org_users"]
    clients = bundle["clients_engagements"]
    calendar = bundle["calendar_kpis_docs"]
    return {
        "legal_entities": len(org.get("legal_entities") or []),
        "users": len(org.get("users") or []),
        "clients": len(clients.get("clients") or []),
        "engagements": len(clients.get("engagements") or []),
        "compliance_events": len(calendar.get("compliance_events") or []),
        "kpis": len(calendar.get("kpis") or []),
        "sample_documents": len(calendar.get("sample_documents") or []),
    }


def seed(directory: Path | None = None, *, write_snapshot: bool = True) -> dict[str, Any]:
    """Load synthetic fixtures and optionally write a local demo snapshot under output/."""
    bundle = load_all(directory)
    counts = summary(bundle)
    result = {
        "is_synthetic": True,
        "disclaimer": DISCLAIMER,
        "counts": counts,
        "source_dir": str(directory or synthetic_dir()),
    }
    if write_snapshot:
        out = OUTPUT_DIR / "synthetic"
        out.mkdir(parents=True, exist_ok=True)
        snapshot = {**result, "bundle": bundle}
        path = out / "seed_snapshot.json"
        path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        result["snapshot"] = str(path)
    return result
