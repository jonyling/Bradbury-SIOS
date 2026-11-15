"""Bradbury SIOS CLI and Phase 0 quarantine smoke tests."""

from __future__ import annotations

from pathlib import Path

from sios import PRODUCT_NAME
from sios.cli import main as sios_main
from grit.cli import QUARANTINED_COMMANDS, main as grit_main
from grit.ontology.pack import manifests


def test_sios_help_names_product() -> None:
    try:
        sios_main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0


def test_sios_seed_dry_run(capsys) -> None:
    code = sios_main(["seed", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "FAKE" in out or "SYNTHETIC" in out.upper()
    assert "users:" in out


def test_sios_deadlines_and_digest(capsys) -> None:
    assert sios_main(["deadlines", "--as-of", "2026-11-15", "--within-days", "60"]) == 0
    assert sios_main(["digest"]) == 0
    out = capsys.readouterr().out
    assert PRODUCT_NAME in out or "synthetic" in out.lower()


def test_sios_packs_lists_bradbury_stubs(capsys) -> None:
    assert sios_main(["packs"]) == 0
    out = capsys.readouterr().out
    assert "corp-sec" in out
    assert "accounting" in out
    assert "hr-advisory" in out


def test_ste_packs_archived_not_active() -> None:
    assert not Path("config/urs").exists()
    assert not Path("config/ste").exists()
    assert not Path("config/wsh").exists()
    assert Path("archive/legacy-ste/config/urs").is_dir()
    assert Path("archive/legacy-ste/config/ste").is_dir()
    assert manifests() == {}


def test_grit_quarantines_weekly(capsys) -> None:
    assert "weekly" in QUARANTINED_COMMANDS
    code = grit_main(["weekly", "--dry-run"])
    assert code == 2
    assert "quarantined" in capsys.readouterr().out.lower()


def test_grit_quarantines_adverse(capsys) -> None:
    code = grit_main(["adverse"])
    assert code == 2
    assert "quarantined" in capsys.readouterr().out.lower()
