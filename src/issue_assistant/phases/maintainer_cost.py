from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import MaintainerCostEstimate, NormalizedIssue, QualityBreakdown


@dataclass(frozen=True)
class CostLimits:
    max_body_chars_considered: int = 10_000


DEFAULT_LIMITS = CostLimits()


def estimate_maintainer_cost(
    *,
    normalized: NormalizedIssue,
    quality: QualityBreakdown,
    limits: CostLimits = DEFAULT_LIMITS,
) -> MaintainerCostEstimate:
    body = (normalized.issue.body or "")[: limits.max_body_chars_considered]

    reasons: list[str] = []

    # deterministic signals
    mentioned_files = _mentioned_files(normalized.issue.title + "\n" + body)
    file_count = len(mentioned_files)

    has_repro = "reproduction_steps" in normalized.sections
    has_logs = "logs" in normalized.sections

    body_len = len(body.strip())

    # Base score
    score = 0

    # A) Issue size / complexity hints
    if body_len > 2000:
        score += 2
        reasons.append("long description")
    elif body_len > 500:
        score += 1
        reasons.append("moderate description length")

    # B) Affected files/components mentioned
    if file_count >= 5:
        score += 2
        reasons.append("many referenced files")
    elif file_count >= 2:
        score += 1
        reasons.append("multiple referenced files")

    # C) Repro complexity proxy
    # If reproducibility is high and repro steps exist, cost tends to be lower (less time spent clarifying)
    if not has_repro:
        score += 1
        reasons.append("missing reproduction steps")
    if not has_logs:
        score += 1
        reasons.append("missing logs/stack trace")

    if quality.reproducibility >= 75 and has_repro:
        score -= 1
        reasons.append("high reproducibility")

    # Map score -> cost category
    if score <= 0:
        level = "low"
    elif score <= 2:
        level = "medium"
    else:
        level = "high"

    reasons = _uniq(reasons)

    return MaintainerCostEstimate(level=level, reasons=tuple(reasons), signals={
        "body_length": body_len,
        "referenced_files": file_count,
        "has_repro": has_repro,
        "has_logs": has_logs,
        "reproducibility": quality.reproducibility,
    })


def _uniq(xs: list[str]) -> list[str]:
    out: list[str] = []
    for x in xs:
        x2 = x.strip()
        if x2 and x2 not in out:
            out.append(x2)
    return out


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
