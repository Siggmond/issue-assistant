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


def _analysis(issue: Issue) -> IssueAnalysis:
    return IssueAnalysis(
        issue_number=issue.number,
        normalized=normalize_issue(issue),
        quality=QualityBreakdown(completeness=0, clarity=0, reproducibility=0, noise=0, reasons=()),
        triage=TriageClassification(category="bug", confidence=0.9),
        lifecycle=LifecycleClassification(state="actionable", confidence="HIGH", reasons=()),
        maintainer_cost=MaintainerCostEstimate(level="low", reasons=(), signals={}),
        duplicates=None,
        maintainer_action=MaintainerAction(recommended_actions=("Review",)),
    )


def test_governance_mode_propagates_to_artifacts(tmp_path: Path) -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=1, title="A", body="", author=None, created_at=now)

    run = AnalysisRun(
        generated_at=now,
        repo="owner/name",
        issues=(_analysis(issue),),
        dependencies=(),
        governance_mode="strict",
    )

    ArtifactWriter(output_dir=tmp_path).write(run)

    # Top-level JSON
    payload = json.loads((tmp_path / "quality_breakdown.json").read_text(encoding="utf-8"))
    assert payload["governance_mode"] == "strict"

    # Top-level Markdown
    txt = (tmp_path / "ISSUE_SUMMARY.md").read_text(encoding="utf-8")
    assert "Governance mode: `strict`" in txt

    # Per-issue JSON
    per = json.loads((tmp_path / "issues" / "1" / "maintainer_cost.json").read_text(encoding="utf-8"))
    assert per["governance_mode"] == "strict"

    # Per-issue Markdown
    pmd = (tmp_path / "issues" / "1" / "CONTRIBUTOR_GUIDE.md").read_text(encoding="utf-8")
    assert "Governance mode: `strict`" in pmd
