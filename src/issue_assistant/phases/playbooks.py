from __future__ import annotations

from dataclasses import dataclass

from ..models import AnalysisRun, DependencyLink, IssueAnalysis
from .labels import recommend_labels


@dataclass(frozen=True)
class PlaybookLimits:
    max_indexed_issues: int = 500
    max_dependencies_shown: int = 20


DEFAULT_LIMITS = PlaybookLimits()


def render_maintainer_playbooks_md(*, run: AnalysisRun, limits: PlaybookLimits = DEFAULT_LIMITS) -> str:
    lines: list[str] = []
    lines.append("# Maintainer Playbooks")
    lines.append("")

    if run.repo:
        lines.append(f"Repository: `{run.repo}`")
        lines.append("")

    lines.append(f"Generated at: `{run.generated_at.isoformat()}`")
    lines.append("")

    lines.append("## Principles")
    lines.append("")
    lines.append("These playbooks are deterministic decision-support. They are not automated actions.")
    lines.append("")

    lines.append("## Global playbooks")
    lines.append("")
    lines.extend(_render_global_playbooks(run))

    lines.append("## Per-issue playbooks")
    lines.append("")
    lines.append("Per-issue playbooks are generated under:")
    lines.append("")
    lines.append("- `.issue-assistant/issues/<issue_number>/playbook.md`")
    lines.append("")

    indexed = sorted(run.issues, key=lambda a: a.issue_number)[: limits.max_indexed_issues]
    for a in indexed:
        lines.append(f"- Issue #{a.issue_number}: issues/{a.issue_number}/playbook.md")

    if len(run.issues) > limits.max_indexed_issues:
        lines.append("")
        lines.append(f"Limits: index truncated to first {limits.max_indexed_issues} issues.")

    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_issue_playbook_md(
    *,
    run: AnalysisRun,
    analysis: IssueAnalysis,
    limits: PlaybookLimits = DEFAULT_LIMITS,
) -> str:
    a = analysis
    i = a.normalized.issue

    triggers = _issue_triggers(run=run, a=a, limits=limits)

    lines: list[str] = []
    lines.append(f"# Issue #{i.number} Playbook")
    lines.append("")
    lines.append(f"Title: {i.title}")
    lines.append("")

    lines.append("## When to use")
    lines.append("")
    lines.append("Use this playbook when the issue has been analyzed by this tool and you want deterministic next steps.")
    lines.append("")

    lines.append("## Why this playbook was selected")
    lines.append("")
    if triggers:
        lines.append("Trigger conditions met:")
        for t in triggers:
            lines.append(f"- {t}")
    else:
        lines.append("No special trigger conditions were met; this is a default playbook derived from the analysis.")
    lines.append("")

    lines.append("## What should the maintainer do next?")
    lines.append("")
    for step in _recommended_next_steps(run=run, a=a, limits=limits):
        lines.append(f"- {step}")
    lines.append("")

    lines.append("## What should not be done yet?")
    lines.append("")
    for step in _not_yet_steps(a):
        lines.append(f"- {step}")
    lines.append("")

    lines.append("## What information is missing (if any)?")
    lines.append("")
    missing = _missing_info(a)
    if not missing:
        lines.append("No missing information detected by deterministic rules.")
    else:
        for m in missing:
            lines.append(f"- {m}")
    lines.append("")

    lines.append("## Suggested labels")
    lines.append("")
    suggestions = recommend_labels(a)
    if not suggestions:
        lines.append("No label suggestions.")
    else:
        for s in suggestions:
            lines.append(f"- `{s.name}`")
    lines.append("")

    lines.append("## Dependencies (Phase 8)")
    lines.append("")
    deps = _deps_for_issue(run=run, issue_number=i.number)
    if not deps:
        lines.append("No dependency links detected.")
        lines.append("")
    else:
        shown = deps[: limits.max_dependencies_shown]
        for d in shown:
            tgt = f"{d.target.kind}:{d.target.repo or ''}{'#' if d.target.kind != 'commit' else ''}{d.target.identifier}".strip()
            lines.append(f"- {d.reference_type} -> {tgt} (evidence: {d.evidence})")
        if len(deps) > limits.max_dependencies_shown:
            lines.append("")
            lines.append(f"Limits: dependencies truncated to first {limits.max_dependencies_shown} links.")
        lines.append("")

    lines.append("## What this does not cover")
    lines.append("")
    lines.append("- Semantic understanding of the issue beyond deterministic rules")
    lines.append("- Automatically closing, labeling, or commenting on issues")
    lines.append("- Assigning maintainers based on CODEOWNERS or repository metadata")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_global_playbooks(run: AnalysisRun) -> list[str]:
    lines: list[str] = []

    low_quality = [a for a in run.issues if _is_low_quality(a)]
    duplicates = [a for a in run.issues if a.duplicates is not None and a.duplicates.likely_duplicates_of]
    stale = [a for a in run.issues if a.lifecycle.state == "stale"]
    bugs = [a for a in run.issues if a.triage.category == "bug"]
    features = [a for a in run.issues if a.triage.category == "feature request"]
    support = [a for a in run.issues if a.triage.category in ("support request", "question")]

    lines.extend(
        _global_section(
            title="Handling low-quality issues",
            when=[
                "lifecycle.state == needs-info",
                "quality.completeness < 50 OR quality.reproducibility < 50",
                "quality.noise >= 70 OR normalized.is_low_signal == True",
            ],
            why=f"Selected because {len(low_quality)} issue(s) meet low-quality conditions.",
            actions=[
                "Request missing reproduction steps / environment / logs (as applicable)",
                "Ask for expected vs actual behavior to be stated clearly",
                "Defer deeper investigation until required info is provided",
            ],
            labels=["needs-info", "triage"],
            not_covered=[
                "Detecting malicious intent",
                "Automatically closing issues",
            ],
        )
    )

    lines.extend(
        _global_section(
            title="Handling duplicates",
            when=[
                "duplicates.likely_duplicates_of is non-empty",
            ],
            why=f"Selected because {len(duplicates)} issue(s) have likely duplicates.",
            actions=[
                "Confirm the duplicate relationship by checking the referenced issue(s)",
                "Link the issues together and consolidate discussion",
                "If confirmed, close the duplicate with a reference (manual maintainer decision)",
            ],
            labels=["duplicate", "triage"],
            not_covered=[
                "Cross-repo duplicate detection",
                "Semantic equivalence beyond extracted signatures/files/titles",
            ],
        )
    )

    lines.extend(
        _global_section(
            title="Handling stale issues",
            when=[
                "lifecycle.state == stale",
            ],
            why=f"Selected because {len(stale)} issue(s) are classified as stale.",
            actions=[
                "Ask for confirmation the issue still reproduces on the latest version",
                "Request updated reproduction steps / logs if the environment changed",
                "Consider closing if no response (manual maintainer decision)",
            ],
            labels=["needs-info", "triage"],
            not_covered=[
                "Repository-specific stale policies",
                "Automatic timers or auto-closing",
            ],
        )
    )

    lines.extend(
        _global_section(
            title="Handling feature requests vs bugs",
            when=[
                "triage.category in {bug, feature request}",
            ],
            why=f"Selected because repo contains {len(bugs)} bug(s) and {len(features)} feature request(s).",
            actions=[
                "For bugs: request minimal reproduction + expected/actual + logs",
                "For feature requests: request motivation, scope, and acceptance criteria",
                "Decide whether the request fits project goals (manual maintainer decision)",
            ],
            labels=["bug", "enhancement", "triage"],
            not_covered=[
                "Roadmap prioritization",
                "Estimating impact or user value",
            ],
        )
    )

    lines.extend(
        _global_section(
            title="Handling support requests",
            when=[
                "triage.category in {support request, question}",
            ],
            why=f"Selected because {len(support)} issue(s) are support/question.",
            actions=[
                "Ask for expected outcome, current behavior, and configuration",
                "Point to relevant documentation if available (manual maintainer decision)",
                "If it is usage guidance rather than a bug, suggest moving to appropriate support channels (manual)",
            ],
            labels=["support", "question", "triage"],
            not_covered=[
                "Answer generation",
                "Documentation completeness assessment",
            ],
        )
    )

    lines.append("## Limits")
    lines.append("")
    lines.append("- Triggers are based only on deterministic fields produced by earlier phases.")
    lines.append("- Recommended actions do not imply automation; maintainers must decide what to do.")
    lines.append("- Label names are suggestions based on Phase 7 rules and may not match repo label taxonomy.")
    lines.append("")

    return lines


