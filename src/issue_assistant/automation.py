from __future__ import annotations

from dataclasses import dataclass

from .models import Issue, IssueAnalysis
from .phases.labels import recommend_labels


@dataclass(frozen=True)
class AutoCommentDecision:
    should_comment: bool
    body: str | None
    rule_ids: tuple[str, ...]


_AUTOCOMMENT_MARKER = "<!-- issue-assistant:auto-comment -->"


def decide_auto_comment(*, governance_mode: str, analysis: IssueAnalysis, artifacts_root: str | None = None) -> AutoCommentDecision:
    mode = (governance_mode or "").strip().lower()
    if mode == "dry-run":
        return AutoCommentDecision(should_comment=False, body=None, rule_ids=())

    triggers = _comment_triggers(analysis)
    if not (triggers.needs_info or triggers.low_signal or triggers.duplicates):
        return AutoCommentDecision(should_comment=False, body=None, rule_ids=())

    if _already_commented(analysis.normalized.issue):
        return AutoCommentDecision(should_comment=False, body=None, rule_ids=())

    if mode not in ("strict", "aggressive"):
        return AutoCommentDecision(should_comment=False, body=None, rule_ids=())

    lines: list[str] = []
    lines.append(_AUTOCOMMENT_MARKER)

    lines.append("Issue Assistant (deterministic):")
    lines.append("")

    rule_ids: list[str] = []

    if triggers.needs_info:
        lines.append("- Missing information detected. Please add: reproduction steps, environment details, expected vs actual behavior, and logs/stack trace if available.")
        rule_ids.extend(["lifecycle.needs_info.quality", "labels.needs_info"])

    if triggers.low_signal:
        lines.append("- Low-signal indicators detected. Adding concrete details will help maintainers triage faster.")
        rule_ids.extend(["norm.low_signal.empty_body", "quality.needs_info_threshold"])

    if triggers.duplicates and analysis.duplicates is not None and analysis.duplicates.likely_duplicates_of:
        dup_list = ", ".join(f"#{n}" for n in analysis.duplicates.likely_duplicates_of[:5])
        lines.append(f"- Possible duplicate of: {dup_list}. If this is the same issue, please add any distinguishing details.")
        rule_ids.append("duplicates.detected")

    if mode == "aggressive":
        suggestions = recommend_labels(analysis)
        if suggestions:
            names = ", ".join(f"`{s.name}`" for s in suggestions)
            lines.append("")
            lines.append(f"Suggested labels (not applied automatically): {names}")
            rule_ids.append("labels.type_from_triage")

    if artifacts_root:
        issue_number = analysis.issue_number
        lines.append("")
        lines.append("Artifacts:")
        lines.append(f"- {artifacts_root}/issues/{issue_number}/playbook.md")
        lines.append(f"- {artifacts_root}/issues/{issue_number}/explainability.json")

    if rule_ids:
        uniq: list[str] = []
        for r in rule_ids:
            if r not in uniq:
                uniq.append(r)
        lines.append("")
        lines.append("Explainability rules referenced:")
        lines.append("- " + ", ".join(f"`{r}`" for r in uniq))
        rule_ids = uniq

    body = "\n".join(lines).rstrip() + "\n"
    if body.strip() == _AUTOCOMMENT_MARKER:
        return AutoCommentDecision(should_comment=False, body=None, rule_ids=())

    return AutoCommentDecision(should_comment=True, body=body, rule_ids=tuple(rule_ids))


@dataclass(frozen=True)
class _Triggers:
    needs_info: bool
    low_signal: bool
    duplicates: bool


def _comment_triggers(a: IssueAnalysis) -> _Triggers:
    needs_info = a.lifecycle.state == "needs-info"
    low_signal = bool(a.normalized.is_low_signal) or a.quality.noise >= 70
    duplicates = bool(a.duplicates is not None and a.duplicates.likely_duplicates_of)

    return _Triggers(needs_info=needs_info, low_signal=low_signal, duplicates=duplicates)


def _already_commented(issue: Issue) -> bool:
    for c in issue.comments:
        if _AUTOCOMMENT_MARKER in (c.body or ""):
            return True
    return False
