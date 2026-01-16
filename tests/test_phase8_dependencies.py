from __future__ import annotations

from issue_assistant.models import Commit, Issue, IssueAuthor, IssueComment, PullRequest
from issue_assistant.phases.dependencies import DEFAULT_LIMITS, extract_issue_dependencies


def test_dependencies_detect_simple_issue_reference_in_issue_body() -> None:
    issue = Issue(number=1, title="A", body="See #2 for details", author=None)
    links = extract_issue_dependencies(repo="owner/name", issues=[issue], limits=DEFAULT_LIMITS)

    assert any(l.source.kind == "issue" and l.source.identifier == "1" and l.target.kind == "issue" and l.target.identifier == "2" for l in links)


def test_dependencies_detect_cross_repo_reference() -> None:
    issue = Issue(number=1, title="A", body="Related: other/repo#77", author=None)
    links = extract_issue_dependencies(repo="owner/name", issues=[issue], limits=DEFAULT_LIMITS)

    assert any(l.target.repo == "other/repo" and l.target.identifier == "77" for l in links)


def test_dependencies_detect_issue_referencing_pr() -> None:
    issue = Issue(number=1, title="A", body="Fixed by PR #5", author=None)
    links = extract_issue_dependencies(repo="owner/name", issues=[issue], limits=DEFAULT_LIMITS)

    assert any(l.target.kind == "pull_request" and l.target.identifier == "5" for l in links)


def test_dependencies_detect_pr_referencing_issue_in_body_and_comments() -> None:
    pr = PullRequest(
        number=5,
        title="Fix",
        body="Fixes #1",
        author=IssueAuthor(login="dev"),
        comments=(IssueComment(id=1, author=None, body="Also relates to GH-2", created_at=None, updated_at=None),),
    )
    links = extract_issue_dependencies(repo="owner/name", issues=[], pull_requests=[pr], limits=DEFAULT_LIMITS)

    assert any(l.source.kind == "pull_request" and l.source.identifier == "5" and l.target.kind == "issue" and l.target.identifier == "1" for l in links)
    assert any(l.target.kind == "issue" and l.target.identifier == "2" for l in links)


def test_dependencies_detect_commit_message_reference() -> None:
    c = Commit(sha="abc", message="Merge pull request #9 from x\n\nFixes #3")
    links = extract_issue_dependencies(repo="owner/name", issues=[], commits=[c], limits=DEFAULT_LIMITS)

    assert any(l.target.kind == "pull_request" and l.target.identifier == "9" for l in links)
    assert any(l.target.kind == "issue" and l.target.identifier == "3" for l in links)


def test_dependencies_avoid_heading_false_positive() -> None:
    issue = Issue(number=1, title="A", body="#123\nNot a reference", author=None)
    links = extract_issue_dependencies(repo="owner/name", issues=[issue], limits=DEFAULT_LIMITS)

    assert not any(l.target.identifier == "123" for l in links)
