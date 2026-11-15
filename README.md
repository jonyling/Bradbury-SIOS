# Bradbury SIOS

**Bradbury SIOS** is the SME SI Operating System for Bradbury Consulting Pte Ltd — the internal operating layer for clients, engagements, statutory calendars, delivery work, documents, staffing, and management visibility.

This repository was seeded from grit-scan-platform DNA and repositioned in **Phase 0**. **Phase 1** adds the MVP operating core on synthetic data.

See [docs/SIOS_VISION.md](docs/SIOS_VISION.md) for the vision stub and pointers to the full plan.

## The rule

Agents propose. Deterministic functions decide. A named human approves.

Optional AI assistance **proposes** but never silently decides. Compliance and billing terminals (`lodged`, `issued`) require a named **human** through ReviewGate + TransitionGuard — never an LLM actor.

## Phase 1 status

| Area | Status |
|------|--------|
| Client + Engagement + Task + Compliance + Document metadata | Active on synthetic fixtures |
| Live packs `corp-sec` / `accounting` / `hr-advisory` | Checklists drive workstreams |
| Principal dashboard + practice queues (Streamlit) | `sios ui` |
| Deterministic SLA / filing status | Due 7/14/30 · at-risk · capacity |
| ReviewGate on ready to lodge/send (FS, policy, invoice) | `sios approve` / UI Approvals |
| Principal digest | No news APIs |
| STE / news / WSH / adverse / Dataverse | Remain quarantined |

## Repository layout

| Path | Contents |
|------|----------|
| `sios/` | Product operating core + CLI + Streamlit |
| `sios/store.py` | In-memory store seeded from synthetic JSON |
| `sios/packs.py` / `workflow.py` / `gates.py` | Packs, checklist workflow, ReviewGate adapter |
| `sios/digest.py` / `sla.py` | Principal digest + deterministic SLA |
| `grit/core/` | ReviewGate primitive (+ legacy TransitionGuard DNA) |
| `config/bradbury/` | Live corp-sec, accounting, hr-advisory checklists |
| `data/synthetic/` | Synthetic fixtures (`is_synthetic=true`) |
| `archive/legacy-ste/` | Archived STE packs |
| `tests/` | DNA + SIOS Phase 0/1 suite |

## Install the local environment

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e . --no-deps
```

## Active commands

```bash
python -m sios --help
python -m sios seed
python -m sios deadlines --as-of 2026-11-15 --within-days 45
python -m sios digest --as-of 2026-11-15
python -m sios packs
python -m sios checklist --eng-id E-505
python -m sios checklist --demo-incorporation
python -m sios ui
```

## Synthetic data

Fixtures under `data/synthetic/` are **entirely fake**. They use `SYN-` ids and `is_synthetic: true`. Demo clients are labeled **SYNTHETIC** in the UI and digest. Do not treat them as real Bradbury clients or filings.

## Tests

```bash
python -m pytest -q
```

Default collection excludes `tests/quarantined/`.
