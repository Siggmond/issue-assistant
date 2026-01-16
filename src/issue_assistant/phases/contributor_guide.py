from __future__ import annotations

import re

from ..models import IssueAnalysis


def render_contributor_guide(a: IssueAnalysis) -> str:
    n = a.normalized
    q = a.quality

    lines: list[str] = []
    lines.append(f"# Contributor Guide for Issue #{n.issue.number}")
    lines.append("")
    lines.append(f"Title: {n.issue.title}")
    lines.append("")

    lines.append("## What to add")
    lines.append("")

    missing: list[str] = []
    if "reproduction_steps" not in n.sections:
        missing.append("Reproduction steps (minimal, numbered)")
    if "expected_behavior" not in n.sections:
        missing.append("Expected behavior")
    if "actual_behavior" not in n.sections:
        missing.append("Actual behavior")
    if "environment" not in n.sections:
        missing.append("Environment details (Python version, OS, package versions)")
    if "logs" not in n.sections:
        missing.append("Logs / stack trace (paste in a code block)")

    if missing:
        for m in missing:
            lines.append(f"- [ ] {m}")
    else:
        lines.append("- [ ] Confirm the provided information is still accurate")

    lines.append("")

    lines.append("## Likely involved files")
    lines.append("")
    files = _mentioned_files(n.issue.title + "\n" + (n.issue.body or ""))
    if files:
        for f in files[:20]:
            lines.append(f"- `{f}`")
        if len(files) > 20:
            lines.append("- (more omitted)")
    else:
        lines.append("- None detected from the issue text.")

    lines.append("")

    lines.append("## How to improve this issue")
    lines.append("")
    lines.append(f"- Current triage: **{a.triage.category}**")
    lines.append(f"- Lifecycle state: **{a.lifecycle.state}**")
    lines.append(f"- Maintainer cost (relative): **{a.maintainer_cost.level}**")
    lines.append("")

    if q.noise >= 60:
        lines.append("- Reduce noise: keep the description focused and remove urgency language.")
    if q.reproducibility < 50:
        lines.append("- Improve reproducibility: provide minimal repro steps and exact environment.")
    if "logs" not in n.sections:
        lines.append("- Add logs: include the full error message and stack trace in a fenced code block.")

    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _mentioned_files(text: str) -> list[str]:
    t = text or ""
    files = re.findall(r"\b[a-zA-Z0-9_./-]+\.py\b", t)
    files += re.findall(r"\b[a-zA-Z0-9_./-]+\.toml\b", t)
    files += re.findall(r"\b[a-zA-Z0-9_./-]+\.yml\b", t)
    files += re.findall(r"\b[a-zA-Z0-9_./-]+\.yaml\b", t)

    out: list[str] = []
    seen: set[str] = set()
    for f in files:
        f2 = f.strip("` ")
        if f2 and f2 not in seen:
            seen.add(f2)
            out.append(f2)
    return out
