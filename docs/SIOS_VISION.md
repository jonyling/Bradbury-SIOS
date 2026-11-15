# Bradbury SIOS — Vision (repo stub)

**Bradbury SIOS** is the SME SI Operating System for Bradbury Consulting Pte Ltd.

This repository was seeded from grit-scan-platform DNA (ReviewGate, TransitionGuard, workflow, CLI, Streamlit, Co-Pilot pattern, report renderers) and is being repositioned away from STE external risk scanning.

## Canonical plan

The full vision, phased roadmap, keep/adapt/discard table, and immediate build actions live in the project store:

- Vision plan: project store `docs/bradbury-sios-vision-plan.md`
- Org skeleton: `docs/bradbury-org-skeleton.md`
- Synthetic data: `docs/bradbury-synthetic-data.md`
- Phase 0 execution plan: `docs/phase-0-execution-plan.md`

## Phase 0 in this repo

- Product surface renamed to Bradbury SIOS (`sios/` facade).
- STE / news / WSH / adverse / Dataverse paths quarantined under `archive/legacy-ste/` and module `QUARANTINED.md` markers.
- Synthetic fixtures in `data/synthetic/` (`is_synthetic=true`).
- Service-line stubs in `config/bradbury/`.

## Rule

Agents propose. Deterministic functions decide. A named human approves.
