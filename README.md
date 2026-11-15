# Bradbury SIOS

**Bradbury SIOS** is the SME SI Operating System for Bradbury Consulting Pte Ltd — the internal operating layer for clients, engagements, statutory calendars, delivery work, documents, staffing, and management visibility.

This repository was seeded from grit-scan-platform DNA and is being repositioned in **Phase 0** away from ST Engineering external risk scanning. It is an independent product, not a risk scanner.

See [docs/SIOS_VISION.md](docs/SIOS_VISION.md) for the vision stub and pointers to the full plan.

## The rule

Agents propose. Deterministic functions decide. A named human approves.

Optional AI assistance **proposes** but never silently decides. Compliance and billing outcomes require a named human through `ReviewGate()`.

## Phase 0 status

| Area | Status |
|------|--------|
| Product name / CLI (`sios`) | Active |
| Synthetic Bradbury org + clients (`data/synthetic/`) | Active — **FAKE data only** |
| Service-line pack stubs (`config/bradbury/`) | Active stubs |
| ReviewGate / TransitionGuard / workflow DNA | Kept |
| Streamlit shell / Co-Pilot pattern / report renderers | Kept (light rebrand) |
| STE packs, news acquisition, WSH, adverse, Dataverse STE, FIRMS | Quarantined → `archive/legacy-ste/` |

## Repository layout

| Path | Contents |
|------|----------|
| `sios/` | Product facade: `seed`, `deadlines`, `digest`, `packs`, `ui` |
| `grit/core/` | Deterministic DNA including `ReviewGate()` and `TransitionGuard()` |
| `grit/workflow/` | Supervisor / package review patterns |
| `grit/report/` | Word / PowerPoint / Excel / Markdown renderers |
| `grit/ui/` | Streamlit shell |
| `grit/copilot/` | Co-Pilot pattern (to be grounded on SIOS records in later phases) |
| `grit/acquisition/`, `adverse/`, `wsh/`, `dataverse/`, `daily/` | **Quarantined** legacy STE/news modules |
| `config/bradbury/` | Corp-sec, accounting, hr-advisory checklist stubs |
| `data/synthetic/` | Synthetic fixtures (`is_synthetic=true`) |
| `archive/legacy-ste/` | Archived STE packs, profiles, examples |
| `specs/` | Active trust-model specs (ReviewGate, TransitionGuard, workflow) |
| `specs/archive/` | Archived STE risk-scanner specs |
| `tests/` | Default suite: DNA + SIOS foundation |
| `tests/quarantined/` | Legacy STE/news tests (not collected by default) |

## Install the local environment

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e . --no-deps
```

## Active commands

```bash
.venv/bin/python -m sios --help
.venv/bin/python -m sios seed
.venv/bin/python -m sios deadlines --within-days 45
.venv/bin/python -m sios digest
.venv/bin/python -m sios packs
.venv/bin/python -m sios ui
```

`python -m grit` remains as a **legacy** entry point. STE/news commands print a quarantine message and exit.

## Synthetic data

Fixtures under `data/synthetic/` are **entirely fake**. They use `SYN-` ids and `is_synthetic: true`. The loader refuses any file that omits that flag. Do not treat them as real Bradbury clients or filings.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Default collection excludes `tests/quarantined/`. DNA checks:

```bash
.venv/bin/python -m pytest tests/test_p3_review_gate.py tests/test_p3_transition_guard.py tests/test_p3_supervisor.py tests/test_sios_synthetic.py tests/test_sios_cli.py -q
```

## What comes next (not Phase 0)

Phase 1 MVP: Client + Engagement + Task + Compliance Calendar + Document metadata, with live corp-sec / accounting / hr-advisory packs and a Principal dashboard. See the store vision plan.
