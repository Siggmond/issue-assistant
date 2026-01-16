from __future__ import annotations

from issue_assistant.models import (
    Issue,
    IssueAnalysis,
    LifecycleClassification,
    MaintainerAction,
    MaintainerCostEstimate,
    QualityBreakdown,
    TriageClassification,
)
from issue_assistant.phases.normalization import normalize_issue
from issue_assistant.phases.contributor_guide import render_contributor_guide


def test_contributor_guide_includes_checklist_for_missing_sections() -> None:
    issue = Issue(number=10, title="Bug: crash", body="pls fix", author=None)
    n = normalize_issue(issue)

    a = IssueAnalysis(
        issue_number=issue.number,
        normalized=n,
        quality=QualityBreakdown(completeness=0, clarity=0, reproducibility=0, noise=80, reasons=()),
        triage=TriageClassification(category="bug", confidence=0.9),
        lifecycle=LifecycleClassification(state="needs-info", confidence="HIGH", reasons=()),
        maintainer_cost=MaintainerCostEstimate(level="medium", reasons=(), signals={}),
        duplicates=None,
        maintainer_action=MaintainerAction(recommended_actions=("Request info",)),
    )

    md = render_contributor_guide(a)
    assert "Reproduction steps" in md
    assert "Environment details" in md
    assert "Logs / stack trace" in md
