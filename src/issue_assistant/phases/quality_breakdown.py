from __future__ import annotations

import re

from ..models import NormalizedIssue, QualityBreakdown


def score_quality_breakdown(n: NormalizedIssue) -> QualityBreakdown:
    reasons: list[str] = []

    sections = n.sections
    body = n.issue.body or ""

    has_repro = _has_repro(sections, body)
    has_expected = _has_expected(sections, body)
    has_actual = _has_actual(sections, body)
    has_env = _has_environment(sections, body)
    has_logs = _has_logs(sections, body)

    completeness = 0
    completeness += 20 if has_repro else 0
    completeness += 20 if has_expected else 0
    completeness += 20 if has_actual else 0
    completeness += 20 if has_env else 0
    completeness += 20 if has_logs else 0

    clarity = 0
    if has_expected:
        clarity += 50
    if has_actual:
        clarity += 50
    if has_expected and len(sections.get("expected_behavior", "").strip()) < 10:
        reasons.append("expected behavior too short")
        clarity = max(0, clarity - 10)
    if has_actual and len(sections.get("actual_behavior", "").strip()) < 10:
        reasons.append("actual behavior too short")
        clarity = max(0, clarity - 10)

    reproducibility = 0
    reproducibility += 50 if has_repro else 0
    reproducibility += 25 if has_env else 0
    reproducibility += 25 if has_logs else 0

    noise = 0
    if n.is_low_signal:
        noise = min(100, noise + 60)
        reasons.extend(list(n.low_signal_reasons))

    if len(_signal_text(body)) < 80:
        noise = min(100, noise + 20)
        reasons.append("short description")

    if len(n.normalized_title) < 6:
        noise = min(100, noise + 20)
        reasons.append("very short title after normalization")

    reasons = _uniq(reasons)

    return QualityBreakdown(
        completeness=int(_clamp(completeness)),
        clarity=int(_clamp(clarity)),
        reproducibility=int(_clamp(reproducibility)),
        noise=int(_clamp(noise)),
        reasons=tuple(reasons),
    )


def _clamp(v: int) -> int:
    return 0 if v < 0 else (100 if v > 100 else v)


def _uniq(xs: list[str]) -> list[str]:
    out: list[str] = []
    for x in xs:
        x2 = x.strip()
        if x2 and x2 not in out:
            out.append(x2)
    return out


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


def _signal_text(s: str) -> str:
    s = re.sub(r"```[\s\S]*?```", " ", s)
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()
