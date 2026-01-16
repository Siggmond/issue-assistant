from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

import issue_assistant.cli as cli
from issue_assistant.github import GitHubRepoRef
from issue_assistant.models import Issue, IssueAuthor


class FakeGitHubClient:
    def __init__(self, *, token: str) -> None:
        self.token = token
        self.calls: dict[str, int] = {"issue_comments_list": 0, "issue_comment_create": 0, "issues_list": 0, "issue_get": 0}
        self.api_call_counts: dict[str, int] = {
            "http_get": 0,
            "http_post": 0,
            "issues_list": 0,
            "issue_get": 0,
            "issue_comments_list": 0,
            "issue_comment_create": 0,
        }

    def list_issues(
        self,
        repo: GitHubRepoRef,
        *,
        state: str = "open",
        limit: int = 200,
        include_pull_requests: bool = False,
        include_comments: bool = True,
    ) -> list[Issue]:
        self.calls["issues_list"] += 1
        self.api_call_counts["issues_list"] += 1

        now = datetime(2026, 1, 15, tzinfo=timezone.utc)
        # Intentionally out-of-order to ensure pipeline/artifacts stay deterministic.
        issues = [
            Issue(number=2, title="Two", body="", author=IssueAuthor(login="u"), created_at=now),
            Issue(number=1, title="One", body="", author=IssueAuthor(login="u"), created_at=now),
        ]

        if include_comments:
            for i in range(len(issues)):
                self.list_issue_comments(repo, issues[i].number)

        return issues

    def get_issue(self, repo: GitHubRepoRef, number: int, *, include_comments: bool = True) -> Issue:
        self.calls["issue_get"] += 1
        self.api_call_counts["issue_get"] += 1

        now = datetime(2026, 1, 15, tzinfo=timezone.utc)
        issue = Issue(number=int(number), title="X", body="", author=IssueAuthor(login="u"), created_at=now)
        if include_comments:
            self.list_issue_comments(repo, issue.number)
        return issue

    def list_issue_comments(self, repo: GitHubRepoRef, number: int):
        self.calls["issue_comments_list"] += 1
        self.api_call_counts["issue_comments_list"] += 1
        return []

    def create_issue_comment(self, repo: GitHubRepoRef, number: int, *, body: str) -> None:
        self.calls["issue_comment_create"] += 1
        self.api_call_counts["issue_comment_create"] += 1


def test_comments_mode_none_skips_comment_fetching(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGitHubClient(token="t")
    monkeypatch.setattr(cli, "GitHubClient", lambda token: fake)

    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "issue-assistant",
            "analyze",
            "--github-token",
            "t",
            "--repo",
            "o/r",
            "--output-dir",
            str(out_dir),
            "--comments-mode",
            "none",
        ],
    )

    cli.main()

    assert fake.calls["issue_comments_list"] == 0

    payload = json.loads((out_dir / "issues.json").read_text(encoding="utf-8"))
    nums = [int(x["issue"]["number"]) for x in payload["issues"]]
    assert nums == sorted(nums)


def test_dry_run_never_posts_comment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGitHubClient(token="t")
    monkeypatch.setattr(cli, "GitHubClient", lambda token: fake)

    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "issue-assistant",
            "analyze",
            "--github-token",
            "t",
            "--repo",
            "o/r",
            "--issue-number",
            "1",
            "--output-dir",
            str(out_dir),
            "--governance-mode",
            "dry-run",
            "--auto-comment",
            "--comments-mode",
            "all",
        ],
    )

    cli.main()

    assert fake.calls["issue_comment_create"] == 0


def test_comments_mode_needed_fetches_when_comment_dependent_phase_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGitHubClient(token="t")
    monkeypatch.setattr(cli, "GitHubClient", lambda token: fake)

    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "issue-assistant",
            "analyze",
            "--github-token",
            "t",
            "--repo",
            "o/r",
            "--output-dir",
            str(out_dir),
            "--comments-mode",
            "needed",
            "--phases",
            "knowledge_base",
        ],
    )

    cli.main()

    assert fake.calls["issue_comments_list"] > 0


def test_comments_mode_needed_skips_when_only_comment_independent_phases_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGitHubClient(token="t")
    monkeypatch.setattr(cli, "GitHubClient", lambda token: fake)

    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "issue-assistant",
            "analyze",
            "--github-token",
            "t",
            "--repo",
            "o/r",
            "--output-dir",
            str(out_dir),
            "--comments-mode",
            "needed",
            "--phases",
            "weekly_digest",
        ],
    )

    cli.main()

    assert fake.calls["issue_comments_list"] == 0


def test_verbose_warns_when_comments_mode_none_but_comment_dependent_phase_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGitHubClient(token="t")
    monkeypatch.setattr(cli, "GitHubClient", lambda token: fake)

    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "issue-assistant",
            "analyze",
            "--github-token",
            "t",
            "--repo",
            "o/r",
            "--output-dir",
            str(out_dir),
            "--comments-mode",
            "none",
            "--phases",
            "knowledge_base",
            "--verbose",
        ],
    )

    cli.main()

    captured = capsys.readouterr()
    assert "warning: comment-dependent phase enabled" in captured.err
