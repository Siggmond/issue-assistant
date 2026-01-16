from __future__ import annotations

from datetime import datetime, timezone

from issue_assistant.automation import decide_auto_comment
from issue_assistant.models import (
    Issue,
    IssueAnalysis,
    IssueAuthor,
    IssueComment,
    LifecycleClassification,
    MaintainerAction,
    MaintainerCostEstimate,
    NormalizedIssue,
    QualityBreakdown,
    TriageClassification,
)


def _analysis(*, issue: Issue, lifecycle_state: str = "actionable", is_low_signal: bool = False, noise: int = 0, duplicates: bool = False) -> IssueAnalysis:
    normalized = NormalizedIssue(
        issue=issue,
        normalized_title=(issue.title or "").lower(),
        sections={},
        is_low_signal=is_low_signal,
        low_signal_reasons=(),
    )

    lifecycle = LifecycleClassification(state=lifecycle_state, confidence="HIGH", reasons=())

    dup = None
    if duplicates:
        from issue_assistant.models import DuplicateLink

        dup = DuplicateLink(issue_number=issue.number, likely_duplicates_of=(2,), similarity_reasons=("same title",))

    return IssueAnalysis(
        issue_number=issue.number,
        normalized=normalized,
        quality=QualityBreakdown(completeness=0, clarity=0, reproducibility=0, noise=noise, reasons=()),
        triage=TriageClassification(category="bug", confidence=1.0, reasons=()),
        lifecycle=lifecycle,
        maintainer_cost=MaintainerCostEstimate(level="low", reasons=(), signals={}),
        duplicates=dup,
        maintainer_action=MaintainerAction(recommended_actions=()),
    )


def test_autocomment_dry_run_never_comments() -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=1, title="A", body="", author=IssueAuthor(login="u"), created_at=now)
    a = _analysis(issue=issue, lifecycle_state="needs-info")

    d = decide_auto_comment(governance_mode="dry-run", analysis=a)
    assert d.should_comment is False
    assert d.body is None


def test_autocomment_strict_only_when_triggered() -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=1, title="A", body="ok", author=IssueAuthor(login="u"), created_at=now)

    a_ok = _analysis(issue=issue, lifecycle_state="actionable")
    d_ok = decide_auto_comment(governance_mode="strict", analysis=a_ok)
    assert d_ok.should_comment is False

    a_need = _analysis(issue=issue, lifecycle_state="needs-info")
    d_need = decide_auto_comment(governance_mode="strict", analysis=a_need)
    assert d_need.should_comment is True
    assert d_need.body is not None
    assert "Explainability rules referenced" in d_need.body


def test_autocomment_aggressive_includes_label_suggestions_line() -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(number=1, title="Bug", body="", author=IssueAuthor(login="u"), created_at=now)
    a = _analysis(issue=issue, lifecycle_state="needs-info")

    d = decide_auto_comment(governance_mode="aggressive", analysis=a)
    assert d.should_comment is True
    assert d.body is not None
    assert "Suggested labels" in d.body


def test_autocomment_does_not_repeat_if_marker_present() -> None:
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    issue = Issue(
        number=1,
        title="A",
        body="",
        author=IssueAuthor(login="u"),
        created_at=now,
        comments=(
            IssueComment(
                id=1,
                author=IssueAuthor(login="issue-assistant"),
                body="<!-- issue-assistant:auto-comment -->\nprior",
                created_at=now,
                updated_at=now,
            ),
        ),
    )
    a = _analysis(issue=issue, lifecycle_state="needs-info")

    d = decide_auto_comment(governance_mode="strict", analysis=a)
    assert d.should_comment is False
