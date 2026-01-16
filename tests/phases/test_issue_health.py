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
from issue_assistant.phases.issue_health import DEFAULT_LIMITS, compute_issue_health
from issue_assistant.phases.normalization import normalize_issue


def test_issue_health_metrics_present() -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)

    issue = Issue(number=1, title="A", body="", author=None, created_at=now)
    a = IssueAnalysis(
        issue_number=1,
        normalized=normalize_issue(issue),
        quality=QualityBreakdown(completeness=50, clarity=50, reproducibility=100, noise=0, reasons=()),
        triage=TriageClassification(category="bug", confidence=0.9),
        lifecycle=LifecycleClassification(state="needs-info", confidence="HIGH", reasons=()),
        maintainer_cost=MaintainerCostEstimate(level="medium", reasons=(), signals={}),
        duplicates=None,
        maintainer_action=MaintainerAction(recommended_actions=("Review",)),
    )

    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(a,), dependencies=())
    health = compute_issue_health(run=run, limits=DEFAULT_LIMITS)

    metrics = health["metrics"]
    assert "needs_info_pct" in metrics
    assert metrics["needs_info_pct"] == 100.0
    assert "avg_quality_reproducibility" in metrics
