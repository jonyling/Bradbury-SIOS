# Bradbury SIOS service-line packs (Phase 1 live)

These are **operational playbooks**, not STE risk-scan ontology packs.

| Pack | Purpose | Phase 1 |
|------|---------|---------|
| `corp-sec` | Incorporation, named secretary, filings, AGM | Live — drives checklists + ReviewGate |
| `accounting` | Books, FS, GST, monthly close | Live — drives checklists + ReviewGate |
| `hr-advisory` | Policies, letters, HR projects | Live — drives checklists + ReviewGate |

`sios.packs` loads `checklist.yaml` and `OperatingStore.expand_live_pack_checklists()` materializes steps onto synthetic engagements.
