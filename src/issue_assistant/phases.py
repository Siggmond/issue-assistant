from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseSpec:
    name: str
    requires_comments: bool


PHASES: dict[str, PhaseSpec] = {
    "dependencies": PhaseSpec(name="dependencies", requires_comments=True),
    "weekly_digest": PhaseSpec(name="weekly_digest", requires_comments=False),
    "issue_health": PhaseSpec(name="issue_health", requires_comments=False),
    "low_signal": PhaseSpec(name="low_signal", requires_comments=True),
    "knowledge_base": PhaseSpec(name="knowledge_base", requires_comments=True),
    "playbooks": PhaseSpec(name="playbooks", requires_comments=False),
    "maintainer_load": PhaseSpec(name="maintainer_load", requires_comments=False),
    "explainability": PhaseSpec(name="explainability", requires_comments=False),
}


def normalize_enabled_phases(phases_arg: str | None) -> set[str] | None:
    if phases_arg is None or str(phases_arg).strip() == "" or str(phases_arg).strip().lower() == "all":
        return None

    raw = str(phases_arg)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    enabled: set[str] = set()
    for p in parts:
        if p not in PHASES:
            raise ValueError(f"Unknown phase: {p}")
        enabled.add(p)

    return enabled


def enabled_phases_require_comments(enabled: set[str] | None) -> bool:
    if enabled is None:
        return any(spec.requires_comments for spec in PHASES.values())
    return any(PHASES[p].requires_comments for p in enabled)
