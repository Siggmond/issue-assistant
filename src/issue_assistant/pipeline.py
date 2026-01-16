from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AnalysisRun,
    DuplicateLink,
    Issue,
    IssueAnalysis,
    MaintainerAction,
    NormalizedIssue,
    QualityBreakdown,
    TriageClassification,
)
from .phases.actions import recommend_actions
from .phases.dependencies import DEFAULT_LIMITS as DEP_LIMITS
from .phases.dependencies import extract_issue_dependencies
from .phases.duplicates import detect_duplicates_v2
from .phases.lifecycle import classify_lifecycle
from .phases.maintainer_cost import estimate_maintainer_cost
from .phases.normalization import normalize_issue
from .phases.quality_breakdown import score_quality_breakdown
from .phases.triage import classify_issue


def analyze_issues(
    *,
    issues: list[Issue],
    repo: str | None,
    pull_requests: list["PullRequest"] | None = None,
    commits: list["Commit"] | None = None,
    governance_mode: str = "dry-run",
) -> AnalysisRun:
    normalized = [normalize_issue(i) for i in issues]
    quality = {n.issue.number: score_quality_breakdown(n) for n in normalized}
    triage = {n.issue.number: classify_issue(n) for n in normalized}
    lifecycle = {n.issue.number: classify_lifecycle(normalized=n, quality=quality[n.issue.number], triage=triage[n.issue.number]) for n in normalized}
    cost = {n.issue.number: estimate_maintainer_cost(normalized=n, quality=quality[n.issue.number]) for n in normalized}

    dup_map: dict[int, DuplicateLink] = detect_duplicates_v2(normalized)

    analyses: list[IssueAnalysis] = []
    for n in normalized:
        num = n.issue.number
        analyses.append(
            IssueAnalysis(
                issue_number=num,
                normalized=n,
                quality=quality[num],
                triage=triage[num],
                lifecycle=lifecycle[num],
                maintainer_cost=cost[num],
                duplicates=dup_map.get(num),
                maintainer_action=_actions(n, quality[num], triage[num]),
            )
        )

    analyses.sort(key=lambda a: a.issue_number)

    deps = extract_issue_dependencies(
        repo=repo,
        issues=issues,
        pull_requests=pull_requests,
        commits=commits,
        limits=DEP_LIMITS,
    )

    return AnalysisRun(
        generated_at=datetime.now(tz=timezone.utc),
        repo=repo,
        issues=tuple(analyses),
        dependencies=deps,
        governance_mode=governance_mode,
    )


def _actions(n: NormalizedIssue, q: QualityBreakdown, t: TriageClassification) -> MaintainerAction:
    return recommend_actions(normalized=n, quality=q, triage=t)
