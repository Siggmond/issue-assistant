from __future__ import annotations

import re

from ..models import NormalizedIssue, QualityScore


def score_issue_quality(n: NormalizedIssue) -> QualityScore:
    missing: list[str] = []
    reasons: list[str] = []

    sections = n.sections
    body = (n.issue.body or "")

    has_repro = _has_repro(sections, body)
    has_expected = _has_expected(sections, body)
    has_actual = _has_actual(sections, body)
    has_env = _has_environment(sections, body)
    has_logs = _has_logs(sections, body)

    if not has_repro:
        missing.append("reproduction steps")
    if not has_expected:
        missing.append("expected behavior")
    if not has_actual:
        missing.append("actual behavior")
    if not has_env:
        missing.append("environment details")

    score = 0
    score += 25 if has_repro else 0
    score += 20 if has_expected else 0
    score += 20 if has_actual else 0
    score += 15 if has_env else 0
    score += 20 if has_logs else 0

    if n.is_low_signal:
        reasons.append("low-signal issue")
        score = max(0, score - 15)

    level = _level(score)

    return QualityScore(level=level, score=score, missing=tuple(missing), reasons=tuple(reasons))


def _level(score: int) -> str:
    if score >= 75:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _has_repro(sections: dict[str, str], body: str) -> bool:
    if "reproduction_steps" in sections and len(sections["reproduction_steps"].strip()) >= 20:
        return True
    return bool(re.search(r"\b(steps to reproduce|repro steps|reproduction steps)\b", body, flags=re.I))


def _has_expected(sections: dict[str, str], body: str) -> bool:
    if "expected_behavior" in sections and len(sections["expected_behavior"].strip()) >= 10:
        return True
    return bool(re.search(r"\bexpected\b", body, flags=re.I))


def _has_actual(sections: dict[str, str], body: str) -> bool:
    if "actual_behavior" in sections and len(sections["actual_behavior"].strip()) >= 10:
        return True
    return bool(re.search(r"\b(actual|observed|instead)\b", body, flags=re.I))


def _has_environment(sections: dict[str, str], body: str) -> bool:
    if "environment" in sections and len(sections["environment"].strip()) >= 10:
        return True
    return bool(re.search(r"\b(python\s*\d|osx|macos|windows|linux|ubuntu|version\s*[:=])\b", body, flags=re.I))


def _has_logs(sections: dict[str, str], body: str) -> bool:
    if "logs" in sections and len(sections["logs"].strip()) >= 10:
        return True

    if "```" in body and ("traceback" in body.lower() or "error" in body.lower()):
        return True

    if "Traceback (most recent call last):" in body:
        return True

    return bool(re.search(r"\b(exception|stack trace|traceback|error:)\b", body, flags=re.I))
