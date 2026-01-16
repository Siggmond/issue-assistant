from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import Commit, DependencyEndpoint, DependencyLink, Issue, PullRequest


@dataclass(frozen=True)
class DependencyLimits:
    max_text_chars_considered: int = 20_000
    max_links_emitted: int = 5_000


DEFAULT_LIMITS = DependencyLimits()


def extract_issue_dependencies(
    *,
    repo: str | None,
    issues: list[Issue],
    pull_requests: list[PullRequest] | None = None,
    commits: list[Commit] | None = None,
    limits: DependencyLimits = DEFAULT_LIMITS,
) -> tuple[DependencyLink, ...]:
    prs = pull_requests or []
    cs = commits or []

    links: list[DependencyLink] = []

    for issue in issues:
        src = DependencyEndpoint(kind="issue", repo=repo, identifier=str(issue.number))
        text = _issue_text(issue, limits=limits)
        links.extend(_links_from_text(source=src, text=text, default_target_repo=repo, source_kind_hint="issue"))

    for pr in prs:
        src = DependencyEndpoint(kind="pull_request", repo=repo, identifier=str(pr.number))
        text = _pr_text(pr, limits=limits)
        links.extend(_links_from_text(source=src, text=text, default_target_repo=repo, source_kind_hint="pull_request"))

    for c in cs:
        src = DependencyEndpoint(kind="commit", repo=repo, identifier=c.sha)
        text = (c.message or "")[: limits.max_text_chars_considered]
        links.extend(_links_from_commit_message(source=src, text=text, default_target_repo=repo))

    links = _dedupe_links(links)

    if len(links) > limits.max_links_emitted:
        links = links[: limits.max_links_emitted]

    return tuple(links)


def dependencies_to_json(*, links: tuple[DependencyLink, ...], limits: DependencyLimits) -> dict[str, object]:
    return {
        "limits": {
            "max_text_chars_considered": limits.max_text_chars_considered,
            "max_links_emitted": limits.max_links_emitted,
            "not_detected": [
                "implicit semantic relationships (e.g., 'this relates to that')",
                "references in images/screenshots",
                "links that rely on GitHub UI context (e.g. timeline events)",
                "commit messages unless provided explicitly or git scanning is enabled",
            ],
        },
        "links": [
            {
                "source": {
                    "kind": d.source.kind,
                    "repo": d.source.repo,
                    "identifier": d.source.identifier,
                },
                "target": {
                    "kind": d.target.kind,
                    "repo": d.target.repo,
                    "identifier": d.target.identifier,
                },
                "reference_type": d.reference_type,
                "evidence": d.evidence,
                "reasons": list(d.reasons),
            }
            for d in links
        ],
    }


def render_issue_dependencies_md(*, repo: str | None, links: tuple[DependencyLink, ...], limits: DependencyLimits) -> str:
    lines: list[str] = []
    lines.append("# Issue Dependencies")
    lines.append("")
    if repo:
        lines.append(f"Repository: `{repo}`")
        lines.append("")

    lines.append("## Limits")
    lines.append("")
    lines.append(f"- max_text_chars_considered: `{limits.max_text_chars_considered}`")
    lines.append(f"- max_links_emitted: `{limits.max_links_emitted}`")
    lines.append("")
    lines.append("Not detected:")
    lines.append("- implicit semantic relationships")
    lines.append("- references in images/screenshots")
    lines.append("- GitHub UI timeline events")
    lines.append("- commit messages unless provided or git scanning is enabled")
    lines.append("")

    lines.append("## Links")
    lines.append("")
    if not links:
        lines.append("No explicit issue/PR/commit references detected.")
        lines.append("")
        return "\n".join(lines)

    for d in links:
        lines.append(f"- {d.source.kind}:{_fmt_endpoint(d.source)} -> {d.target.kind}:{_fmt_endpoint(d.target)}")
        lines.append(f"  - reference_type: `{d.reference_type}`")
        if d.reasons:
            lines.append("  - reasons:")
            for r in d.reasons:
                lines.append(f"    - {r}")
        lines.append(f"  - evidence: `{_short(d.evidence)}`")

    lines.append("")
    return "\n".join(lines)


def _fmt_endpoint(e: DependencyEndpoint) -> str:
    if e.repo:
        return f"{e.repo}#{e.identifier}" if e.kind in ("issue", "pull_request") else f"{e.repo}@{e.identifier}"
    return e.identifier


def _short(s: str, n: int = 140) -> str:
    t = (s or "").strip().replace("\n", " ")
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _issue_text(issue: Issue, *, limits: DependencyLimits) -> str:
    parts: list[str] = [issue.title or "", "", issue.body or ""]
    for c in issue.comments:
        parts.append("\n")
        parts.append(c.body or "")
    return "\n".join(parts)[: limits.max_text_chars_considered]


def _pr_text(pr: PullRequest, *, limits: DependencyLimits) -> str:
    parts: list[str] = [pr.title or "", "", pr.body or ""]
    for c in pr.comments:
        parts.append("\n")
        parts.append(c.body or "")
    return "\n".join(parts)[: limits.max_text_chars_considered]


