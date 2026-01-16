from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher

from ..models import DuplicateLink, NormalizedIssue


@dataclass(frozen=True)
class DuplicateLimits:
    max_candidates_per_issue: int = 3
    max_pairs_evaluated_per_issue: int = 500
    title_similarity_threshold: float = 0.72
    stack_trace_similarity_threshold: float = 0.78


DEFAULT_LIMITS = DuplicateLimits()


def detect_duplicates_v2(
    issues: list[NormalizedIssue],
    *,
    limits: DuplicateLimits = DEFAULT_LIMITS,
) -> dict[int, DuplicateLink]:
    by_num = {n.issue.number: n for n in issues}
    nums = sorted(by_num.keys())

    results: dict[int, DuplicateLink] = {}

    for a_num in nums:
        a = by_num[a_num]
        candidates: list[tuple[int, float, tuple[str, ...]]] = []
        evaluated = 0

        for b_num in nums:
            if b_num == a_num:
                continue
            evaluated += 1
            if evaluated > limits.max_pairs_evaluated_per_issue:
                break

            b = by_num[b_num]
            score, reasons = _similarity_v2(a, b, limits)
            if score >= limits.title_similarity_threshold:
                candidates.append((b_num, score, reasons))

        candidates.sort(key=lambda t: (-t[1], t[0]))

        if candidates:
            top = candidates[: limits.max_candidates_per_issue]
            likely = tuple(n for n, _, _ in top)
            reason_set: list[str] = []
            for _, _, rs in top:
                for r in rs:
                    if r not in reason_set:
                        reason_set.append(r)

            results[a_num] = DuplicateLink(
                issue_number=a_num,
                likely_duplicates_of=likely,
                similarity_reasons=tuple(reason_set),
            )

    return results


def build_duplicate_groups_md(
    normalized_issues: list[NormalizedIssue],
    dup_map: dict[int, DuplicateLink],
    *,
    limits: DuplicateLimits = DEFAULT_LIMITS,
) -> str:
    title_by_num = {n.issue.number: n.issue.title for n in normalized_issues}

    # Graph per reason
    edges_by_reason: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for a_num, link in dup_map.items():
        for b_num in link.likely_duplicates_of:
            for r in link.similarity_reasons:
                edges_by_reason[r].append((a_num, b_num))

    lines: list[str] = []
    lines.append("# Duplicate Groups")
    lines.append("")
    lines.append("## Limits")
    lines.append("")
    lines.append(f"- max_candidates_per_issue: `{limits.max_candidates_per_issue}`")
    lines.append(f"- max_pairs_evaluated_per_issue: `{limits.max_pairs_evaluated_per_issue}`")
    lines.append(f"- title_similarity_threshold: `{limits.title_similarity_threshold}`")
    lines.append(f"- stack_trace_similarity_threshold: `{limits.stack_trace_similarity_threshold}`")
    lines.append("")

    if not edges_by_reason:
        lines.append("No duplicate groups detected.")
        lines.append("")
        return "\n".join(lines)

    for reason in sorted(edges_by_reason.keys()):
        groups = _connected_components(edges_by_reason[reason])
        if not groups:
            continue

        lines.append(f"## Reason: {reason}")
        lines.append("")

        for g in groups:
            nums = sorted(g)
            if len(nums) < 2:
                continue
            lines.append("### Group")
            lines.append("")
            for n in nums:
                t = title_by_num.get(n, "")
                lines.append(f"- #{n}: {t}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _connected_components(edges: list[tuple[int, int]]) -> list[set[int]]:
    adj: dict[int, set[int]] = defaultdict(set)
    nodes: set[int] = set()
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
        nodes.add(a)
        nodes.add(b)

    seen: set[int] = set()
    out: list[set[int]] = []

    for n in sorted(nodes):
        if n in seen:
            continue
        stack = [n]
        comp: set[int] = set()
        seen.add(n)
        while stack:
            x = stack.pop()
            comp.add(x)
            for y in adj.get(x, ()): 
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        out.append(comp)

    out.sort(key=lambda s: (-len(s), sorted(s)[0] if s else 0))
    return out


def _similarity_v2(a: NormalizedIssue, b: NormalizedIssue, limits: DuplicateLimits) -> tuple[float, tuple[str, ...]]:
    reasons: list[str] = []

    a_title = _norm_text(a.normalized_title or a.issue.title)
    b_title = _norm_text(b.normalized_title or b.issue.title)
    title_sim = _ratio(a_title, b_title)

    score = 0.0
    score += 0.50 * title_sim

    a_err_hashes = _error_signature_hashes(a)
    b_err_hashes = _error_signature_hashes(b)
    if a_err_hashes and b_err_hashes and set(a_err_hashes).intersection(b_err_hashes):
        score += 0.30
        reasons.append("error signature hash match")

    a_files = _mentioned_files(a.issue.title + "\n" + a.issue.body)
    b_files = _mentioned_files(b.issue.title + "\n" + b.issue.body)
    if a_files and b_files and set(a_files).intersection(b_files):
        score += 0.12
        reasons.append("referenced files overlap")

    a_stack = _stack_text(a)
    b_stack = _stack_text(b)
    if a_stack and b_stack:
        st_sim = _ratio(a_stack, b_stack)
        if st_sim >= limits.stack_trace_similarity_threshold:
            score += 0.20
            reasons.append("stack trace similarity")

    if title_sim >= 0.9:
        reasons.append("very similar titles")

    return min(1.0, score), tuple(reasons)


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(a=a, b=b).ratio()


def _norm_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9 _\-./]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()[:500]


