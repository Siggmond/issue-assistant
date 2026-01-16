from __future__ import annotations

import re

from ..models import NormalizedIssue, TriageClassification


def classify_issue(n: NormalizedIssue) -> TriageClassification:
    title = (n.issue.title or "").lower()
    body = (n.issue.body or "").lower()
    labels = {l.name.lower() for l in n.issue.labels}

    reasons: list[str] = []

    if any(l in labels for l in ("bug", "type: bug", "kind/bug")):
        reasons.append("labeled as bug")
        return TriageClassification(category="bug", confidence=0.95, reasons=tuple(reasons))

    if any(l in labels for l in ("enhancement", "feature", "type: feature", "kind/feature")):
        reasons.append("labeled as enhancement/feature")
        return TriageClassification(category="feature request", confidence=0.95, reasons=tuple(reasons))

    if any(l in labels for l in ("question", "type: question")):
        reasons.append("labeled as question")
        return TriageClassification(category="question", confidence=0.95, reasons=tuple(reasons))

    if any(l in labels for l in ("documentation", "docs", "type: docs")):
        reasons.append("labeled as documentation")
        return TriageClassification(category="documentation", confidence=0.95, reasons=tuple(reasons))

    if _looks_like_support(title, body):
        reasons.append("requests help/support")
        return TriageClassification(category="support request", confidence=0.75, reasons=tuple(reasons))

    if _looks_like_question(title, body):
        reasons.append("question phrasing")
        return TriageClassification(category="question", confidence=0.7, reasons=tuple(reasons))

    if _looks_like_feature(title, body):
        reasons.append("feature phrasing")
        return TriageClassification(category="feature request", confidence=0.7, reasons=tuple(reasons))

    if _looks_like_docs(title, body):
        reasons.append("documentation phrasing")
        return TriageClassification(category="documentation", confidence=0.65, reasons=tuple(reasons))

    if _looks_like_bug(title, body):
        reasons.append("error/bug phrasing")
        return TriageClassification(category="bug", confidence=0.7, reasons=tuple(reasons))

    return TriageClassification(category="question", confidence=0.4, reasons=tuple(reasons))


def _looks_like_question(title: str, body: str) -> bool:
    if title.strip().endswith("?"):
        return True
    return bool(re.search(r"\b(how do i|how to|is it possible|can i|should i|what is)\b", title + "\n" + body))


def _looks_like_feature(title: str, body: str) -> bool:
    return bool(re.search(r"\b(feature request|request|would be nice|enhancement|add support|please add)\b", title + "\n" + body))


def _looks_like_docs(title: str, body: str) -> bool:
    return bool(re.search(r"\b(docs|documentation|readme|typo|broken link)\b", title + "\n" + body))


def _looks_like_bug(title: str, body: str) -> bool:
    return bool(re.search(r"\b(bug|crash|exception|traceback|error|regression|broken)\b", title + "\n" + body))


def _looks_like_support(title: str, body: str) -> bool:
    return bool(re.search(r"\b(help|support|assist|guidance|stuck)\b", title + "\n" + body))
