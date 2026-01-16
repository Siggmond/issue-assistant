from __future__ import annotations

from dataclasses import dataclass

from ..models import AnalysisRun, DependencyLink, IssueAnalysis
from .labels import recommend_labels


@dataclass(frozen=True)
class ExplainabilityLimits:
    max_indexed_issues: int = 500
    max_dependency_links_per_issue: int = 50


DEFAULT_LIMITS = ExplainabilityLimits()


def build_explainability(*, run: AnalysisRun, limits: ExplainabilityLimits = DEFAULT_LIMITS) -> dict[str, object]:
    issues = sorted(run.issues, key=lambda a: a.issue_number)[: limits.max_indexed_issues]
    return {
        "generated_at": run.generated_at.isoformat(),
        "repo": run.repo,
        "rules": rule_index(),
        "per_issue": [
            {
                "issue_number": a.issue_number,
                "path": f"issues/{a.issue_number}/explainability.json",
            }
            for a in issues
        ],
        "limits": {
            "max_indexed_issues": int(limits.max_indexed_issues),
            "max_dependency_links_per_issue": int(limits.max_dependency_links_per_issue),
        },
    }


def build_issue_explainability(
    *,
    run: AnalysisRun,
    analysis: IssueAnalysis,
    limits: ExplainabilityLimits = DEFAULT_LIMITS,
) -> dict[str, object]:
    a = analysis
    i = a.normalized.issue

    deps = _deps_for_issue(run=run, issue_number=i.number)
    if len(deps) > limits.max_dependency_links_per_issue:
        deps = deps[: limits.max_dependency_links_per_issue]

    return {
        "issue_number": i.number,
        "title": i.title,
        "sections": {
            "normalization": _explain_normalization(a),
            "quality": _explain_quality(a),
            "triage": _explain_triage(a),
            "lifecycle": _explain_lifecycle(a),
            "maintainer_cost": _explain_maintainer_cost(a),
            "maintainer_actions": _explain_actions(a),
            "duplicates": _explain_duplicates(a),
            "labels": _explain_labels(a),
            "dependencies": _explain_dependencies(deps),
            "playbook": _explain_playbook(a),
        },
        "limits": {
            "max_dependency_links_per_issue": int(limits.max_dependency_links_per_issue),
            "not_detected": [
                "semantic interpretation beyond deterministic rules",
                "automatic commenting/labeling/closing",
                "maintainer-specific policies",
            ],
        },
    }


