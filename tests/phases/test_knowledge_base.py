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
from issue_assistant.phases.knowledge_base import DEFAULT_LIMITS, build_knowledge_base
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


def test_build_knowledge_base_extracts_error_signatures_and_files() -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)

    issue1 = Issue(
        number=1,
        title="Crash",
        body="Traceback (most recent call last):\nValueError: boom\nSee src/app/main.py",
        author=None,
        created_at=now,
    )
    issue2 = Issue(
        number=2,
        title="Another crash",
        body="ValueError: boom\nAlso mentions config.toml",
        author=None,
        created_at=now,
    )

    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(_analysis(issue1), _analysis(issue2)), dependencies=())

    kb = build_knowledge_base(run=run, limits=DEFAULT_LIMITS)

    errs = kb.get("top_error_signatures")
    assert isinstance(errs, list)
    assert errs, "expected at least one error signature"

    sig_texts = [e.get("signature") for e in errs if isinstance(e, dict)]
    assert any(isinstance(s, str) and "ValueError" in s for s in sig_texts)

    files = kb.get("top_mentioned_files")
    assert isinstance(files, list)
    file_names = [f.get("file") for f in files if isinstance(f, dict)]
    assert "src/app/main.py" in file_names
    assert "config.toml" in file_names


def test_phase12_artifacts_written(tmp_path: Path) -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=1, title="How to use?", body="How do I configure this?", author=None, created_at=now)
    run = AnalysisRun(generated_at=now, repo="owner/name", issues=(_analysis(issue),), dependencies=())

    ArtifactWriter(output_dir=tmp_path).write(run)

    md = tmp_path / "KNOWLEDGE_BASE.md"
    js = tmp_path / "knowledge_base.json"
    assert md.exists()
    assert js.exists()

    payload = json.loads(js.read_text(encoding="utf-8"))
    assert "limits" in payload
    assert "top_error_signatures" in payload
    assert "top_mentioned_files" in payload
    assert "faq_patterns" in payload
