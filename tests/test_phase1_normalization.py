from __future__ import annotations

import json
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
from issue_assistant.phases.normalization import normalize_issue, normalize_title


def test_normalize_title_strips_noise_words_and_symbols() -> None:
    assert normalize_title("🚨 URGENT: Help!!! Bug in login 😭") == "in login"


def test_normalize_issue_extracts_sections_and_code_fence_logs() -> None:
    body = """
### Steps to reproduce
1. Run app
2. Click login

Expected behavior: should login

### Actual behavior
Crashes

```python
Traceback (most recent call last):
  File \"x.py\", line 1
ValueError: boom
```

Environment:
Python 3.11 on Windows
""".strip()

    issue = Issue(number=1, title="Bug: login crash", body=body, author=None)
    n = normalize_issue(issue)

    assert n.sections["reproduction_steps"].startswith("1. Run app")
    assert "should login" in n.sections["expected_behavior"]
    assert "Crashes" in n.sections["actual_behavior"]
    assert "ValueError" in n.sections["logs"]
    assert "Python 3.11" in n.sections["environment"]


def test_artifact_writer_persists_normalized_issue_json(tmp_path: Path) -> None:
    issue = Issue(number=7, title="Help!! 😭 login error", body="", author=None)
    normalized = normalize_issue(issue)

    run = AnalysisRun(
        generated_at=__import__("datetime").datetime(2026, 1, 1),
        repo="owner/name",
        issues=(
            IssueAnalysis(
                issue_number=issue.number,
                normalized=normalized,
                quality=QualityBreakdown(completeness=0, clarity=0, reproducibility=0, noise=100, reasons=()),
                triage=TriageClassification(category="bug", confidence=1.0),
                lifecycle=LifecycleClassification(state="needs-info", confidence="HIGH", reasons=()),
                maintainer_cost=MaintainerCostEstimate(level="low", reasons=(), signals={}),
                duplicates=None,
                maintainer_action=MaintainerAction(recommended_actions=("Review",)),
            ),
        ),
        dependencies=(),
    )

    ArtifactWriter(output_dir=tmp_path).write(run)

    p = tmp_path / "issues" / "7" / "normalized_issue.json"
    assert p.exists()

    payload = json.loads(p.read_text(encoding="utf-8"))
    assert payload["normalized_title"] == "login error"

    qb = tmp_path / "issues" / "7" / "quality_breakdown.json"
    assert qb.exists()
