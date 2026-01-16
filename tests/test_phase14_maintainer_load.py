from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from issue_assistant.artifacts import ArtifactWriter
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
from issue_assistant.phases.maintainer_load import compute_maintainer_load
from issue_assistant.phases.normalization import normalize_issue


def _analysis(issue: Issue, *, cost: str, lifecycle: str, noise: int) -> IssueAnalysis:
    return IssueAnalysis(
        issue_number=issue.number,
        normalized=normalize_issue(issue),
        quality=QualityBreakdown(completeness=0, clarity=0, reproducibility=0, noise=noise, reasons=()),
        triage=TriageClassification(category="bug", confidence=0.9),
        lifecycle=LifecycleClassification(state=lifecycle, confidence="HIGH", reasons=()),
        maintainer_cost=MaintainerCostEstimate(level=cost, reasons=(), signals={}),
        duplicates=None,
        maintainer_action=MaintainerAction(recommended_actions=("Review",)),
    )


def test_compute_maintainer_load_counts() -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)

    issues = [
        _analysis(Issue(number=1, title="A", body="", author=None, created_at=now), cost="high", lifecycle="needs-info", noise=80),
        _analysis(Issue(number=2, title="B", body="", author=None, created_at=now), cost="high", lifecycle="stale", noise=0),
        _analysis(Issue(number=3, title="C", body="", author=None, created_at=now), cost="low", lifecycle="actionable", noise=0),
    ]

    run = AnalysisRun(generated_at=now, repo="owner/name", issues=tuple(issues), dependencies=())
    report = compute_maintainer_load(run=run)

    counts = report["counts"]
    assert counts["total_issues"] == 3
    assert counts["high_cost"] == 2
    assert counts["needs_info"] == 1
    assert counts["stale"] == 1


def test_phase14_artifacts_written(tmp_path: Path) -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=1, title="A", body="", author=None, created_at=now)
    a = _analysis(issue, cost="high", lifecycle="needs-info", noise=80)
    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(a,), dependencies=())

    ArtifactWriter(output_dir=tmp_path).write(run)

    md = tmp_path / "MAINTAINER_LOAD.md"
    js = tmp_path / "maintainer_load.json"
    assert md.exists()
    assert js.exists()

    payload = json.loads(js.read_text(encoding="utf-8"))
    assert "limits" in payload
    assert "counts" in payload
    assert "level" in payload
