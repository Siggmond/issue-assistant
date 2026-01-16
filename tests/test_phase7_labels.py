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
from issue_assistant.phases.labels import labels_to_json, recommend_labels


def test_label_recommendations_include_type_and_needs_info() -> None:
    issue = Issue(number=1, title="Bug: crash", body="pls fix", author=None)
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

    labels = recommend_labels(a)
    payload = labels_to_json(labels)

    names = {l["name"] for l in payload["labels"]}
    assert "bug" in names
    assert "needs-info" in names
    assert "triage" in names