def _global_section(
    *,
    title: str,
    when: list[str],
    why: str,
    actions: list[str],
    labels: list[str],
    not_covered: list[str],
) -> list[str]:
    lines: list[str] = []
    lines.append(f"### {title}")
    lines.append("")

    lines.append("When to use:")
    for w in when:
        lines.append(f"- {w}")
    lines.append("")

    lines.append("Why it was selected:")
    lines.append(f"- {why}")
    lines.append("")

    lines.append("Recommended maintainer actions:")
    for a in actions:
        lines.append(f"- {a}")
    lines.append("")

    lines.append("Suggested labels (Phase 7 reference):")
    for l in labels:
        lines.append(f"- `{l}`")
    lines.append("")

    lines.append("What it does not cover:")
    for n in not_covered:
        lines.append(f"- {n}")
    lines.append("")

    return lines


def _is_low_quality(a: IssueAnalysis) -> bool:
    if a.lifecycle.state == "needs-info":
        return True
    if a.quality.completeness < 50:
        return True
    if a.quality.reproducibility < 50:
        return True
    if a.quality.noise >= 70:
        return True
    if a.normalized.is_low_signal:
        return True
    return False


def _missing_info(a: IssueAnalysis) -> list[str]:
    missing: list[str] = []

    if a.quality.reproducibility < 50:
        if "reproduction_steps" not in a.normalized.sections:
            missing.append("reproduction steps")
        if "environment" not in a.normalized.sections:
            missing.append("environment details")

    if a.quality.completeness < 50:
        if "expected_behavior" not in a.normalized.sections:
            missing.append("expected behavior")
        if "actual_behavior" not in a.normalized.sections:
            missing.append("actual behavior")

    if a.quality.reproducibility < 50 or a.quality.completeness < 50:
        if "logs" not in a.normalized.sections:
            missing.append("logs / stack trace")

    out: list[str] = []
    for m in missing:
        if m not in out:
            out.append(m)
    return out