_RE_CROSS_REPO = re.compile(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#(\d+)\b")
_RE_GH = re.compile(r"\bGH-(\d+)\b", flags=re.I)
_RE_HASH_NUM = re.compile(r"(?<!#)(?<![A-Za-z0-9_./-])#(\d+)\b")
_RE_PR_WORD = re.compile(r"\b(?:pr|pull request)\s*#(\d+)\b", flags=re.I)


def _links_from_text(*, source: DependencyEndpoint, text: str, default_target_repo: str | None, source_kind_hint: str) -> list[DependencyLink]:
    links: list[DependencyLink] = []

    for repo2, num in _RE_CROSS_REPO.findall(text or ""):
        tgt = DependencyEndpoint(kind="issue", repo=repo2, identifier=str(int(num)))
        links.append(
            DependencyLink(
                source=source,
                target=tgt,
                reference_type="explicit_cross_repo",
                evidence=f"{repo2}#{int(num)}",
                reasons=("matched owner/repo#number",),
            )
        )

    for num in _RE_GH.findall(text or ""):
        tgt = DependencyEndpoint(kind="issue", repo=default_target_repo, identifier=str(int(num)))
        links.append(
            DependencyLink(
                source=source,
                target=tgt,
                reference_type="explicit_gh",
                evidence=f"GH-{int(num)}",
                reasons=("matched GH-<number>",),
            )
        )

    # PR-specific references from issues: "PR #123" / "pull request #123"
    for num in _RE_PR_WORD.findall(text or ""):
        tgt = DependencyEndpoint(kind="pull_request", repo=default_target_repo, identifier=str(int(num)))
        links.append(
            DependencyLink(
                source=source,
                target=tgt,
                reference_type="explicit_pr_ref",
                evidence=f"PR #{int(num)}",
                reasons=("matched PR #<number>",),
            )
        )

    # Plain #123 depends on source hint
    for m in _RE_HASH_NUM.finditer(text or ""):
        if _is_heading_like(text, m.start()):
            continue

        num = int(m.group(1))
        # Deterministic rule:
        # - If local window contains PR wording, treat as a pull request
        # - Otherwise treat as an issue
        # This avoids guessing based on repo state while still supporting explicit "PR #123" style.
        target_kind = "pull_request" if _has_pr_context(text, m.start()) else "issue"

        tgt = DependencyEndpoint(kind=target_kind, repo=default_target_repo, identifier=str(num))
        links.append(
            DependencyLink(
                source=source,
                target=tgt,
                reference_type="explicit_number",
                evidence=m.group(0),
                reasons=(
                    "matched #<number>",
                    "interpreted as pull_request due to PR context" if target_kind == "pull_request" else "interpreted as issue by default",
                ),
            )
        )

    return links


def _links_from_commit_message(*, source: DependencyEndpoint, text: str, default_target_repo: str | None) -> list[DependencyLink]:
    links: list[DependencyLink] = []

    # Common GitHub merge commit format
    mm = re.search(r"(?i)merge pull request\s+#(\d+)\b", text or "")
    if mm:
        n = int(mm.group(1))
        links.append(
            DependencyLink(
                source=source,
                target=DependencyEndpoint(kind="pull_request", repo=default_target_repo, identifier=str(n)),
                reference_type="commit_message_merge_pr",
                evidence=mm.group(0),
                reasons=("matched 'merge pull request #<number>'",),
            )
        )

    for repo2, num in _RE_CROSS_REPO.findall(text or ""):
        links.append(
            DependencyLink(
                source=source,
                target=DependencyEndpoint(kind="issue", repo=repo2, identifier=str(int(num))),
                reference_type="commit_message_cross_repo",
                evidence=f"{repo2}#{int(num)}",
                reasons=("matched owner/repo#number in commit message",),
            )
        )

    # Prefer explicit PR wording if present
    prw = re.search(r"(?i)\bpr\s*#(\d+)\b", text or "")
    if prw:
        n = int(prw.group(1))
        links.append(
            DependencyLink(
                source=source,
                target=DependencyEndpoint(kind="pull_request", repo=default_target_repo, identifier=str(n)),
                reference_type="commit_message_pr",
                evidence=prw.group(0),
                reasons=("matched 'PR #<number>' in commit message",),
            )
        )

    # Generic #123 in commit message treated as issue
    for m in _RE_HASH_NUM.finditer(text or ""):
        if _is_heading_like(text, m.start()):
            continue
        n = int(m.group(1))
        links.append(
            DependencyLink(
                source=source,
                target=DependencyEndpoint(kind="issue", repo=default_target_repo, identifier=str(n)),
                reference_type="commit_message_issue",
                evidence=m.group(0),
                reasons=("matched #<number> in commit message",),
            )
        )

    return links


def _dedupe_links(links: list[DependencyLink]) -> list[DependencyLink]:
    seen: set[tuple[str, str, str, str, str, str]] = set()
    out: list[DependencyLink] = []
    for d in links:
        key = (
            d.source.kind,
            str(d.source.repo),
            d.source.identifier,
            d.target.kind,
            str(d.target.repo),
            d.target.identifier,
        )
        key2 = key + (d.reference_type,)
        if key2 in seen:
            continue
        seen.add(key2)
        out.append(d)
    out.sort(key=lambda x: (x.source.kind, x.source.identifier, x.target.kind, x.target.identifier, x.reference_type))
    return out


def _has_pr_context(text: str, idx: int) -> bool:
    # Look back a bit for "PR" wording (deterministic local window)
    start = max(0, idx - 20)
    window = (text or "")[start:idx].lower()
    return "pr" in window or "pull request" in window


def _is_heading_like(text: str, match_start: int) -> bool:
    # Avoid matching markdown headings like a line that is just "#123" or "#123 ..." at line start
    t = text or ""
    line_start = t.rfind("\n", 0, match_start) + 1
    line_end = t.find("\n", match_start)
    if line_end == -1:
        line_end = len(t)
    line = t[line_start:line_end].strip()
    return bool(re.fullmatch(r"#\d+(?:\s+.*)?", line))
