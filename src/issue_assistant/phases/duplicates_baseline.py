from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..models import DuplicateLink, NormalizedIssue


def detect_duplicates(issues: list[NormalizedIssue]) -> dict[int, DuplicateLink]:
    by_num = {n.issue.number: n for n in issues}
    nums = sorted(by_num.keys())

    results: dict[int, DuplicateLink] = {}

    for i, a_num in enumerate(nums):
        a = by_num[a_num]
        candidates: list[tuple[int, float, tuple[str, ...]]] = []

        for b_num in nums:
            if b_num == a_num:
                continue

            b = by_num[b_num]
            score, reasons = _similarity(a, b)
            if score >= 0.72:
                candidates.append((b_num, score, reasons))

        candidates.sort(key=lambda t: (-t[1], t[0]))

        if candidates:
            top = candidates[:3]
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


def _similarity(a: NormalizedIssue, b: NormalizedIssue) -> tuple[float, tuple[str, ...]]:
    reasons: list[str] = []

    a_title = _norm_title(a.issue.title)
    b_title = _norm_title(b.issue.title)
    title_sim = _ratio(a_title, b_title)

    score = 0.0
    score += 0.55 * title_sim

    a_err = _error_signatures(a.issue.body)
    b_err = _error_signatures(b.issue.body)
    shared_err = sorted(set(a_err).intersection(b_err))
    if shared_err:
        score += 0.30
        reasons.append("identical error string")

    a_files = _mentioned_files(a.issue.title + "\n" + a.issue.body)
    b_files = _mentioned_files(b.issue.title + "\n" + b.issue.body)
    shared_files = sorted(set(a_files).intersection(b_files))
    if shared_files:
        score += 0.15
        reasons.append("same file/component mentioned")

    if title_sim >= 0.9:
        reasons.append("very similar titles")

    return min(1.0, score), tuple(reasons)


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(a=a, b=b).ratio()


def _norm_title(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9 _\-./]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


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
