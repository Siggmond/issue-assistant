from __future__ import annotations

from issue_assistant.models import Issue
from issue_assistant.phases.normalization import normalize_issue
from issue_assistant.phases.quality_breakdown import score_quality_breakdown


def test_quality_breakdown_high_when_sections_present() -> None:
    body = """
### Steps to reproduce
1. Do X
2. Do Y

### Expected behavior
It should succeed

### Actual behavior
It fails with an error

### Environment
Python 3.11, Windows

### Logs
Traceback (most recent call last):
ValueError: boom
""".strip()

    n = normalize_issue(Issue(number=1, title="Bug: crash", body=body, author=None))
    q = score_quality_breakdown(n)

    assert q.completeness >= 80
    assert q.clarity >= 80
    assert q.reproducibility >= 75
    assert q.noise <= 40


def test_quality_breakdown_noise_increases_for_low_signal() -> None:
    n = normalize_issue(Issue(number=2, title="help", body="pls fix", author=None))
    q = score_quality_breakdown(n)

    assert q.noise >= 60
    assert q.completeness <= 40
