from __future__ import annotations

from dataclasses import dataclass

from ..models import AnalysisRun


@dataclass(frozen=True)
class HealthLimits:
    max_examples_per_metric: int = 25


DEFAULT_LIMITS = HealthLimits()


def compute_issue_health(*, run: AnalysisRun, limits: HealthLimits = DEFAULT_LIMITS) -> dict[str, object]:
    total = len(run.issues)
    if total == 0:
        return {
            "generated_at": run.generated_at.isoformat(),
            "repo": run.repo,
            "total_issues": 0,
            "metrics": {},
            "limits": {
                "max_examples_per_metric": int(limits.max_examples_per_metric),
                "not_detected": [
                    "PR review / CI signals",
                    "maintainer workload outside issues",
                ],
            },
        }

    needs_info = [a.issue_number for a in run.issues if a.lifecycle.state == "needs-info"]
    stale = [a.issue_number for a in run.issues if a.lifecycle.state == "stale"]
    blocked = [a.issue_number for a in run.issues if a.lifecycle.state == "blocked"]
    duplicates = [a.issue_number for a in run.issues if a.duplicates is not None and a.duplicates.likely_duplicates_of]

    avg_repro = sum(a.quality.reproducibility for a in run.issues) / total
    avg_complete = sum(a.quality.completeness for a in run.issues) / total

    cost_map = {"low": 1, "medium": 2, "high": 3}
    avg_cost = sum(cost_map.get(a.maintainer_cost.level, 2) for a in run.issues) / total

    def pct(x: int) -> float:
        return round((100.0 * x) / total, 2)

    return {
        "generated_at": run.generated_at.isoformat(),
        "repo": run.repo,
        "total_issues": total,
        "metrics": {
            "needs_info_pct": pct(len(needs_info)),
            "stale_pct": pct(len(stale)),
            "blocked_pct": pct(len(blocked)),
            "duplicate_pct": pct(len(duplicates)),
            "avg_quality_reproducibility": round(avg_repro, 2),
            "avg_quality_completeness": round(avg_complete, 2),
            "avg_maintainer_cost_score": round(avg_cost, 2),
            "examples": {
                "needs_info": needs_info[: limits.max_examples_per_metric],
                "stale": stale[: limits.max_examples_per_metric],
                "blocked": blocked[: limits.max_examples_per_metric],
                "duplicates": duplicates[: limits.max_examples_per_metric],
            },
        },
        "limits": {
            "max_examples_per_metric": int(limits.max_examples_per_metric),
            "not_detected": [
                "PR review / CI signals",
                "maintainer workload outside issues",
                "severity/impact unless explicitly described",
            ],
        },
    }


def render_issue_health_md(*, health: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Issue Health")
    lines.append("")

    repo = health.get("repo")
    if repo:
        lines.append(f"Repository: `{repo}`")
        lines.append("")

    lines.append(f"Total issues analyzed: **{health.get('total_issues')}**")
    lines.append("")

    metrics = health.get("metrics") if isinstance(health.get("metrics"), dict) else {}
    lines.append("## Metrics")
    lines.append("")

    for k in [
        "needs_info_pct",
        "stale_pct",
        "blocked_pct",
        "duplicate_pct",
        "avg_quality_reproducibility",
        "avg_quality_completeness",
        "avg_maintainer_cost_score",
    ]:
        if k in metrics:
            lines.append(f"- {k}: `{metrics[k]}`")

    lines.append("")

    examples = metrics.get("examples") if isinstance(metrics.get("examples"), dict) else {}
    if examples:
        lines.append("## Examples")
        lines.append("")
        for section in ["needs_info", "stale", "blocked", "duplicates"]:
            vals = examples.get(section) if isinstance(examples.get(section), list) else []
            lines.append(f"### {section}")
            if vals:
                for n in vals:
                    lines.append(f"- #{n}")
            else:
                lines.append("- (none)")
            lines.append("")

    limits = health.get("limits") if isinstance(health.get("limits"), dict) else {}
    lines.append("## Limits")
    lines.append("")
    lines.append(f"- max_examples_per_metric: `{limits.get('max_examples_per_metric')}`")
    lines.append("")

    not_detected = limits.get("not_detected") if isinstance(limits.get("not_detected"), list) else []
    if not_detected:
        lines.append("Not detected:")
        for item in not_detected:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
