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
        triage=TriageClassification(category="bug", confidence=0.9, reasons=("error/bug phrasing",)),
        lifecycle=LifecycleClassification(state="needs-info", confidence="HIGH", reasons=("missing key issue sections",)),
        maintainer_cost=MaintainerCostEstimate(level="high", reasons=("missing reproduction steps",), signals={}),
        duplicates=None,
        maintainer_action=MaintainerAction(recommended_actions=("Request reproduction steps",)),
    )


def test_phase15_artifacts_written(tmp_path: Path) -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=1, title="Crash", body="", author=None, created_at=now)
    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(_analysis(issue),), dependencies=())

    ArtifactWriter(output_dir=tmp_path).write(run)

    md = tmp_path / "EXPLAINABILITY.md"
    js = tmp_path / "explainability.json"
    assert md.exists()
    assert js.exists()

    payload = json.loads(js.read_text(encoding="utf-8"))
    assert "rules" in payload
    assert "per_issue" in payload

    md_txt = md.read_text(encoding="utf-8")
    assert "# Explainability" in md_txt
    assert "## Rule index" in md_txt
    assert "## Per-issue explainability" in md_txt


def test_phase15_per_issue_explainability_shape(tmp_path: Path) -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=2, title="Crash", body="", author=None, created_at=now)
    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(_analysis(issue),), dependencies=())

    ArtifactWriter(output_dir=tmp_path).write(run)

    per_issue = tmp_path / "issues" / "2" / "explainability.json"
    assert per_issue.exists()

    payload = json.loads(per_issue.read_text(encoding="utf-8"))
    assert payload["issue_number"] == 2
    sections = payload.get("sections")
    assert isinstance(sections, dict)

    for required in [
        "normalization",
        "quality",
        "triage",
        "lifecycle",
        "maintainer_cost",
        "maintainer_actions",
        "duplicates",
        "labels",
        "dependencies",
        "playbook",
    ]:
        assert required in sections
        sec = sections[required]
        assert "rules_fired" in sec
        assert "why_this_matters" in sec
        assert "what_this_does_not_imply" in sec
