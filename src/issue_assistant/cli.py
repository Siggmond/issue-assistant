from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
import subprocess
from typing import Any

from .artifacts import ArtifactWriter
from .automation import decide_auto_comment
from .github import GitHubClient, GitHubRepoRef
from .models import Commit, Issue, IssueAuthor, IssueComment, IssueLabel, PullRequest
from .phase_registry import enabled_phases_require_comments, normalize_enabled_phases
from .pipeline import analyze_issues


def main() -> None:
    parser = argparse.ArgumentParser(prog="issue-assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--repo", default=None, help="Repository name (e.g. owner/name)")
    analyze.add_argument("--repo-path", default=".", help="Path to the repo root (default: .)")
    analyze.add_argument(
        "--issues-file",
        default=None,
        help="Path to a JSON file containing a GitHub Issues API-like payload.",
    )
    analyze.add_argument("--github-token", default=None, help="GitHub token (uses GitHub API when provided)")
    analyze.add_argument("--state", default="open", choices=["open", "closed", "all"], help="Issue state")
    analyze.add_argument("--limit", type=int, default=200, help="Max issues to fetch/analyze")
    analyze.add_argument(
        "--include-pull-requests",
        action="store_true",
        help="Include pull requests from /issues endpoint",
    )
    analyze.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: <repo-path>/.issue-assistant)",
    )
    analyze.add_argument(
        "--pull-requests-file",
        default=None,
        help="Optional: path to a JSON file containing pull requests (GitHub API-like payload).",
    )
    analyze.add_argument(
        "--commits-file",
        default=None,
        help="Optional: path to a JSON file containing commits (simple JSON array).",
    )
    analyze.add_argument(
        "--scan-git-commits",
        action="store_true",
        help="Optional: read commit messages from local git (requires git).",
    )
    analyze.add_argument(
        "--git-commit-limit",
        type=int,
        default=200,
        help="Max commits to scan when --scan-git-commits is enabled.",
    )

    analyze.add_argument(
        "--governance-mode",
        default="dry-run",
        choices=["dry-run", "strict", "aggressive"],
        help="Trust mode: dry-run (default), strict, aggressive.",
    )

    analyze.add_argument(
        "--issue-number",
        type=int,
        default=None,
        help="Optional: analyze a single issue number (recommended for issue-triggered GitHub Actions).",
    )
    analyze.add_argument(
        "--auto-comment",
        action="store_true",
        help="Optional: governance-aware auto-commenting (dry-run never comments). Requires --github-token, --repo, and --issue-number.",
    )
    analyze.add_argument(
        "--artifacts-url-prefix",
        default=None,
        help="Optional: URL prefix used to link to committed artifacts (e.g. https://github.com/<owner>/<repo>/blob/<ref>/.issue-assistant).",
    )

    analyze.add_argument(
        "--comments-mode",
        default="all",
        choices=["none", "needed", "all"],
        help="GitHub comment fetching mode: none, needed, or all (default: all).",
    )

    analyze.add_argument(
        "--phases",
        default=None,
        help="Optional comma-separated phase list to emit (e.g. dependencies,weekly_digest). Default: all.",
    )

    analyze.add_argument(
        "--verbose",
        action="store_true",
        help="Print lightweight run metrics (elapsed time, GitHub API call counts) to stderr.",
    )

    args = parser.parse_args()

    if args.command == "analyze":
        t0 = time.perf_counter()
        repo_path = Path(args.repo_path).resolve()
        output_dir = Path(args.output_dir).resolve() if args.output_dir else (repo_path / ".issue-assistant")

        enabled_phases = normalize_enabled_phases(str(args.phases) if args.phases is not None else None)
        phases_need_comments = enabled_phases_require_comments(enabled_phases)

        if bool(args.auto_comment) and str(args.comments_mode) == "none":
            raise SystemExit("--auto-comment requires issue comments; use --comments-mode needed|all")

        if bool(args.verbose) and str(args.comments_mode) == "none" and phases_need_comments:
            sys.stderr.write(
                "[issue-assistant] warning: comment-dependent phase enabled but --comments-mode=none; results may be less accurate\n"
            )

        issues: list[Issue] = []
        gh: GitHubClient | None = None
        repo_ref: GitHubRepoRef | None = None
        if args.github_token:
            if not args.repo:
                raise SystemExit("--repo is required when using --github-token")
            repo_ref = GitHubRepoRef.parse(args.repo)
            gh = GitHubClient(token=args.github_token)

            cmode = str(args.comments_mode)
            include_comments = cmode == "all" or (cmode == "needed" and (bool(args.auto_comment) or phases_need_comments))

            if args.issue_number is not None:
                issues = [gh.get_issue(repo_ref, int(args.issue_number), include_comments=include_comments)]
            else:
                issues = gh.list_issues(
                    repo_ref,
                    state=args.state,
                    limit=args.limit,
                    include_pull_requests=bool(args.include_pull_requests),
                    include_comments=include_comments,
                )
        elif args.issues_file:
            issues = _load_issues_from_file(Path(args.issues_file))
        else:
            raise SystemExit("Provide either --github-token (and --repo) or --issues-file")

        prs: list[PullRequest] | None = None
        if args.pull_requests_file:
            prs = _load_pull_requests_from_file(Path(args.pull_requests_file))

        commits: list[Commit] | None = None
        if args.commits_file:
            commits = _load_commits_from_file(Path(args.commits_file))
        elif args.scan_git_commits:
            commits = _scan_git_commits(repo_path=repo_path, limit=int(args.git_commit_limit))

        run = analyze_issues(
            issues=issues,
            repo=args.repo,
            pull_requests=prs,
            commits=commits,
            governance_mode=str(args.governance_mode),
        )
        ArtifactWriter(output_dir=output_dir, enabled_phases=enabled_phases).write(run)

        if bool(args.auto_comment):
            if not args.github_token or not args.repo or args.issue_number is None:
                raise SystemExit("--auto-comment requires --github-token, --repo, and --issue-number")

            mode = str(args.governance_mode)
            if mode != "dry-run":
                if gh is None or repo_ref is None:
                    repo_ref = GitHubRepoRef.parse(args.repo)
                    gh = GitHubClient(token=args.github_token)

                issue = gh.get_issue(repo_ref, int(args.issue_number), include_comments=True)

                analysis = next((a for a in run.issues if a.issue_number == int(args.issue_number)), None)
                if analysis is None:
                    raise SystemExit("--issue-number was requested but analysis was not produced")

                decision = decide_auto_comment(
                    governance_mode=mode,
                    analysis=analysis,
                    artifacts_root=str(args.artifacts_url_prefix) if args.artifacts_url_prefix else None,
                )
                if decision.should_comment and decision.body:
                    gh.create_issue_comment(repo_ref, issue.number, body=decision.body)

        if bool(args.verbose):
            elapsed = time.perf_counter() - t0
            if gh is not None:
                sys.stderr.write(f"[issue-assistant] elapsed_seconds={elapsed:.3f} github_api_calls={gh.api_call_counts}\n")
            else:
                sys.stderr.write(f"[issue-assistant] elapsed_seconds={elapsed:.3f}\n")


