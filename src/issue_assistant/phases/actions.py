from __future__ import annotations

from ..models import MaintainerAction, NormalizedIssue, QualityBreakdown, TriageClassification


def recommend_actions(*, normalized: NormalizedIssue, quality: QualityBreakdown, triage: TriageClassification) -> MaintainerAction:
    actions: list[str] = []
    labels: list[str] = []
    notes: list[str] = []

    if quality.reproducibility < 50 or quality.completeness < 50:
        actions.append("Request reproduction steps")
        actions.append("Request environment details")
        labels.append("needs-info")
        actions.append("Do not assign yet")

    if normalized.is_low_signal:
        if "needs-info" not in labels:
            labels.append("needs-info")
        actions.append("Ask the reporter to expand the description")

    if triage.category == "bug":
        labels.append("bug")
    elif triage.category == "feature request":
        labels.append("enhancement")
    elif triage.category == "documentation":
        labels.append("documentation")
    elif triage.category == "question":
        labels.append("question")
    elif triage.category == "support request":
        labels.append("support")

    if normalized.issue.author is None:
        notes.append("issue author not available")

    if not actions:
        actions.append("Review and triage")

    labels = _uniq(labels)
    actions = _uniq(actions)
    notes = _uniq(notes)

    return MaintainerAction(
        recommended_actions=tuple(actions),
        recommended_labels=tuple(labels),
        recommended_assignees=(),
        notes=tuple(notes),
    )


def _uniq(xs: list[str]) -> list[str]:
    out: list[str] = []
    for x in xs:
        x2 = x.strip()
        if x2 and x2 not in out:
            out.append(x2)
    return out
