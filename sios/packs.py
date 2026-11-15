"""Load and apply Bradbury service-line pack checklists (Phase 1 live packs)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from grit.settings import CONFIG_DIR

LIVE_PACKS = ("corp-sec", "accounting", "hr-advisory")

# Engagement type → default checklist key inside the pack YAML.
CHECKLIST_FOR_ENGAGEMENT = {
    ("corp-sec", "package"): "incorporation_package",
    ("corp-sec", "retainer"): "retainer_corp_sec",
    ("accounting", "retainer"): "monthly_close",
    ("accounting", "project"): "monthly_close",
    ("hr-advisory", "project"): "policy_suite",
    ("hr-advisory", "retainer"): "policy_suite",
}

GATE_KIND_BY_STEP = {
    "bizfile_pack_review_gate": "filing_pack_ready",
    "senior_review_gate": "fs_send",
    "client_send": "fs_send",
    "finalise_train": "policy_final",
    "gst_draft": "gst_ready",
}


class PackError(ValueError):
    """Invalid or missing service-line pack."""


def packs_root() -> Path:
    return CONFIG_DIR / "bradbury"


def load_pack(pack_id: str) -> dict[str, Any]:
    if pack_id not in LIVE_PACKS:
        raise PackError(f"Pack {pack_id!r} is not a Phase 1 live pack ({', '.join(LIVE_PACKS)})")
    path = packs_root() / pack_id / "checklist.yaml"
    if not path.is_file():
        raise PackError(f"Missing checklist for pack {pack_id}: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if data.get("pack") != pack_id:
        raise PackError(f"{path}: pack field must be {pack_id!r}")
    return data


def list_live_packs() -> list[dict[str, Any]]:
    rows = []
    for pack_id in LIVE_PACKS:
        data = load_pack(pack_id)
        rows.append(
            {
                "pack": pack_id,
                "label": data.get("label") or pack_id,
                "version": data.get("version"),
                "review_gates": list(data.get("review_gates") or []),
                "checklists": sorted((data.get("checklists") or {}).keys()),
                "is_synthetic_playbook": bool(data.get("is_synthetic_playbook")),
            }
        )
    return rows


def checklist_key_for(pack: str, engagement_type: str) -> str | None:
    return CHECKLIST_FOR_ENGAGEMENT.get((pack, engagement_type))


def checklist_steps(pack_id: str, checklist_key: str) -> list[dict[str, Any]]:
    data = load_pack(pack_id)
    checklists = data.get("checklists") or {}
    steps = checklists.get(checklist_key)
    if not isinstance(steps, list):
        raise PackError(f"Pack {pack_id} has no checklist {checklist_key!r}")
    enriched = []
    for step in steps:
        row = dict(step)
        step_id = row.get("id") or ""
        if row.get("needs_review_gate") and not row.get("gate_kind"):
            row["gate_kind"] = GATE_KIND_BY_STEP.get(step_id) or (data.get("review_gates") or ["filing_pack_ready"])[0]
        enriched.append(row)
    return enriched
