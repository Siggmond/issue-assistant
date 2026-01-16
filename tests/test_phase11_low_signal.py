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
from issue_assistant.phases.low_signal import DEFAULT_LIMITS, detect_low_signal_issues
from issue_assistant.phases.normalization import normalize_issue


def _analysis(issue: Issue, *, noise: int) -> IssueAnalysis:
    return IssueAnalysis(
        issue_number=issue.number,
        normalized=normalize_issue(issue),
        quality=QualityBreakdown(completeness=0, clarity=0, reproducibility=0, noise=noise, reasons=()),
        triage=TriageClassification(category="question", confidence=0.5),
        lifecycle=LifecycleClassification(state="needs-info", confidence="HIGH", reasons=()),
        maintainer_cost=MaintainerCostEstimate(level="low", reasons=(), signals={}),
        duplicates=None,
        maintainer_action=MaintainerAction(recommended_actions=("Review",)),
    )


def test_low_signal_detects_spam_keywords() -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=1, title="Free money", body="crypto airdrop click here https://x", author=None, created_at=now)
    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(_analysis(issue, noise=90),), dependencies=())

    report = detect_low_signal_issues(run=run, limits=DEFAULT_LIMITS)
    assert report["items"], "expected at least one low-signal finding"
    assert report["items"][0]["classification"] in ("spam", "low_effort")


def test_low_signal_avoids_false_positive_when_traceback_present() -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=2, title="Crash", body="Traceback (most recent call last):\nValueError: boom", author=None, created_at=now)
    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(_analysis(issue, noise=0),), dependencies=())

    report = detect_low_signal_issues(run=run, limits=DEFAULT_LIMITS)
    assert report["items"] == []


def test_phase11_artifacts_written(tmp_path: Path) -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=3, title="pls fix", body="!!!!", author=None, created_at=now)
    a = _analysis(issue, noise=80)

    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(a,), dependencies=())
    ArtifactWriter(output_dir=tmp_path).write(run)

    md = tmp_path / "LOW_SIGNAL_ISSUES.md"
    js = tmp_path / "low_signal_issues.json"
    assert md.exists()
    assert js.exists()

    payload = json.loads(js.read_text(encoding="utf-8"))
    assert "limits" in payload
    assert "items" in payload