def _load_issues_from_file(path: Path) -> list[Issue]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(payload, dict) and "items" in payload and isinstance(payload["items"], list):
        raw_issues = payload["items"]
    elif isinstance(payload, list):
        raw_issues = payload
    else:
        raise ValueError("issues-file must be a list of issues or an object with an 'items' list")

    issues: list[Issue] = []
    for raw in raw_issues:
        issues.append(_parse_issue(raw))
    return issues


def _parse_issue(raw: dict[str, Any]) -> Issue:
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

    comments_raw = raw.get("comments") or []
    comments: list[IssueComment] = []
    if isinstance(comments_raw, list):
        for c in comments_raw:
            if not isinstance(c, dict):
                continue
            c_user = c.get("user") or None
            c_author = (
                None
                if not isinstance(c_user, dict)
                else IssueAuthor(login=str(c_user.get("login") or ""), id=_opt_int(c_user.get("id")))
            )
            comments.append(
                IssueComment(
                    id=int(c.get("id")),
                    author=c_author,
                    body=str(c.get("body") or ""),
                    created_at=_opt_dt(c.get("created_at")),
                    updated_at=_opt_dt(c.get("updated_at")),
                )
            )

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
        comments=tuple(comments),
        raw=raw,
    )


def _load_pull_requests_from_file(path: Path) -> list[PullRequest]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "items" in payload and isinstance(payload["items"], list):
        raw_prs = payload["items"]
    elif isinstance(payload, list):
        raw_prs = payload
    else:
        raise ValueError("pull-requests-file must be a list or an object with an 'items' list")

    prs: list[PullRequest] = []
    for raw in raw_prs:
        if isinstance(raw, dict):
            prs.append(_parse_pull_request(raw))
    return prs


