"""Synthetic Bradbury fixtures must load only when is_synthetic=true."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sios.synthetic import DISCLAIMER, SyntheticDataError, load_all, seed, summary


def test_load_all_enforces_synthetic_flag(tmp_path: Path) -> None:
    for name in ("org-users.json", "clients-engagements.json", "calendar-kpis-docs.json"):
        (tmp_path / name).write_text(json.dumps({"is_synthetic": True, "users": [], "clients": [], "engagements": [], "compliance_events": [], "kpis": [], "sample_documents": [], "legal_entities": []}), encoding="utf-8")
    bundle = load_all(tmp_path)
    assert bundle["is_synthetic"] is True
    assert "FAKE" in bundle["disclaimer"] or "SYNTHETIC" in bundle["disclaimer"].upper() or DISCLAIMER in bundle["disclaimer"]


def test_load_all_refuses_non_synthetic(tmp_path: Path) -> None:
    (tmp_path / "org-users.json").write_text(json.dumps({"is_synthetic": False, "users": []}), encoding="utf-8")
    (tmp_path / "clients-engagements.json").write_text(json.dumps({"is_synthetic": True}), encoding="utf-8")
    (tmp_path / "calendar-kpis-docs.json").write_text(json.dumps({"is_synthetic": True}), encoding="utf-8")
    with pytest.raises(SyntheticDataError, match="is_synthetic"):
        load_all(tmp_path)


def test_repo_fixtures_are_synthetic() -> None:
    bundle = load_all()
    counts = summary(bundle)
    assert bundle["is_synthetic"] is True
    assert counts["users"] >= 1
    assert counts["clients"] >= 1
    assert counts["engagements"] >= 1
    assert counts["compliance_events"] >= 1
    for client in bundle["clients_engagements"]["clients"]:
        assert client["name"].startswith("SYN ") or client["name"].startswith("SYN")


def test_seed_writes_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from grit import settings

    monkeypatch.setattr(settings, "OUTPUT_DIR", tmp_path / "output")
    result = seed(write_snapshot=True)
    assert result["is_synthetic"] is True
    assert Path(result["snapshot"]).is_file()
    payload = json.loads(Path(result["snapshot"]).read_text(encoding="utf-8"))
    assert payload["is_synthetic"] is True
