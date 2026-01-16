from __future__ import annotations

from dataclasses import dataclass

from ..models import IssueAnalysis


@dataclass(frozen=True)
class LabelSuggestion:
    name: str
    reasons: tuple[str, ...]


def recommend_labels(a: IssueAnalysis) -> tuple[LabelSuggestion, ...]:
    suggestions: list[LabelSuggestion] = []

    # Primary type from triage
    if a.triage.category == "bug":
        suggestions.append(LabelSuggestion(name="bug", reasons=("triage category is bug",)))
    elif a.triage.category == "feature request":
        suggestions.append(LabelSuggestion(name="enhancement", reasons=("triage category is feature request",)))
    elif a.triage.category == "documentation":
        suggestions.append(LabelSuggestion(name="documentation", reasons=("triage category is documentation",)))
    elif a.triage.category == "question":
        suggestions.append(LabelSuggestion(name="question", reasons=("triage category is question",)))
    elif a.triage.category == "support request":
        suggestions.append(LabelSuggestion(name="support", reasons=("triage category is support request",)))

    # needs-info
    needs_info_reasons: list[str] = []
    if a.lifecycle.state == "needs-info":
        needs_info_reasons.append("lifecycle state is needs-info")
    if a.quality.reproducibility < 50:
        needs_info_reasons.append("reproducibility below 50")
    if a.quality.completeness < 50:
        needs_info_reasons.append("completeness below 50")
    if needs_info_reasons:
        suggestions.append(LabelSuggestion(name="needs-info", reasons=tuple(needs_info_reasons)))

    # duplicate
    if a.duplicates is not None and a.duplicates.likely_duplicates_of:
        suggestions.append(LabelSuggestion(name="duplicate", reasons=("duplicate detection found likely duplicates",)))

    # triage label for workflow
    suggestions.append(LabelSuggestion(name="triage", reasons=("standard workflow label",)))

    # Deterministic de-dupe, stable sort
    by_name: dict[str, LabelSuggestion] = {}
    for s in suggestions:
        if s.name not in by_name:
            by_name[s.name] = s

    return tuple(by_name[n] for n in sorted(by_name.keys()))


def labels_to_json(suggestions: tuple[LabelSuggestion, ...]) -> dict[str, object]:
    return {
        "labels": [
            {
                "name": s.name,
                "reasons": list(s.reasons),
            }
            for s in suggestions
        ]
    }