def _parse_pull_request(raw: dict[str, Any]) -> PullRequest:
    number = int(raw.get("number"))
    title = str(raw.get("title") or "").strip()
    body = str(raw.get("body") or "")
    user = raw.get("user") or None
    author = None if not isinstance(user, dict) else IssueAuthor(login=str(user.get("login") or ""), id=_opt_int(user.get("id")))

    comments_raw = raw.get("comments") or []
    comments: list[IssueComment] = []
    if isinstance(comments_raw, list):
        for c in comments_raw:
            if not isinstance(c, dict):
                continue
            c_user = c.get("user") or None
            c_author = (
                None
                if not isinstance(c_user, dict)
                else IssueAuthor(login=str(c_user.get("login") or ""), id=_opt_int(c_user.get("id")))
            )
            comments.append(
                IssueComment(
                    id=int(c.get("id")),
                    author=c_author,
                    body=str(c.get("body") or ""),
                    created_at=_opt_dt(c.get("created_at")),
                    updated_at=_opt_dt(c.get("updated_at")),
                )
            )

    return PullRequest(
        number=number,
        title=title,
        body=body,
        author=author,
        state=str(raw.get("state")) if raw.get("state") is not None else None,
        created_at=_opt_dt(raw.get("created_at")),
        updated_at=_opt_dt(raw.get("updated_at")),
        closed_at=_opt_dt(raw.get("closed_at")),
        merged_at=_opt_dt(raw.get("merged_at")),
        comments=tuple(comments),
        raw=raw,
    )


def _load_commits_from_file(path: Path) -> list[Commit]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("commits-file must be a JSON list")
    commits: list[Commit] = []
    for raw in payload:
        if isinstance(raw, dict):
            commits.append(_parse_commit(raw))
    return commits


def _parse_commit(raw: dict[str, Any]) -> Commit:
    sha = str(raw.get("sha") or raw.get("id") or "").strip()
    message = str(raw.get("message") or "")
    author = None
    if isinstance(raw.get("author"), str):
        author = str(raw.get("author"))
    authored_at = _opt_dt(raw.get("authored_at") or raw.get("date"))
    return Commit(sha=sha, message=message, author=author, authored_at=authored_at, raw=raw)


def _scan_git_commits(*, repo_path: Path, limit: int) -> list[Commit]:
    # Deterministic local scan; if git is not available or repo is not a git repo, returns [].
    try:
        cmd = ["git", "log", f"-n{int(limit)}", "--pretty=format:%H%n%B%n==END=="]
        proc = subprocess.run(cmd, cwd=str(repo_path), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []

    if proc.returncode != 0:
        return []

    commits: list[Commit] = []
    buf: list[str] = []
    sha: str | None = None
    for line in (proc.stdout or "").splitlines():
        if sha is None:
            s = line.strip()
            if s:
                sha = s
            continue
        if line.strip() == "==END==":
            msg = "\n".join(buf).strip("\n")
            commits.append(Commit(sha=sha, message=msg))
            sha = None
            buf = []
            continue
        buf.append(line)

    return commits


def _opt_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _opt_dt(v: Any):
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
