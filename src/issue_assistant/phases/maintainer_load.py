from __future__ import annotations

from dataclasses import dataclass

from ..models import AnalysisRun, IssueAnalysis


@dataclass(frozen=True)
class MaintainerLoadLimits:
    max_examples_per_bucket: int = 10


DEFAULT_LIMITS = MaintainerLoadLimits()


def compute_maintainer_load(*, run: AnalysisRun, limits: MaintainerLoadLimits = DEFAULT_LIMITS) -> dict[str, object]:
    total = len(run.issues)

    high_cost: list[int] = []
    needs_info: list[int] = []
    stale: list[int] = []
    blocked: list[int] = []
    duplicates: list[int] = []
    low_signal: list[int] = []

    for a in run.issues:
        if a.maintainer_cost.level == "high":
            high_cost.append(a.issue_number)
        if a.lifecycle.state == "needs-info":
            needs_info.append(a.issue_number)
        if a.lifecycle.state == "stale":
            stale.append(a.issue_number)
        if a.lifecycle.state == "blocked":
            blocked.append(a.issue_number)
        if a.duplicates is not None and a.duplicates.likely_duplicates_of:
            duplicates.append(a.issue_number)
        if _is_low_signal(a):
            low_signal.append(a.issue_number)

    dep_links_total = len(run.dependencies)

    # Deterministic scoring (no probabilities)
    score = 0
    reasons: list[str] = []

    if len(high_cost) >= 5:
        score += 2
        reasons.append("many high maintainer-cost issues")
    elif len(high_cost) >= 2:
        score += 1
        reasons.append("some high maintainer-cost issues")

    if len(needs_info) >= 10:
        score += 2
        reasons.append("large needs-info backlog")
    elif len(needs_info) >= 3:
        score += 1
        reasons.append("some needs-info backlog")

    if len(stale) >= 10:
        score += 2
        reasons.append("many stale issues")
    elif len(stale) >= 3:
        score += 1
        reasons.append("some stale issues")

    if len(blocked) >= 5:
        score += 1
        reasons.append("many blocked issues")

    if len(duplicates) >= 5:
        score += 1
        reasons.append("high duplicate volume")

    if len(low_signal) >= 10:
        score += 1
        reasons.append("many low-signal issues")

    if dep_links_total >= 50:
        score += 1
        reasons.append("many dependency links")

    if total >= 50:
        score += 1
        reasons.append("large total issue set")

    if score >= 6:
        level = "high"
    elif score >= 3:
        level = "medium"
    else:
        level = "low"

    return {
        "generated_at": run.generated_at.isoformat(),
        "repo": run.repo,
        "level": level,
        "score": score,
        "reasons": reasons,
        "counts": {
            "total_issues": total,
            "high_cost": len(high_cost),
            "needs_info": len(needs_info),
            "stale": len(stale),
            "blocked": len(blocked),
            "duplicates": len(duplicates),
            "low_signal": len(low_signal),
            "dependency_links": dep_links_total,
        },
        "examples": {
            "high_cost": sorted(high_cost)[: limits.max_examples_per_bucket],
            "needs_info": sorted(needs_info)[: limits.max_examples_per_bucket],
            "stale": sorted(stale)[: limits.max_examples_per_bucket],
            "blocked": sorted(blocked)[: limits.max_examples_per_bucket],
            "duplicates": sorted(duplicates)[: limits.max_examples_per_bucket],
            "low_signal": sorted(low_signal)[: limits.max_examples_per_bucket],
        },
        "limits": {
            "max_examples_per_bucket": int(limits.max_examples_per_bucket),
            "not_detected": [
                "maintainer availability, time zones, PTO",
                "review queue / CI load (unless explicitly ingested)",
                "sentiment or emotional tone",
                "issue age distribution unless captured in lifecycle",
            ],
        },
    }


def render_maintainer_load_md(*, report: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Maintainer Load")
    lines.append("")

    repo = report.get("repo")
    if repo:
        lines.append(f"Repository: `{repo}`")
        lines.append("")

    lines.append(f"Generated at: `{report.get('generated_at')}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"Estimated load level: **{str(report.get('level')).upper()}**")
    lines.append(f"Deterministic score: `{report.get('score')}`")
    lines.append("")

    reasons = report.get("reasons") if isinstance(report.get("reasons"), list) else []
    if reasons:
        lines.append("Reasons:")
        for r in reasons:
            lines.append(f"- {r}")
        lines.append("")

    counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
    lines.append("## Counts")
    lines.append("")
    for k in [
        "total_issues",
        "high_cost",
        "needs_info",
        "stale",
        "blocked",
        "duplicates",
        "low_signal",
        "dependency_links",
    ]:
        lines.append(f"- {k}: {counts.get(k)}")
    lines.append("")

    examples = report.get("examples") if isinstance(report.get("examples"), dict) else {}
    lines.append("## Examples")
    lines.append("")
    for bucket in ["high_cost", "needs_info", "stale", "blocked", "duplicates", "low_signal"]:
        nums = examples.get(bucket) if isinstance(examples.get(bucket), list) else []
        lines.append(f"### {bucket}")
        if nums:
            for n in nums:
                lines.append(f"- #{n}")
        else:
            lines.append("- (none)")
        lines.append("")

    lines.append("## Limits")
    lines.append("")
    limits = report.get("limits") if isinstance(report.get("limits"), dict) else {}
    lines.append(f"- max_examples_per_bucket: `{limits.get('max_examples_per_bucket')}`")
    lines.append("")

    not_detected = limits.get("not_detected") if isinstance(limits.get("not_detected"), list) else []
    if not_detected:
        lines.append("Not detected:")
        for x in not_detected:
            lines.append(f"- {x}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _is_low_signal(a: IssueAnalysis) -> bool:
    if a.normalized.is_low_signal:
        return True
    if a.quality.noise >= 70:
        return True
    return False
