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
from issue_assistant.phases.normalization import normalize_issue


def test_phase9_phase10_artifacts_written(tmp_path: Path) -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=1, title="A", body="", author=None, created_at=now)
    a = IssueAnalysis(
        issue_number=1,
        normalized=normalize_issue(issue),
        quality=QualityBreakdown(completeness=0, clarity=0, reproducibility=0, noise=0, reasons=()),
        triage=TriageClassification(category="bug", confidence=0.9),
        lifecycle=LifecycleClassification(state="needs-info", confidence="HIGH", reasons=()),
        maintainer_cost=MaintainerCostEstimate(level="high", reasons=(), signals={}),
        duplicates=None,
        maintainer_action=MaintainerAction(recommended_actions=("Review",)),
    )

    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(a,), dependencies=())
    ArtifactWriter(output_dir=tmp_path).write(run)

    md9 = tmp_path / "WEEKLY_DIGEST.md"
    js9 = tmp_path / "weekly_digest.json"
    md10 = tmp_path / "ISSUE_HEALTH.md"
    js10 = tmp_path / "issue_health.json"

    assert md9.exists()
    assert js9.exists()
    assert md10.exists()
    assert js10.exists()

    payload9 = json.loads(js9.read_text(encoding="utf-8"))
    assert "limits" in payload9

    payload10 = json.loads(js10.read_text(encoding="utf-8"))
    assert "limits" in payload10
