"""Messages for legacy GRIT-Scan / STE paths disabled in Bradbury SIOS Phase 0."""

from __future__ import annotations

MESSAGE = (
    "This command is quarantined in Bradbury SIOS Phase 0. "
    "It belongs to the legacy GRIT-Scan / ST Engineering risk-scanner seed "
    "(news acquisition, STE packs, WSH, Dataverse STE, adverse news, RED). "
    "Use `python -m sios --help` for active commands. "
    "Legacy code remains under grit/ and archive/legacy-ste/ for reference."
)


def refuse(command: str | None = None) -> int:
    label = f" ({command})" if command else ""
    print(f"Quarantined{label}: {MESSAGE}")
    return 2
