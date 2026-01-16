from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..models import AnalysisRun


@dataclass(frozen=True)
class WeeklyDigestLimits:
    lookback_days: int = 7
    max_items_per_section: int = 25


DEFAULT_LIMITS = WeeklyDigestLimits()


def build_weekly_digest(*, run: AnalysisRun, now: datetime | None = None, limits: WeeklyDigestLimits = DEFAULT_LIMITS) -> dict[str, object]:
    now2 = now or run.generated_at
    if now2.tzinfo is None:
        now2 = now2.replace(tzinfo=timezone.utc)

    since = now2 - timedelta(days=int(limits.lookback_days))

    recent = []
    for a in run.issues:
        i = a.normalized.issue
        ts = i.updated_at or i.created_at
        if ts is None:
            continue
        ts2 = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        if ts2 >= since:
            recent.append(a)

    recent.sort(key=lambda a: ((a.normalized.issue.updated_at or a.normalized.issue.created_at or now2).isoformat(), a.issue_number))

    counts_by_triage: dict[str, int] = {}
    counts_by_lifecycle: dict[str, int] = {}
    high_cost: list[int] = []
    needs_info: list[int] = []

    for a in recent:
        counts_by_triage[a.triage.category] = counts_by_triage.get(a.triage.category, 0) + 1
        counts_by_lifecycle[a.lifecycle.state] = counts_by_lifecycle.get(a.lifecycle.state, 0) + 1
        if a.maintainer_cost.level == "high":
            high_cost.append(a.issue_number)
        if a.lifecycle.state == "needs-info":
            needs_info.append(a.issue_number)

    high_cost = high_cost[: limits.max_items_per_section]
    needs_info = needs_info[: limits.max_items_per_section]

    return {
        "generated_at": now2.isoformat(),
        "repo": run.repo,
        "window": {
            "since": since.isoformat(),
            "until": now2.isoformat(),
            "lookback_days": int(limits.lookback_days),
        },
        "recent_issue_count": len(recent),
        "counts_by_triage": dict(sorted(counts_by_triage.items())),
        "counts_by_lifecycle": dict(sorted(counts_by_lifecycle.items())),
        "high_cost_issues": high_cost,
        "needs_info_issues": needs_info,
        "limits": {
            "lookback_days": int(limits.lookback_days),
            "max_items_per_section": int(limits.max_items_per_section),
            "not_detected": [
                "activity based on GitHub timeline events",
                "PR review/CI status unless explicitly ingested",
            ],
        },
    }


def render_weekly_digest_md(*, digest: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Weekly Digest")
    lines.append("")

    repo = digest.get("repo")
    if repo:
        lines.append(f"Repository: `{repo}`")
        lines.append("")

    window = digest.get("window") if isinstance(digest.get("window"), dict) else {}
    lines.append("## Window")
    lines.append("")
    lines.append(f"- since: `{window.get('since')}`")
    lines.append(f"- until: `{window.get('until')}`")
    lines.append(f"- lookback_days: `{window.get('lookback_days')}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"Recent issues (updated/created in window): **{digest.get('recent_issue_count')}**")
    lines.append("")

    lines.append("## Counts")
    lines.append("")

    triage = digest.get("counts_by_triage") if isinstance(digest.get("counts_by_triage"), dict) else {}
    lifecycle = digest.get("counts_by_lifecycle") if isinstance(digest.get("counts_by_lifecycle"), dict) else {}

    lines.append("### By triage")
    if triage:
        for k in sorted(triage.keys()):
            lines.append(f"- {k}: {triage[k]}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("### By lifecycle")
    if lifecycle:
        for k in sorted(lifecycle.keys()):
            lines.append(f"- {k}: {lifecycle[k]}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Focus")
    lines.append("")

    high = digest.get("high_cost_issues") if isinstance(digest.get("high_cost_issues"), list) else []
    ni = digest.get("needs_info_issues") if isinstance(digest.get("needs_info_issues"), list) else []

    lines.append("### High maintainer-cost issues")
    if high:
        for n in high:
            lines.append(f"- #{n}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("### Needs-info issues")
    if ni:
        for n in ni:
            lines.append(f"- #{n}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Limits")
    lines.append("")
    limits = digest.get("limits") if isinstance(digest.get("limits"), dict) else {}
    lines.append(f"- lookback_days: `{limits.get('lookback_days')}`")
    lines.append(f"- max_items_per_section: `{limits.get('max_items_per_section')}`")
    lines.append("")

    not_detected = limits.get("not_detected") if isinstance(limits.get("not_detected"), list) else []
    if not_detected:
        lines.append("Not detected:")
        for item in not_detected:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
