from __future__ import annotations

from datetime import datetime, timezone

from issue_assistant.models import (
    AnalysisRun,
    Issue,
    IssueAnalysis,
    LifecycleClassification,
    MaintainerAction,
    MaintainerCostEstimate,
    QualityBreakdown,
    TriageClassification,
)
from issue_assistant.phases.normalization import normalize_issue
from issue_assistant.phases.weekly_digest import DEFAULT_LIMITS, build_weekly_digest


def test_weekly_digest_counts_recent_issues() -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)

    i1 = Issue(number=1, title="A", body="", author=None, created_at=now)
    i2 = Issue(number=2, title="B", body="", author=None, created_at=datetime(2025, 12, 1, tzinfo=timezone.utc))

    a1 = IssueAnalysis(
        issue_number=1,
        normalized=normalize_issue(i1),
        quality=QualityBreakdown(completeness=0, clarity=0, reproducibility=0, noise=0, reasons=()),
        triage=TriageClassification(category="bug", confidence=0.9),
        lifecycle=LifecycleClassification(state="needs-info", confidence="HIGH", reasons=()),
        maintainer_cost=MaintainerCostEstimate(level="high", reasons=(), signals={}),
        duplicates=None,
        maintainer_action=MaintainerAction(recommended_actions=("Review",)),
    )
    a2 = IssueAnalysis(
        issue_number=2,
        normalized=normalize_issue(i2),
        quality=QualityBreakdown(completeness=0, clarity=0, reproducibility=0, noise=0, reasons=()),
        triage=TriageClassification(category="bug", confidence=0.9),
        lifecycle=LifecycleClassification(state="actionable", confidence="HIGH", reasons=()),
        maintainer_cost=MaintainerCostEstimate(level="low", reasons=(), signals={}),
        duplicates=None,
        maintainer_action=MaintainerAction(recommended_actions=("Review",)),
    )

    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(a1, a2), dependencies=())
    digest = build_weekly_digest(run=run, now=now, limits=DEFAULT_LIMITS)

    assert digest["recent_issue_count"] == 1
    assert 1 in digest["high_cost_issues"]
    assert 1 in digest["needs_info_issues"]
