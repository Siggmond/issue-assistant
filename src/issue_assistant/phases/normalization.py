from __future__ import annotations

import re

from ..models import Issue, NormalizedIssue


_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "reproduction_steps": ("steps to reproduce", "repro steps", "reproduction", "how to reproduce", "steps"),
    "expected_behavior": ("expected behavior", "expected", "expected result"),
    "actual_behavior": ("actual behavior", "actual", "observed behavior", "what happened"),
    "environment": ("environment", "system info", "version", "versions", "platform"),
    "logs": ("logs", "log", "stack trace", "traceback", "error", "errors"),
}


_TITLE_NOISE_WORDS = {
    "help",
    "urgent",
    "asap",
    "please",
    "plz",
    "question",
    "bug",
    "issue",
}


def normalize_issue(issue: Issue) -> NormalizedIssue:
    body = (issue.body or "").strip()
    title = (issue.title or "").strip()
    normalized_title = normalize_title(title)

    sections = _extract_sections(body)
    sections = _augment_sections_from_inline_blocks(body, sections)
    sections = _augment_sections_from_code_fences(body, sections)

    low_signal_reasons: list[str] = []

    if not normalized_title:
        low_signal_reasons.append("missing title")

    if len(_signal_text(body)) < 40 and len(_signal_text(title)) < 20:
        low_signal_reasons.append("very little description")

    if not body:
        low_signal_reasons.append("empty body")

    is_low_signal = len(low_signal_reasons) > 0

    return NormalizedIssue(
        issue=issue,
        normalized_title=normalized_title,
        sections=sections,
        is_low_signal=is_low_signal,
        low_signal_reasons=tuple(low_signal_reasons),
    )


def normalize_title(title: str) -> str:
    t = (title or "").strip().lower()
    t = re.sub(r"\s+", " ", t)

    t = re.sub(r"\[[^\]]+\]", " ", t)
    t = re.sub(r"\([^\)]*\)", " ", t)

    t = re.sub(r"[^a-z0-9 _\-./]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    parts = [p for p in re.split(r"\s+", t) if p]
    parts = [p for p in parts if p not in _TITLE_NOISE_WORDS]
    out = " ".join(parts).strip()

    out = re.sub(r"^(re:|fw:|fwd:)\s+", "", out).strip()
    out = re.sub(r"\s+", " ", out)
    return out


def _extract_sections(body: str) -> dict[str, str]:
    lines = body.splitlines()
    captured: dict[str, list[str]] = {k: [] for k in _SECTION_ALIASES.keys()}

    current_key: str | None = None

    def commit_key(k: str | None) -> None:
        if k is None:
            return

    for raw_line in lines:
        line = raw_line.strip()
        key = _match_section_header(line)
        if key is not None:
            commit_key(current_key)
            current_key = key
            continue

        if current_key is not None:
            captured[current_key].append(raw_line)

    sections: dict[str, str] = {}
    for k, buf in captured.items():
        text = "\n".join(buf).strip()
        if text:
            sections[k] = text

    return sections


def _augment_sections_from_inline_blocks(body: str, sections: dict[str, str]) -> dict[str, str]:
    if not body:
        return sections

    merged = dict(sections)

    patterns: dict[str, tuple[str, ...]] = {
        "reproduction_steps": ("steps to reproduce", "reproduction steps", "repro steps"),
        "expected_behavior": ("expected behavior", "expected"),
        "actual_behavior": ("actual behavior", "actual"),
        "environment": ("environment", "env", "system info"),
        "logs": ("logs", "log", "stack trace", "traceback"),
    }

    for key, labels in patterns.items():
        if key in merged:
            continue

        for label in labels:
            m = re.search(
                rf"(?im)^\s*(?:#+\s*)?{re.escape(label)}\s*[:\-]\s*(.+?)(?=\n\s*(?:#+\s*)?[A-Za-z][A-Za-z0-9 _/-]*\s*[:\-]|\Z)",
                body,
                flags=re.S,
            )
            if m:
                text = (m.group(1) or "").strip()
                if text:
                    merged[key] = text
                break

    return merged


def _augment_sections_from_code_fences(body: str, sections: dict[str, str]) -> dict[str, str]:
    if not body:
        return sections

    if "logs" in sections:
        return sections

    blocks = re.findall(r"```[\s\S]*?```", body)
    if not blocks:
        return sections

    candidates: list[str] = []
    for b in blocks:
        inner = re.sub(r"^```[^\n]*\n", "", b.strip())
        inner = re.sub(r"\n```$", "", inner)
        txt = inner.strip()
        if not txt:
            continue
        if "traceback" in txt.lower() or "exception" in txt.lower() or "error" in txt.lower():
            candidates.append(txt)

    if not candidates:
        return sections

    merged = dict(sections)
    merged["logs"] = "\n\n".join(candidates).strip()
    return merged


def _match_section_header(line: str) -> str | None:
    if not line:
        return None

    m = re.match(r"^(#{1,6}\s+)?(.+?)\s*:?\s*$", line)
    if not m:
        return None

    header = (m.group(2) or "").strip().lower()
    header = re.sub(r"\s+", " ", header)

    for key, aliases in _SECTION_ALIASES.items():
        for a in aliases:
            if header == a:
                return key

    return None


def _signal_text(s: str) -> str:
    s = re.sub(r"```[\s\S]*?```", " ", s)
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()