def render_explainability_md(*, report: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Explainability")
    lines.append("")
    lines.append("This document is a global index of deterministic rules.")
    lines.append("Per-issue explainability JSON files are the ground truth for why a specific outcome happened.")
    lines.append("")

    lines.append("## Core invariant")
    lines.append("")
    lines.append("Explainability is a core invariant: every recommendation and classification must be traceable to deterministic rules with concrete evidence.")
    lines.append("")

    repo = report.get("repo")
    if repo:
        lines.append(f"Repository: `{repo}`")
        lines.append("")

    lines.append(f"Generated at: `{report.get('generated_at')}`")
    lines.append("")

    rules = report.get("rules") if isinstance(report.get("rules"), dict) else {}
    sections = rules.get("sections") if isinstance(rules.get("sections"), list) else []

    lines.append("## Rule index")
    lines.append("")

    for s in sections:
        if not isinstance(s, dict):
            continue
        lines.append(f"### {s.get('name')}")
        lines.append("")
        lines.append(f"Why this matters to a maintainer: {s.get('why_matters')}")
        lines.append("")
        lines.append(f"What this does NOT imply: {s.get('what_not_imply')}")
        lines.append("")

        rs = s.get("rules") if isinstance(s.get("rules"), list) else []
        if rs:
            lines.append("Rules:")
            for r in rs:
                if not isinstance(r, dict):
                    continue
                lines.append(f"- `{r.get('rule_id')}`: {r.get('description')}")
                lines.append(f"  - thresholds: {r.get('thresholds')}")
                lines.append(f"  - evidence_fields: {r.get('evidence_fields')}")
            lines.append("")

    lines.append("## Per-issue explainability")
    lines.append("")
    lines.append("- `.issue-assistant/issues/<issue_number>/explainability.json`")
    lines.append("")

    per_issue = report.get("per_issue") if isinstance(report.get("per_issue"), list) else []
    for x in per_issue:
        if not isinstance(x, dict):
            continue
        lines.append(f"- Issue #{x.get('issue_number')}: {x.get('path')}")

    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def rule_index() -> dict[str, object]:
    return {
        "sections": [
            {
                "name": "normalization",
                "why_matters": "Normalization affects section extraction which drives later scoring and needs-info outcomes.",
                "what_not_imply": "Low-signal normalization does not imply bad faith or spam.",
                "rules": [
                    {
                        "rule_id": "norm.low_signal.empty_body",
                        "description": "Mark low-signal when body is empty.",
                        "thresholds": {"body_nonempty": True},
                        "evidence_fields": ["issue.body"],
                    },
                    {
                        "rule_id": "norm.section_headers",
                        "description": "Extract sections by matching known headers (repro/expected/actual/env/logs).",
                        "thresholds": {},
                        "evidence_fields": ["issue.body"],
                    },
                ],
            },
            {
                "name": "quality",
                "why_matters": "Quality determines whether maintainers should request more info vs proceed.",
                "what_not_imply": "Low quality does not imply the issue is invalid.",
                "rules": [
                    {
                        "rule_id": "quality.completeness.points",
                        "description": "Completeness adds 20 points per present key section.",
                        "thresholds": {"per_section_points": 20},
                        "evidence_fields": ["normalized.sections"],
                    },
                    {
                        "rule_id": "quality.needs_info_threshold",
                        "description": "Needs-info related thresholds commonly check < 50.",
                        "thresholds": {"min_quality": 50},
                        "evidence_fields": ["quality.completeness", "quality.reproducibility"],
                    },
                ],
            },
            {
                "name": "triage",
                "why_matters": "Triage category influences labels and workflow routing.",
                "what_not_imply": "Triage is not guaranteed correct; maintainers can override.",
                "rules": [
                    {
                        "rule_id": "triage.label_override",
                        "description": "Certain labels force a triage category (bug/enhancement/question/docs).",
                        "thresholds": {},
                        "evidence_fields": ["issue.labels"],
                    },
                    {
                        "rule_id": "triage.text_heuristics",
                        "description": "Fallback category uses deterministic keyword heuristics.",
                        "thresholds": {},
                        "evidence_fields": ["issue.title", "issue.body"],
                    },
                ],
            },
            {
                "name": "lifecycle",
                "why_matters": "Lifecycle drives whether to request info, treat as stale, or treat as blocked.",
                "what_not_imply": "Lifecycle does not imply auto-closing.",
                "rules": [
                    {
                        "rule_id": "lifecycle.needs_info.quality",
                        "description": "Set needs-info when completeness or reproducibility < 50.",
                        "thresholds": {"min_quality": 50},
                        "evidence_fields": ["quality.completeness", "quality.reproducibility"],
                    },
                    {
                        "rule_id": "lifecycle.stale.age_days",
                        "description": "Set stale when no updates for >= stale_days and issue is open.",
                        "thresholds": {"stale_days": "LifecycleLimits.stale_days"},
                        "evidence_fields": ["issue.created_at", "issue.updated_at", "issue.state"],
                    },
                ],
            },
            {
                "name": "maintainer_cost",
                "why_matters": "Cost helps set effort expectations and prioritize maintainer time.",
                "what_not_imply": "Cost is effort, not importance.",
                "rules": [
                    {
                        "rule_id": "cost.body_length",
                        "description": "Add cost score when body length exceeds thresholds.",
                        "thresholds": {"moderate": 500, "long": 2000},
                        "evidence_fields": ["issue.body"],
                    },
                    {
                        "rule_id": "cost.missing_repro_logs",
                        "description": "Add cost score when reproduction steps or logs are missing.",
                        "thresholds": {},
                        "evidence_fields": ["normalized.sections"],
                    },
                ],
            },
            {
                "name": "labels",
                "why_matters": "Label recommendations help route issues (type/needs-info/duplicate/triage).",
                "what_not_imply": "Suggested labels may not match repository taxonomy.",
                "rules": [
                    {
                        "rule_id": "labels.type_from_triage",
                        "description": "Type label is derived from triage category.",
                        "thresholds": {},
                        "evidence_fields": ["triage.category"],
                    },
                    {
                        "rule_id": "labels.needs_info",
                        "description": "Recommend needs-info when lifecycle is needs-info or quality below 50.",
                        "thresholds": {"min_quality": 50},
                        "evidence_fields": ["lifecycle.state", "quality.reproducibility", "quality.completeness"],
                    },
                ],
            },
            {
                "name": "dependencies",
                "why_matters": "Dependency links expose related work/blocks that can affect triage and sequencing.",
                "what_not_imply": "Links do not imply a true dependency; they are extracted references.",
                "rules": [
                    {
                        "rule_id": "deps.regex.references",
                        "description": "Extract references like #123, owner/repo#123, GH-123, PR #123, commit SHAs.",
                        "thresholds": {},
                        "evidence_fields": ["issue.title", "issue.body", "issue.comments", "pr.body", "commit.message"],
                    }
                ],
            },
            {
                "name": "playbooks",
                "why_matters": "Playbook triggers provide consistent next steps based on deterministic signals.",
                "what_not_imply": "Playbooks do not imply automatic actions.",
                "rules": [
                    {
                        "rule_id": "playbook.trigger.low_quality",
                        "description": "Trigger when needs-info or quality < 50 or noise >= 70.",
                        "thresholds": {"min_quality": 50, "noise_high": 70},
                        "evidence_fields": ["lifecycle.state", "quality.completeness", "quality.reproducibility", "quality.noise"],
                    }
                ],
            },
        ]
    }


def _deps_for_issue(*, run: AnalysisRun, issue_number: int) -> list[DependencyLink]:
    out: list[DependencyLink] = []
    for d in run.dependencies:
        if d.source.kind == "issue" and d.source.identifier == str(issue_number):
            out.append(d)
    out.sort(key=lambda d: (d.reference_type, d.target.kind, d.target.repo or "", d.target.identifier))
    return out


def _explain_normalization(a: IssueAnalysis) -> dict[str, object]:
    fired: list[dict[str, object]] = []

    if a.normalized.is_low_signal:
        fired.append(
            {
                "rule_id": "norm.low_signal",
                "thresholds": {"is_low_signal": True},
                "evidence_fields": {
                    "normalized.is_low_signal": a.normalized.is_low_signal,
                    "normalized.low_signal_reasons": list(a.normalized.low_signal_reasons),
                },
            }
        )

    return {
        "rules_fired": fired,
        "why_this_matters": "Normalization controls which sections are recognized for quality and needs-info logic.",
        "what_this_does_not_imply": "Low-signal does not imply spam or invalidity.",
    }


def _explain_quality(a: IssueAnalysis) -> dict[str, object]:
    fired: list[dict[str, object]] = []

    fired.append(
        {
            "rule_id": "quality.scores",
            "thresholds": {"min": 0, "max": 100},
            "evidence_fields": {
                "quality.completeness": a.quality.completeness,
                "quality.clarity": a.quality.clarity,
                "quality.reproducibility": a.quality.reproducibility,
                "quality.noise": a.quality.noise,
                "quality.reasons": list(a.quality.reasons),
            },
        }
    )

    return {
        "rules_fired": fired,
        "why_this_matters": "Quality scores drive whether to ask for more info or proceed.",
        "what_this_does_not_imply": "Low scores do not imply the report is worthless or malicious.",
    }


def _explain_triage(a: IssueAnalysis) -> dict[str, object]:
    return {
        "rules_fired": [
            {
                "rule_id": "triage.classification",
                "thresholds": {},
                "evidence_fields": {
                    "triage.category": a.triage.category,
                    "triage.confidence": a.triage.confidence,
                    "triage.reasons": list(a.triage.reasons),
                },
            }
        ],
        "why_this_matters": "Triage category drives label suggestions and playbook selection.",
        "what_this_does_not_imply": "Triage output is not an instruction to close or to prioritize.",
    }


def _explain_lifecycle(a: IssueAnalysis) -> dict[str, object]:
    return {
        "rules_fired": [
            {
                "rule_id": "lifecycle.classification",
                "thresholds": {"min_quality": 50},
                "evidence_fields": {
                    "lifecycle.state": a.lifecycle.state,
                    "lifecycle.confidence": a.lifecycle.confidence,
                    "lifecycle.reasons": list(a.lifecycle.reasons),
                    "quality.completeness": a.quality.completeness,
                    "quality.reproducibility": a.quality.reproducibility,
                },
            }
        ],
        "why_this_matters": "Lifecycle suggests whether the next step is info gathering, waiting, or action.",
        "what_this_does_not_imply": "Lifecycle does not imply an automatic state transition on GitHub.",
    }


def _explain_maintainer_cost(a: IssueAnalysis) -> dict[str, object]:
    return {
        "rules_fired": [
            {
                "rule_id": "maintainer_cost.estimate",
                "thresholds": {"moderate_body_len": 500, "long_body_len": 2000},
                "evidence_fields": {
                    "maintainer_cost.level": a.maintainer_cost.level,
                    "maintainer_cost.reasons": list(a.maintainer_cost.reasons),
                    "maintainer_cost.signals": dict(a.maintainer_cost.signals),
                },
            }
        ],
        "why_this_matters": "Cost helps allocate maintainer time and set investigation expectations.",
        "what_this_does_not_imply": "Cost does not imply importance or priority.",
    }


def _explain_actions(a: IssueAnalysis) -> dict[str, object]:
    return {
        "rules_fired": [
            {
                "rule_id": "actions.recommend",
                "thresholds": {"min_quality": 50},
                "evidence_fields": {
                    "maintainer_action.recommended_actions": list(a.maintainer_action.recommended_actions),
                    "maintainer_action.recommended_labels": list(a.maintainer_action.recommended_labels),
                    "maintainer_action.notes": list(a.maintainer_action.notes),
                    "quality.completeness": a.quality.completeness,
                    "quality.reproducibility": a.quality.reproducibility,
                    "normalized.is_low_signal": a.normalized.is_low_signal,
                    "triage.category": a.triage.category,
                },
            }
        ],
        "why_this_matters": "Actions provide a consistent triage workflow that reduces maintainer overhead.",
        "what_this_does_not_imply": "Actions are not automated and do not imply a maintainer must follow them.",
    }


def _explain_duplicates(a: IssueAnalysis) -> dict[str, object]:
    fired: list[dict[str, object]] = []

    if a.duplicates is not None and a.duplicates.likely_duplicates_of:
        fired.append(
            {
                "rule_id": "duplicates.detected",
                "thresholds": {},
                "evidence_fields": {
                    "duplicates.likely_duplicates_of": list(a.duplicates.likely_duplicates_of),
                    "duplicates.similarity_reasons": list(a.duplicates.similarity_reasons),
                },
            }
        )

    return {
        "rules_fired": fired,
        "why_this_matters": "Duplicate candidates can reduce duplicated maintainer effort.",
        "what_this_does_not_imply": "Duplicates are suggestions and must be verified manually.",
    }


def _explain_labels(a: IssueAnalysis) -> dict[str, object]:
    suggestions = recommend_labels(a)

    fired: list[dict[str, object]] = []
    for s in suggestions:
        fired.append(
            {
                "rule_id": "labels.recommend",
                "thresholds": {"min_quality": 50},
                "evidence_fields": {
                    "label": s.name,
                    "reasons": list(s.reasons),
                    "triage.category": a.triage.category,
                    "lifecycle.state": a.lifecycle.state,
                    "quality.reproducibility": a.quality.reproducibility,
                    "quality.completeness": a.quality.completeness,
                    "duplicates.present": bool(a.duplicates is not None and a.duplicates.likely_duplicates_of),
                },
            }
        )

    return {
        "rules_fired": fired,
        "why_this_matters": "Labels help route issues through a consistent workflow.",
        "what_this_does_not_imply": "Suggested labels may not match your repository label taxonomy.",
    }


def _explain_dependencies(deps: list[DependencyLink]) -> dict[str, object]:
    fired: list[dict[str, object]] = []

    if deps:
        fired.append(
            {
                "rule_id": "deps.extracted",
                "thresholds": {},
                "evidence_fields": {
                    "dependency_links": [
                        {
                            "reference_type": d.reference_type,
                            "evidence": d.evidence,
                            "target": {
                                "kind": d.target.kind,
                                "repo": d.target.repo,
                                "identifier": d.target.identifier,
                            },
                        }
                        for d in deps
                    ]
                },
            }
        )

    return {
        "rules_fired": fired,
        "why_this_matters": "References can indicate dependencies or related work that affects sequencing.",
        "what_this_does_not_imply": "Extracted links do not guarantee a real dependency.",
    }


def _explain_playbook(a: IssueAnalysis) -> dict[str, object]:
    triggers: list[str] = []

    if a.lifecycle.state == "needs-info" or a.quality.completeness < 50 or a.quality.reproducibility < 50 or a.quality.noise >= 70:
        triggers.append("playbook.trigger.low_quality")

    if a.duplicates is not None and a.duplicates.likely_duplicates_of:
        triggers.append("playbook.trigger.duplicates")

    return {
        "rules_fired": [
            {
                "rule_id": "playbook.triggers",
                "thresholds": {"min_quality": 50, "noise_high": 70},
                "evidence_fields": {
                    "triggers": triggers,
                    "lifecycle.state": a.lifecycle.state,
                    "quality.completeness": a.quality.completeness,
                    "quality.reproducibility": a.quality.reproducibility,
                    "quality.noise": a.quality.noise,
                },
            }
        ],
        "why_this_matters": "Playbooks explain why a consistent set of next steps was produced.",
        "what_this_does_not_imply": "Playbooks do not imply automation or mandatory actions.",
    }