def _stack_text(n: NormalizedIssue) -> str:
    txt = (n.sections.get("logs") or n.issue.body or "").strip()
    if not txt:
        return ""

    txt = re.sub(r"\b0x[0-9a-fA-F]+\b", "0xADDR", txt)
    txt = re.sub(r"\b\d+\b", "N", txt)
    txt = re.sub(r"[A-Za-z]:\\[^\s\n]+", "PATH", txt)
    txt = re.sub(r"/[^\s\n]+", "PATH", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:2000]


def _error_signature_hashes(n: NormalizedIssue) -> list[str]:
    text = (n.sections.get("logs") or "") + "\n" + (n.issue.body or "")
    sigs = _error_signatures(text)

    hashes: list[str] = []
    seen: set[str] = set()
    for s in sigs:
        norm = _normalize_error_signature(s)
        h = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]
        if h not in seen:
            seen.add(h)
            hashes.append(h)
    return hashes


def _normalize_error_signature(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\b0x[0-9a-f]+\b", "0xADDR", s)
    s = re.sub(r"\b\d+\b", "N", s)
    s = re.sub(r"[A-Za-z]:\\[^\s\n]+", "PATH", s)
    s = re.sub(r"/[^\s\n]+", "PATH", s)
    s = re.sub(r"\s+", " ", s)
    return s[:300]


def _error_signatures(text: str) -> list[str]:
    t = text or ""
    sigs: list[str] = []

    for m in re.finditer(r"^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception):\s*.+$", t, flags=re.M):
        s = m.group(0).strip()
        if 10 <= len(s) <= 240:
            sigs.append(s)

    for m in re.finditer(r"\b(error|exception)\b\s*[:=]\s*([^\n]{5,160})", t, flags=re.I):
        s = (m.group(1) + ": " + m.group(2)).strip()
        sigs.append(s)

    out: list[str] = []
    seen: set[str] = set()
    for s in sigs:
        s2 = re.sub(r"\s+", " ", s).strip()
        if s2 and s2 not in seen:
            seen.add(s2)
            out.append(s2)

    return out


def _mentioned_files(text: str) -> list[str]:
    t = text or ""

    files = re.findall(r"\b[a-zA-Z0-9_./-]+\.py\b", t)
    files += re.findall(r"\b[a-zA-Z0-9_./-]+\.toml\b", t)
    files += re.findall(r"\b[a-zA-Z0-9_./-]+\.yml\b", t)
    files += re.findall(r"\b[a-zA-Z0-9_./-]+\.yaml\b", t)

    out: list[str] = []
    seen: set[str] = set()
    for f in files:
        f2 = f.strip("` ")
        if f2 and f2 not in seen:
            seen.add(f2)
            out.append(f2)

    return out
