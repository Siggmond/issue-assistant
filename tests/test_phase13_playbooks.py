from __future__ import annotations

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


def _analysis(issue: Issue, *, triage: str, lifecycle: str, noise: int, completeness: int, reproducibility: int) -> IssueAnalysis:
    return IssueAnalysis(
        issue_number=issue.number,
        normalized=normalize_issue(issue),
        quality=QualityBreakdown(
            completeness=completeness,
            clarity=0,
            reproducibility=reproducibility,
            noise=noise,
            reasons=(),
        ),
        triage=TriageClassification(category=triage, confidence=0.9),
        lifecycle=LifecycleClassification(state=lifecycle, confidence="HIGH", reasons=()),
        maintainer_cost=MaintainerCostEstimate(level="low", reasons=(), signals={}),
        duplicates=None,
        maintainer_action=MaintainerAction(recommended_actions=("Review",)),
    )


def test_phase13_artifacts_written(tmp_path: Path) -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)

    issue = Issue(
        number=1,
        title="How to configure?",
        body="How do I configure this?",
        author=None,
        created_at=now,
    )
    a = _analysis(issue, triage="support request", lifecycle="needs-info", noise=80, completeness=0, reproducibility=0)

    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(a,), dependencies=())
    ArtifactWriter(output_dir=tmp_path).write(run)

    md = tmp_path / "MAINTAINER_PLAYBOOKS.md"
    assert md.exists()

    per_issue = tmp_path / "issues" / "1" / "playbook.md"
    assert per_issue.exists()

    txt = md.read_text(encoding="utf-8")
    assert "# Maintainer Playbooks" in txt
    assert "## Global playbooks" in txt
    assert "## Per-issue playbooks" in txt
    assert "issues/1/playbook.md" in txt

    ptxt = per_issue.read_text(encoding="utf-8")
    assert "## When to use" in ptxt
    assert "## Why this playbook was selected" in ptxt
    assert "## What this does not cover" in ptxt
