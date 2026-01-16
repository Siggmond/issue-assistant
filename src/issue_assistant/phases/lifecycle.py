from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..models import LifecycleClassification, NormalizedIssue, QualityBreakdown, TriageClassification


@dataclass(frozen=True)
class LifecycleLimits:
    stale_days: int = 90


DEFAULT_LIMITS = LifecycleLimits()


def classify_lifecycle(
    *,
    normalized: NormalizedIssue,
    quality: QualityBreakdown,
    triage: TriageClassification,
    now: datetime | None = None,
    limits: LifecycleLimits = DEFAULT_LIMITS,
) -> LifecycleClassification:
    now_dt = now or datetime.now(tz=timezone.utc)

    labels = {l.name.lower() for l in normalized.issue.labels}
    text = (normalized.issue.title or "") + "\n" + (normalized.issue.body or "")
    text_lower = text.lower()

    # 1) blocked
    if any(l in labels for l in ("blocked", "blocking", "dependency")):
        return LifecycleClassification(state="blocked", confidence="HIGH", reasons=("label indicates blocked",))

    if _text_mentions_blocked(text_lower):
        return LifecycleClassification(
            state="blocked",
            confidence="MEDIUM",
            reasons=("text indicates dependency or waiting on external factor",),
        )

    # 2) stale
    updated_at = normalized.issue.updated_at or normalized.issue.created_at
    if updated_at is not None:
        age = now_dt - updated_at
        if age >= timedelta(days=limits.stale_days) and (normalized.issue.state or "open").lower() == "open":
            return LifecycleClassification(
                state="stale",
                confidence="MEDIUM",
                reasons=(f"no updates in {age.days} days",),
            )

    # 3) likely-invalid
    if any(l in labels for l in ("invalid", "wontfix", "won't fix", "duplicate")):
        return LifecycleClassification(
            state="likely-invalid",
            confidence="HIGH",
            reasons=("label indicates invalid/wontfix/duplicate",),
        )

    if _text_mentions_invalid(text_lower) and triage.category in ("question", "support request"):
        return LifecycleClassification(
            state="likely-invalid",
            confidence="LOW",
            reasons=("text suggests unsupported usage or non-actionable request",),
        )

    # 4) needs-info
    if any(l in labels for l in ("needs-info", "need info", "needs info")):
        return LifecycleClassification(
            state="needs-info",
            confidence="HIGH",
            reasons=("label indicates missing information",),
        )

    needs_info_reasons: list[str] = []
    if quality.reproducibility < 50:
        needs_info_reasons.append("low reproducibility")
    if quality.completeness < 50:
        needs_info_reasons.append("missing key issue sections")

    if needs_info_reasons:
        return LifecycleClassification(
            state="needs-info",
            confidence="MEDIUM" if len(needs_info_reasons) == 1 else "HIGH",
            reasons=tuple(needs_info_reasons),
        )

    # 5) actionable (default)
    actionable_reasons: list[str] = []
    if triage.category in ("bug", "feature request", "documentation"):
        actionable_reasons.append("triage category is actionable")
    if quality.reproducibility >= 50:
        actionable_reasons.append("reproducibility is sufficient")

    return LifecycleClassification(
        state="actionable",
        confidence="MEDIUM" if actionable_reasons else "LOW",
        reasons=tuple(actionable_reasons) if actionable_reasons else ("default actionable",),
    )


def _text_mentions_blocked(t: str) -> bool:
    return bool(
        re.search(
            r"\b(blocked|blocking|depends on|waiting for|can't proceed|cannot proceed|after we|once we)\b",
            t,
            flags=re.I,
        )
    )


def _text_mentions_invalid(t: str) -> bool:
    return bool(
        re.search(
            r"\b(user error|misuse|unsupported|not a bug|working as intended|wontfix|won't fix)\b",
            t,
            flags=re.I,
        )
    )
