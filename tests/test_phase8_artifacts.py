from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from issue_assistant.artifacts import ArtifactWriter
from issue_assistant.models import (
    AnalysisRun,
    Commit,
    Issue,
    IssueAnalysis,
    LifecycleClassification,
    MaintainerAction,
    MaintainerCostEstimate,
    QualityBreakdown,
    TriageClassification,
)
from issue_assistant.phases.normalization import normalize_issue
from issue_assistant.phases.dependencies import DEFAULT_LIMITS, extract_issue_dependencies


def test_artifacts_write_issue_dependencies_files(tmp_path: Path) -> None:
    issue = Issue(number=1, title="A", body="See #2", author=None)
    n = normalize_issue(issue)

    a = IssueAnalysis(
        issue_number=1,
        normalized=n,
        quality=QualityBreakdown(completeness=0, clarity=0, reproducibility=0, noise=0, reasons=()),
        triage=TriageClassification(category="bug", confidence=0.9),
        lifecycle=LifecycleClassification(state="actionable", confidence="MEDIUM", reasons=()),
        maintainer_cost=MaintainerCostEstimate(level="low", reasons=(), signals={}),
        duplicates=None,
        maintainer_action=MaintainerAction(recommended_actions=("Review",)),
    )

    deps = extract_issue_dependencies(repo="owner/name", issues=[issue], commits=[Commit(sha="x", message="Fixes #3")], limits=DEFAULT_LIMITS)

    run = AnalysisRun(
        generated_at=__import__("datetime").datetime(2026, 1, 1),
        repo="owner/name",
        issues=(a,),
        dependencies=deps,
    )

    ArtifactWriter(output_dir=tmp_path).write(run)

    md = tmp_path / "ISSUE_DEPENDENCIES.md"
    js = tmp_path / "issue_dependencies.json"
    assert md.exists()
    assert js.exists()

    payload = json.loads(js.read_text(encoding="utf-8"))
    assert "limits" in payload
    assert "links" in payload
    assert any(l["target"]["identifier"] in ("2", "3") for l in payload["links"])
