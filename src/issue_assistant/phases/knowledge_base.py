from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from ..models import AnalysisRun


@dataclass(frozen=True)
class KnowledgeBaseLimits:
    max_text_chars_considered: int = 50_000
    max_error_signatures: int = 25
    max_files: int = 25
    max_faq_items: int = 25


DEFAULT_LIMITS = KnowledgeBaseLimits()


def build_knowledge_base(*, run: AnalysisRun, limits: KnowledgeBaseLimits = DEFAULT_LIMITS) -> dict[str, object]:
    error_counts: dict[str, dict[str, object]] = {}
    file_counts: dict[str, int] = {}
    faq_counts: dict[str, int] = {}

    for a in run.issues:
        i = a.normalized.issue
        title = i.title or ""
        body = i.body or ""
        comments = "\n".join((c.body or "") for c in i.comments)
        text = (title + "\n" + body + "\n" + comments)[: limits.max_text_chars_considered]

        for sig in _error_signatures_from_text(text):
            norm = _normalize_error_signature(sig)
            h = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]
            entry = error_counts.get(h)
            if entry is None:
                error_counts[h] = {
                    "signature_hash": h,
                    "signature": sig,
                    "count": 1,
                    "example_issue_numbers": [i.number],
                }
            else:
                entry["count"] = int(entry.get("count", 0)) + 1
                ex = entry.get("example_issue_numbers")
                if isinstance(ex, list) and len(ex) < 5 and i.number not in ex:
                    ex.append(i.number)

        for f in _mentioned_files(text):
            file_counts[f] = file_counts.get(f, 0) + 1

        for q in _question_patterns(title, body):
            faq_counts[q] = faq_counts.get(q, 0) + 1

    errors = list(error_counts.values())
    errors.sort(key=lambda d: (-int(d.get("count", 0)), str(d.get("signature_hash", ""))))
    if len(errors) > limits.max_error_signatures:
        errors = errors[: limits.max_error_signatures]

    files = [{"file": k, "count": v} for k, v in file_counts.items()]
    files.sort(key=lambda d: (-int(d.get("count", 0)), str(d.get("file", ""))))
    if len(files) > limits.max_files:
        files = files[: limits.max_files]

    faqs = [{"question": k, "count": v} for k, v in faq_counts.items()]
    faqs.sort(key=lambda d: (-int(d.get("count", 0)), str(d.get("question", ""))))
    if len(faqs) > limits.max_faq_items:
        faqs = faqs[: limits.max_faq_items]

    return {
        "generated_at": run.generated_at.isoformat(),
        "repo": run.repo,
        "limits": {
            "max_text_chars_considered": int(limits.max_text_chars_considered),
            "max_error_signatures": int(limits.max_error_signatures),
            "max_files": int(limits.max_files),
            "max_faq_items": int(limits.max_faq_items),
            "not_detected": [
                "semantic clustering of similar-but-not-identical error signatures",
                "solution inference (no LLM / no guessing fixes)",
                "codebase-aware ownership mapping",
            ],
        },
        "top_error_signatures": errors,
        "top_mentioned_files": files,
        "faq_patterns": faqs,
    }


def render_knowledge_base_md(*, kb: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Knowledge Base")
    lines.append("")

    repo = kb.get("repo")
    if repo:
        lines.append(f"Repository: `{repo}`")
        lines.append("")

    limits = kb.get("limits") if isinstance(kb.get("limits"), dict) else {}
    lines.append("## Limits")
    lines.append("")
    lines.append(f"- max_text_chars_considered: `{limits.get('max_text_chars_considered')}`")
    lines.append(f"- max_error_signatures: `{limits.get('max_error_signatures')}`")
    lines.append(f"- max_files: `{limits.get('max_files')}`")
    lines.append(f"- max_faq_items: `{limits.get('max_faq_items')}`")
    lines.append("")

    not_detected = limits.get("not_detected") if isinstance(limits.get("not_detected"), list) else []
    if not_detected:
        lines.append("Not detected:")
        for x in not_detected:
            lines.append(f"- {x}")
        lines.append("")

    errs = kb.get("top_error_signatures") if isinstance(kb.get("top_error_signatures"), list) else []
    lines.append("## Top error signatures")
    lines.append("")
    if not errs:
        lines.append("No error signatures extracted.")
        lines.append("")
    else:
        for e in errs:
            if not isinstance(e, dict):
                continue
            lines.append(f"- `{e.get('signature_hash')}` (count {e.get('count')}): {e.get('signature')}")
        lines.append("")

    files = kb.get("top_mentioned_files") if isinstance(kb.get("top_mentioned_files"), list) else []
    lines.append("## Top mentioned files")
    lines.append("")
    if not files:
        lines.append("No file paths extracted.")
        lines.append("")
    else:
        for f in files:
            if not isinstance(f, dict):
                continue
            lines.append(f"- `{f.get('file')}` (count {f.get('count')})")
        lines.append("")

    faqs = kb.get("faq_patterns") if isinstance(kb.get("faq_patterns"), list) else []
    lines.append("## FAQ-style patterns")
    lines.append("")
    if not faqs:
        lines.append("No recurring question patterns extracted.")
        lines.append("")
    else:
        for f in faqs:
            if not isinstance(f, dict):
                continue
            lines.append(f"- (count {f.get('count')}): {f.get('question')}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _error_signatures_from_text(text: str) -> list[str]:
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


def _normalize_error_signature(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\b0x[0-9a-f]+\b", "0xADDR", s)
    s = re.sub(r"\b\d+\b", "N", s)
    s = re.sub(r"[A-Za-z]:\\[^\s\n]+", "PATH", s)
    s = re.sub(r"/[^\s\n]+", "PATH", s)
    s = re.sub(r"\s+", " ", s)
    return s[:300]


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


def _question_patterns(title: str, body: str) -> list[str]:
    t = ((title or "") + "\n" + (body or "")).strip().lower()
    t = re.sub(r"\s+", " ", t)

    patterns: list[str] = []

    if re.search(r"\bhow\s+do\s+i\b", t):
        patterns.append("how do i …")
    if re.search(r"\bhow\s+to\b", t):
        patterns.append("how to …")
    if re.search(r"\bwhat\s+is\b", t):
        patterns.append("what is …")
    if re.search(r"\bwhy\s+(does|is)\b", t):
        patterns.append("why does/is …")
    if re.search(r"\bcan\s+someone\s+help\b", t):
        patterns.append("can someone help …")

    out: list[str] = []
    seen: set[str] = set()
    for p in patterns:
        if p not in seen:
            seen.add(p)
            out.append(p)

    return out
