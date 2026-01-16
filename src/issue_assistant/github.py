from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .models import Issue, IssueAuthor, IssueComment, IssueLabel


@dataclass(frozen=True)
class GitHubRepoRef:
    owner: str
    name: str

    @staticmethod
    def parse(s: str) -> "GitHubRepoRef":
        raw = (s or "").strip()
        if "/" not in raw:
            raise ValueError("repo must be in the form 'owner/name'")
        owner, name = raw.split("/", 1)
        owner = owner.strip()
        name = name.strip()
        if not owner or not name:
            raise ValueError("repo must be in the form 'owner/name'")
        return GitHubRepoRef(owner=owner, name=name)


class GitHubClient:
    def __init__(self, *, token: str, base_url: str = "https://api.github.com") -> None:
        import requests

        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._comment_cache: dict[tuple[str, str, int], list[IssueComment]] = {}
        self.api_call_counts: dict[str, int] = {"http_get": 0, "http_post": 0, "issues_list": 0, "issue_get": 0, "issue_comments_list": 0, "issue_comment_create": 0}
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def get_issue(self, repo: GitHubRepoRef, number: int, *, include_comments: bool = True) -> Issue:
        self.api_call_counts["issue_get"] = int(self.api_call_counts.get("issue_get", 0)) + 1
        resp = self._get(
            f"{self.base_url}/repos/{repo.owner}/{repo.name}/issues/{number}",
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()
        if not isinstance(raw, dict):
            raise TypeError("GitHub issue response must be a JSON object")

        issue = self._parse_issue(raw)
        raw_comments: list[IssueComment] = []
        if include_comments:
            raw_comments = self.list_issue_comments(repo, issue.number)
        return Issue(
            number=issue.number,
            title=issue.title,
            body=issue.body,
            author=issue.author,
            labels=issue.labels,
            state=issue.state,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            closed_at=issue.closed_at,
            comments=tuple(raw_comments),
            raw=issue.raw,
        )

    def list_issues(
        self,
        repo: GitHubRepoRef,
        *,
        state: str = "open",
        limit: int = 200,
        include_pull_requests: bool = False,
        include_comments: bool = True,
    ) -> list[Issue]:
        self.api_call_counts["issues_list"] = int(self.api_call_counts.get("issues_list", 0)) + 1
        issues: list[Issue] = []

        for raw in self._paginate(
            f"{self.base_url}/repos/{repo.owner}/{repo.name}/issues",
            params={"state": state, "per_page": 100},
            limit=limit,
        ):
            if not include_pull_requests and isinstance(raw, dict) and "pull_request" in raw:
                continue
            issues.append(self._parse_issue(raw))

        if include_comments:
            for i, issue in enumerate(issues):
                raw_comments = self.list_issue_comments(repo, issue.number)
                issues[i] = Issue(
                    number=issue.number,
                    title=issue.title,
                    body=issue.body,
                    author=issue.author,
                    labels=issue.labels,
                    state=issue.state,
                    created_at=issue.created_at,
                    updated_at=issue.updated_at,
                    closed_at=issue.closed_at,
                    comments=tuple(raw_comments),
                    raw=issue.raw,
                )

        return issues

    def list_issue_comments(self, repo: GitHubRepoRef, number: int) -> list[IssueComment]:
        key = (repo.owner, repo.name, int(number))
        cached = self._comment_cache.get(key)
        if cached is not None:
            return list(cached)

        self.api_call_counts["issue_comments_list"] = int(self.api_call_counts.get("issue_comments_list", 0)) + 1
        comments: list[IssueComment] = []
        for raw in self._paginate(
            f"{self.base_url}/repos/{repo.owner}/{repo.name}/issues/{number}/comments",
            params={"per_page": 100},
            limit=10_000,
        ):
            if not isinstance(raw, dict):
                continue
            user = raw.get("user") or None
            author = None
            if isinstance(user, dict):
                author = IssueAuthor(login=str(user.get("login") or ""), id=_opt_int(user.get("id")))

            comments.append(
                IssueComment(
                    id=int(raw.get("id")),
                    author=author,
                    body=str(raw.get("body") or ""),
                    created_at=_opt_dt(raw.get("created_at")),
                    updated_at=_opt_dt(raw.get("updated_at")),
                )
            )

        self._comment_cache[key] = list(comments)
        return comments

    def create_issue_comment(self, repo: GitHubRepoRef, number: int, *, body: str) -> None:
        self.api_call_counts["issue_comment_create"] = int(self.api_call_counts.get("issue_comment_create", 0)) + 1
        payload = {"body": body}
        resp = self._post(
            f"{self.base_url}/repos/{repo.owner}/{repo.name}/issues/{number}/comments",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()

    def _get(self, url: str, **kwargs: Any):
        self.api_call_counts["http_get"] = int(self.api_call_counts.get("http_get", 0)) + 1
        return self.session.get(url, **kwargs)

    def _post(self, url: str, **kwargs: Any):
        self.api_call_counts["http_post"] = int(self.api_call_counts.get("http_post", 0)) + 1
        return self.session.post(url, **kwargs)

    def _paginate(self, url: str, *, params: dict[str, Any], limit: int) -> Iterable[Any]:
        page = 1
        remaining = limit

        while remaining > 0:
            p = dict(params)
            p["page"] = page
            resp = self._get(url, params=p, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list) or not data:
                return

            for item in data:
                yield item
                remaining -= 1
                if remaining <= 0:
                    return

            page += 1

    def _parse_issue(self, raw: dict[str, Any]) -> Issue:
        number = int(raw.get("number"))
        title = str(raw.get("title") or "").strip()
        body = str(raw.get("body") or "")
        user = raw.get("user") or None
        author = None if not isinstance(user, dict) else IssueAuthor(login=str(user.get("login") or ""), id=_opt_int(user.get("id")))

        labels_raw = raw.get("labels") or []
        labels: list[IssueLabel] = []
        if isinstance(labels_raw, list):
            for l in labels_raw:
                if isinstance(l, str):
                    labels.append(IssueLabel(name=l))
                elif isinstance(l, dict):
                    labels.append(IssueLabel(name=str(l.get("name") or "")))

        return Issue(
            number=number,
            title=title,
            body=body,
            author=author,
            labels=tuple(labels),
            state=str(raw.get("state")) if raw.get("state") is not None else None,
            created_at=_opt_dt(raw.get("created_at")),
            updated_at=_opt_dt(raw.get("updated_at")),
            closed_at=_opt_dt(raw.get("closed_at")),
            comments=(),
            raw=raw,
        )


def _opt_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _opt_dt(v: Any):
    from datetime import datetime

    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None