def _not_yet_steps(a: IssueAnalysis) -> list[str]:
    steps: list[str] = []

    if _is_low_quality(a):
        steps.append("Do not attempt deep debugging until missing information is provided.")

    if a.duplicates is not None and a.duplicates.likely_duplicates_of:
        steps.append("Do not implement a new fix until the duplicate relationship is confirmed.")

    if a.lifecycle.state == "blocked":
        steps.append("Do not close as resolved until the blocking dependency is addressed.")

    if not steps:
        steps.append("No explicit " + "not-yet" + " steps detected.")

    return steps


def _recommended_next_steps(*, run: AnalysisRun, a: IssueAnalysis, limits: PlaybookLimits) -> list[str]:
    steps: list[str] = []

    if _is_low_quality(a):
        missing = _missing_info(a)
        if missing:
            steps.append("Request missing information: " + ", ".join(missing) + ".")
        steps.append("Add a needs-info style response and wait for reporter feedback (manual action).")

    if a.duplicates is not None and a.duplicates.likely_duplicates_of:
        targets = ", ".join(f"#{n}" for n in a.duplicates.likely_duplicates_of)
        steps.append(f"Review likely duplicates: {targets}.")
        steps.append("If confirmed, consolidate discussion into a single issue (manual action).")

    deps = _deps_for_issue(run=run, issue_number=a.issue_number)
    if deps:
        steps.append("Review detected dependency links for context before making changes.")

    if a.triage.category == "feature request":
        steps.append("Ask for scope and acceptance criteria; evaluate fit with project direction (manual decision).")

    if a.triage.category in ("support request", "question"):
        steps.append("Clarify intended usage and configuration; point to docs or support channel (manual action).")

    if not steps:
        steps.append("Triage and reproduce if possible; proceed with normal maintainer workflow.")

    out: list[str] = []
    for s in steps:
        if s not in out:
            out.append(s)
    return out


def _deps_for_issue(*, run: AnalysisRun, issue_number: int) -> list[DependencyLink]:
    out: list[DependencyLink] = []
    for d in run.dependencies:
        if d.source.kind != "issue":
            continue
        if d.source.identifier == str(issue_number):
            out.append(d)
    out.sort(key=lambda x: (x.reference_type, x.target.kind, x.target.repo or "", x.target.identifier))
    return out


def _issue_triggers(*, run: AnalysisRun, a: IssueAnalysis, limits: PlaybookLimits) -> list[str]:
    triggers: list[str] = []

    if _is_low_quality(a):
        triggers.append("Low-quality signals detected (needs-info / low completeness / low reproducibility / high noise)")

    if a.duplicates is not None and a.duplicates.likely_duplicates_of:
        triggers.append("Duplicate detection found likely duplicates")

    if _deps_for_issue(run=run, issue_number=a.issue_number):
        triggers.append("Dependency links detected (Phase 8)")

    if a.triage.category in ("support request", "question"):
        triggers.append("Triage category is support/question")

    if a.triage.category == "feature request":
        triggers.append("Triage category is feature request")

    if a.lifecycle.state == "stale":
        triggers.append("Lifecycle state is stale")

    if a.lifecycle.state == "blocked":
        triggers.append("Lifecycle state is blocked")

    return triggers
