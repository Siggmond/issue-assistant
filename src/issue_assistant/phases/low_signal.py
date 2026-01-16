from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import AnalysisRun, IssueAnalysis


@dataclass(frozen=True)
class LowSignalLimits:
    max_text_chars_considered: int = 20_000
    max_items: int = 200


DEFAULT_LIMITS = LowSignalLimits()


def detect_low_signal_issues(*, run: AnalysisRun, limits: LowSignalLimits = DEFAULT_LIMITS) -> dict[str, object]:
    items: list[dict[str, object]] = []

    for a in run.issues:
        score, reasons, signals = _score_issue(a, limits=limits)
        if score <= 0:
            continue
        items.append(
            {
                "issue_number": a.issue_number,
                "score": score,
                "classification": "spam" if signals.get("spam_keyword_hits", 0) >= 2 else "low_effort",
                "reasons": list(reasons),
                "signals": dict(signals),
            }
        )

    items.sort(key=lambda x: (-int(x.get("score", 0)), int(x.get("issue_number", 0))))
    items = items[: limits.max_items]

    return {
        "generated_at": run.generated_at.isoformat(),
        "repo": run.repo,
        "limits": {
            "max_text_chars_considered": int(limits.max_text_chars_considered),
            "max_items": int(limits.max_items),
            "not_detected": [
                "account-level abuse signals (new account, reputation)",
                "rate-based spam patterns across many issues",
                "image-only spam",
            ],
        },
        "items": items,
    }


def render_low_signal_md(*, report: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Low-Signal Issues")
    lines.append("")

    repo = report.get("repo")
    if repo:
        lines.append(f"Repository: `{repo}`")
        lines.append("")

    limits = report.get("limits") if isinstance(report.get("limits"), dict) else {}
    lines.append("## Limits")
    lines.append("")
    lines.append(f"- max_text_chars_considered: `{limits.get('max_text_chars_considered')}`")
    lines.append(f"- max_items: `{limits.get('max_items')}`")
    lines.append("")

    not_detected = limits.get("not_detected") if isinstance(limits.get("not_detected"), list) else []
    if not_detected:
        lines.append("Not detected:")
        for x in not_detected:
            lines.append(f"- {x}")
        lines.append("")

    items = report.get("items") if isinstance(report.get("items"), list) else []
    lines.append("## Findings")
    lines.append("")

    if not items:
        lines.append("No low-signal/spam indicators detected.")
        lines.append("")
        return "\n".join(lines)

    for item in items:
        num = item.get("issue_number")
        cls = item.get("classification")
        score = item.get("score")
        lines.append(f"## #{num}")
        lines.append("")
        lines.append(f"- classification: **{cls}**")
        lines.append(f"- score: `{score}`")
        reasons = item.get("reasons") if isinstance(item.get("reasons"), list) else []
        if reasons:
            lines.append("- reasons:")
            for r in reasons:
                lines.append(f"  - {r}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _score_issue(a: IssueAnalysis, *, limits: LowSignalLimits) -> tuple[int, tuple[str, ...], dict[str, int]]:
    i = a.normalized.issue

    title = (i.title or "")
    body = (i.body or "")
    comments = "\n".join((c.body or "") for c in i.comments)
    text = (title + "\n" + body + "\n" + comments)[: limits.max_text_chars_considered]
    t_low = text.lower()

    reasons: list[str] = []
    signals: dict[str, int] = {}
    score = 0

    # 1) Existing low-signal normalization signal
    if a.normalized.is_low_signal:
        score += 2
        reasons.append("normalized as low-signal")

    # 2) Quality noise signal
    if a.quality.noise >= 70:
        score += 2
        reasons.append("high noise score")
        signals["noise"] = a.quality.noise

    # 3) Very short content
    body_len = len((i.body or "").strip())
    signals["body_len"] = body_len
    if body_len < 40:
        score += 2
        reasons.append("very short body")
    elif body_len < 120:
        score += 1
        reasons.append("short body")

    # 4) Too many links for content size
    link_count = len(re.findall(r"https?://", text))
    signals["link_count"] = link_count
    if link_count >= 3 and body_len < 200:
        score += 2
        reasons.append("many links relative to text")

    # 5) Spam keyword hits (deterministic)
    spam_keywords = [
        "buy now",
        "free money",
        "crypto",
        "bitcoin",
        "airdrop",
        "casino",
        "porn",
        "viagra",
        "loan",
        "investment",
        "click here",
        "whatsapp",
        "telegram",
    ]
    hits = 0
    for kw in spam_keywords:
        if kw in t_low:
            hits += 1
    signals["spam_keyword_hits"] = hits
    if hits >= 2:
        score += 4
        reasons.append("multiple spam keyword hits")
    elif hits == 1:
        score += 2
        reasons.append("spam keyword hit")

    # 6) Repeated characters (e.g., "!!!!!!", "??????")
    if re.search(r"([!?\.])\1{5,}", text):
        score += 1
        reasons.append("excessive repeated punctuation")

    # 7) Non-actionable request patterns
    if re.search(r"\b(pls|please)\s+(fix|help)\b", t_low):
        score += 1
        reasons.append("non-actionable request phrasing")

    # 8) Down-weight if it actually contains strong debugging signals
    if "traceback" in t_low or "exception" in t_low or "stack trace" in t_low:
        score -= 2
        reasons.append("contains error details")

    if "steps to reproduce" in t_low or "reproduction" in t_low:
        score -= 1
        reasons.append("contains reproduction info")

    reasons = tuple(_uniq(reasons))

    if score < 0:
        score = 0

    return score, reasons, signals


def _uniq(xs: list[str]) -> list[str]:
    out: list[str] = []
    for x in xs:
        x2 = x.strip()
        if x2 and x2 not in out:
            out.append(x2)
    return out
