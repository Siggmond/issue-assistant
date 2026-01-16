from __future__ import annotations

from datetime import datetime, timedelta, timezone

from issue_assistant.models import Issue, QualityBreakdown, TriageClassification
from issue_assistant.phases.normalization import normalize_issue
from issue_assistant.phases.lifecycle import classify_lifecycle


def test_lifecycle_needs_info_when_low_reproducibility() -> None:
    issue = Issue(number=1, title="Bug: crash", body="it crashes", author=None)
    n = normalize_issue(issue)

    q = QualityBreakdown(completeness=20, clarity=0, reproducibility=0, noise=80, reasons=())
    t = TriageClassification(category="bug", confidence=0.9)

    lc = classify_lifecycle(normalized=n, quality=q, triage=t, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert lc.state == "needs-info"
    assert lc.confidence in ("HIGH", "MEDIUM")


def test_lifecycle_stale_when_no_updates_over_limit() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    old = now - timedelta(days=120)

    issue = Issue(
        number=2,
        title="Bug: old",
        body="Steps to reproduce: ...",
        author=None,
        state="open",
        created_at=old,
        updated_at=old,
    )
    n = normalize_issue(issue)

    q = QualityBreakdown(completeness=80, clarity=80, reproducibility=75, noise=0, reasons=())
    t = TriageClassification(category="bug", confidence=0.9)

    lc = classify_lifecycle(normalized=n, quality=q, triage=t, now=now)
    assert lc.state == "stale"


def test_lifecycle_blocked_when_text_mentions_dependency() -> None:
    issue = Issue(number=3, title="Blocked", body="This is blocked: depends on #123", author=None)
    n = normalize_issue(issue)

    q = QualityBreakdown(completeness=80, clarity=80, reproducibility=75, noise=0, reasons=())
    t = TriageClassification(category="bug", confidence=0.9)

    lc = classify_lifecycle(normalized=n, quality=q, triage=t, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert lc.state == "blocked"
