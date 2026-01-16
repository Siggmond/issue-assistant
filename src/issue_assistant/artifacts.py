from __future__ import annotations

import json
from pathlib import Path

from .models import AnalysisRun, maintainer_cost_to_json, normalized_issue_to_json, quality_breakdown_to_json
from .phases.contributor_guide import render_contributor_guide
from .phases.dependencies import DEFAULT_LIMITS as DEP_LIMITS
from .phases.dependencies import dependencies_to_json, render_issue_dependencies_md
from .phases.duplicates import DEFAULT_LIMITS, build_duplicate_groups_md
from .phases.explainability import DEFAULT_LIMITS as EXPL_LIMITS
from .phases.explainability import build_explainability, build_issue_explainability, render_explainability_md
from .phases.issue_health import DEFAULT_LIMITS as HEALTH_LIMITS
from .phases.issue_health import compute_issue_health, render_issue_health_md
from .phases.knowledge_base import DEFAULT_LIMITS as KB_LIMITS
from .phases.knowledge_base import build_knowledge_base, render_knowledge_base_md
from .phases.labels import labels_to_json, recommend_labels
from .phases.low_signal import DEFAULT_LIMITS as LOW_SIGNAL_LIMITS
from .phases.low_signal import detect_low_signal_issues, render_low_signal_md
from .phases.maintainer_load import DEFAULT_LIMITS as LOAD_LIMITS
from .phases.maintainer_load import compute_maintainer_load, render_maintainer_load_md
from .phases.playbooks import DEFAULT_LIMITS as PLAYBOOK_LIMITS
from .phases.playbooks import render_issue_playbook_md, render_maintainer_playbooks_md
from .phases.weekly_digest import DEFAULT_LIMITS as DIGEST_LIMITS
from .phases.weekly_digest import build_weekly_digest, render_weekly_digest_md


class ArtifactWriter:
    def __init__(self, output_dir: Path, *, enabled_phases: set[str] | None = None) -> None:
        self.output_dir = output_dir
        self.enabled_phases = enabled_phases

    def _enabled(self, phase: str) -> bool:
        return self.enabled_phases is None or phase in self.enabled_phases

    def write(self, run: AnalysisRun) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        issues_json_path = self.output_dir / "issues.json"
        issues_json_path.write_text(json.dumps(run.as_json_dict(), indent=2, sort_keys=True), encoding="utf-8")

        quality_breakdown_path = self.output_dir / "quality_breakdown.json"
        quality_breakdown_path.write_text(
            json.dumps(_with_governance(_quality_breakdown_json(run), run), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        (self.output_dir / "ISSUE_SUMMARY.md").write_text(_with_governance_md(_render_issue_summary(run), run), encoding="utf-8")
        (self.output_dir / "DUPLICATES.md").write_text(_with_governance_md(_render_duplicates(run), run), encoding="utf-8")
        (self.output_dir / "DUPLICATE_GROUPS.md").write_text(_with_governance_md(_render_duplicate_groups(run), run), encoding="utf-8")
        (self.output_dir / "TRIAGE.md").write_text(_with_governance_md(_render_triage(run), run), encoding="utf-8")
        (self.output_dir / "CLUSTERS.md").write_text(_with_governance_md(_render_clusters_placeholder(run), run), encoding="utf-8")
        (self.output_dir / "MAINTAINER_ACTIONS.md").write_text(_with_governance_md(_render_actions(run), run), encoding="utf-8")
        (self.output_dir / "MAINTAINER_COST.md").write_text(_with_governance_md(_render_maintainer_cost(run), run), encoding="utf-8")
        (self.output_dir / "CONTRIBUTOR_GUIDE.md").write_text(_with_governance_md(_render_contributor_guide_index(run), run), encoding="utf-8")

        (self.output_dir / "labels.json").write_text(
            json.dumps(_with_governance(_labels_json(run), run), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        if self._enabled("dependencies"):
            (self.output_dir / "issue_dependencies.json").write_text(
                json.dumps(
                    _with_governance(dependencies_to_json(links=run.dependencies, limits=DEP_LIMITS), run),
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            (self.output_dir / "ISSUE_DEPENDENCIES.md").write_text(
                _with_governance_md(render_issue_dependencies_md(repo=run.repo, links=run.dependencies, limits=DEP_LIMITS), run),
                encoding="utf-8",
            )

        if self._enabled("weekly_digest"):
            digest = build_weekly_digest(run=run, now=run.generated_at, limits=DIGEST_LIMITS)
            (self.output_dir / "weekly_digest.json").write_text(
                json.dumps(_with_governance(digest, run), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            (self.output_dir / "WEEKLY_DIGEST.md").write_text(
                _with_governance_md(render_weekly_digest_md(digest=digest), run),
                encoding="utf-8",
            )

        if self._enabled("issue_health"):
            health = compute_issue_health(run=run, limits=HEALTH_LIMITS)
            (self.output_dir / "issue_health.json").write_text(
                json.dumps(_with_governance(health, run), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            (self.output_dir / "ISSUE_HEALTH.md").write_text(
                _with_governance_md(render_issue_health_md(health=health), run),
                encoding="utf-8",
            )

        if self._enabled("low_signal"):
            low_signal = detect_low_signal_issues(run=run, limits=LOW_SIGNAL_LIMITS)
            (self.output_dir / "low_signal_issues.json").write_text(
                json.dumps(_with_governance(low_signal, run), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            (self.output_dir / "LOW_SIGNAL_ISSUES.md").write_text(
                _with_governance_md(render_low_signal_md(report=low_signal), run),
                encoding="utf-8",
            )

        if self._enabled("knowledge_base"):
            kb = build_knowledge_base(run=run, limits=KB_LIMITS)
            (self.output_dir / "knowledge_base.json").write_text(
                json.dumps(_with_governance(kb, run), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            (self.output_dir / "KNOWLEDGE_BASE.md").write_text(
                _with_governance_md(render_knowledge_base_md(kb=kb), run),
                encoding="utf-8",
            )

        if self._enabled("playbooks"):
            (self.output_dir / "MAINTAINER_PLAYBOOKS.md").write_text(
                _with_governance_md(render_maintainer_playbooks_md(run=run, limits=PLAYBOOK_LIMITS), run),
                encoding="utf-8",
            )

        if self._enabled("maintainer_load"):
            load = compute_maintainer_load(run=run, limits=LOAD_LIMITS)
            (self.output_dir / "maintainer_load.json").write_text(
                json.dumps(_with_governance(load, run), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            (self.output_dir / "MAINTAINER_LOAD.md").write_text(
                _with_governance_md(render_maintainer_load_md(report=load), run),
                encoding="utf-8",
            )

        if self._enabled("explainability"):
            explainability = build_explainability(run=run, limits=EXPL_LIMITS)
            (self.output_dir / "explainability.json").write_text(
                json.dumps(_with_governance(explainability, run), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            (self.output_dir / "EXPLAINABILITY.md").write_text(
                _with_governance_md(render_explainability_md(report=explainability), run),
                encoding="utf-8",
            )

        for a in run.issues:
            issue_dir = self.output_dir / "issues" / str(a.issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "normalized_issue.json").write_text(
                json.dumps(_with_governance(normalized_issue_to_json(a.normalized), run), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            (issue_dir / "quality_breakdown.json").write_text(
                json.dumps(_with_governance(quality_breakdown_to_json(a.quality), run), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            (issue_dir / "maintainer_cost.json").write_text(
                json.dumps(_with_governance(maintainer_cost_to_json(a.maintainer_cost), run), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            (issue_dir / "CONTRIBUTOR_GUIDE.md").write_text(_with_governance_md(render_contributor_guide(a), run), encoding="utf-8")
            (issue_dir / "labels.json").write_text(
                json.dumps(_with_governance(labels_to_json(recommend_labels(a)), run), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            if self._enabled("playbooks"):
                (issue_dir / "playbook.md").write_text(
                    _with_governance_md(render_issue_playbook_md(run=run, analysis=a, limits=PLAYBOOK_LIMITS), run),
                    encoding="utf-8",
                )
            if self._enabled("explainability"):
                (issue_dir / "explainability.json").write_text(
                    json.dumps(
                        _with_governance(build_issue_explainability(run=run, analysis=a, limits=EXPL_LIMITS), run),
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )


def _with_governance(payload: dict[str, object], run: AnalysisRun) -> dict[str, object]:
    return {
        "governance_mode": run.governance_mode,
        **payload,
    }


def _with_governance_md(md: str, run: AnalysisRun) -> str:
    text = md or ""
    lines = text.splitlines()
    if not lines:
        return f"Governance mode: `{run.governance_mode}`\n"

    out: list[str] = []
    out.append(lines[0])
    out.append("")
    out.append(f"Governance mode: `{run.governance_mode}`")
    out.append("")
    out.extend(lines[1:])
    return "\n".join(out).rstrip() + "\n"


def _quality_breakdown_json(run: AnalysisRun) -> dict[str, object]:
    return {
        "generated_at": run.generated_at.isoformat(),
        "repo": run.repo,
        "issues": [
            {
                "issue_number": a.issue_number,
                "quality": quality_breakdown_to_json(a.quality),
            }
            for a in run.issues
        ],
    }


def _labels_json(run: AnalysisRun) -> dict[str, object]:
    return {
        "generated_at": run.generated_at.isoformat(),
        "repo": run.repo,
        "issues": [
            {
                "issue_number": a.issue_number,
                **labels_to_json(recommend_labels(a)),
            }
            for a in run.issues
        ],
    }


def _render_issue_summary(run: AnalysisRun) -> str:
    lines: list[str] = []
    lines.append("# Issue Summary")
    lines.append("")
    lines.append("## Quality breakdown")
    lines.append("")
    lines.append("These scores are deterministic signals designed to help maintainers decide what to do next.")
    lines.append("")
    lines.append("- Completeness: presence of key sections (repro/expected/actual/env/logs)")
    lines.append("- Clarity: whether expected vs actual is clearly stated")
    lines.append("- Reproducibility: whether someone else can reproduce (repro steps + env + logs)")
    lines.append("- Noise: low-signal indicators (very short, noisy title, etc.)")
    lines.append("")
    if run.repo:
        lines.append(f"Repository: `{run.repo}`")
        lines.append("")
    lines.append(f"Generated at: `{run.generated_at.isoformat()}`")
    lines.append("")

    for a in run.issues:
        i = a.normalized.issue
        lines.append(f"## #{i.number}: {i.title}")
        lines.append("")
        lines.append(
            "- Quality: "
            f"completeness {a.quality.completeness}, "
            f"clarity {a.quality.clarity}, "
            f"reproducibility {a.quality.reproducibility}, "
            f"noise {a.quality.noise}"
        )
        lines.append(f"- Triage: **{a.triage.category}** (confidence {a.triage.confidence:.2f})")
        if a.duplicates and a.duplicates.likely_duplicates_of:
            dups = ", ".join(f"#{n}" for n in a.duplicates.likely_duplicates_of)
            lines.append(f"- Likely duplicates of: {dups}")
        if a.normalized.is_low_signal:
            lines.append("- Low signal: **YES**")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_duplicate_groups(run: AnalysisRun) -> str:
    normalized = [a.normalized for a in run.issues]
    dup_map = {a.issue_number: a.duplicates for a in run.issues if a.duplicates is not None}
    # build_duplicate_groups_md expects a dict[int, DuplicateLink]
    return build_duplicate_groups_md(normalized, dup_map, limits=DEFAULT_LIMITS)


def _render_duplicates(run: AnalysisRun) -> str:
    lines: list[str] = []
    lines.append("# Duplicates")
    lines.append("")

    any_dups = False
    for a in run.issues:
        d = a.duplicates
        if not d or not d.likely_duplicates_of:
            continue
        any_dups = True
        lines.append(f"## Issue #{d.issue_number}")
        lines.append("")
        lines.append("Likely duplicates of:")
        for n in d.likely_duplicates_of:
            lines.append(f"- #{n}")
        if d.similarity_reasons:
            lines.append("")
            lines.append("Similarity reasons:")
            for r in d.similarity_reasons:
                lines.append(f"- {r}")
        lines.append("")

    if not any_dups:
        lines.append("No likely duplicates detected.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_triage(run: AnalysisRun) -> str:
    lines: list[str] = []
    lines.append("# Triage")
    lines.append("")

    for a in run.issues:
        i = a.normalized.issue
        lines.append(f"## #{i.number}: {i.title}")
        lines.append("")
        lines.append(f"Category: **{a.triage.category}**")
        lines.append(f"Confidence: `{a.triage.confidence:.2f}`")
        if a.triage.reasons:
            lines.append("")
            lines.append("Reasons:")
            for r in a.triage.reasons:
                lines.append(f"- {r}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_contributor_guide_index(run: AnalysisRun) -> str:
    lines: list[str] = []
    lines.append("# Contributor Guide")
    lines.append("")
    lines.append("Per-issue contributor checklists are available under:")
    lines.append("")
    lines.append("- `.issue-assistant/issues/<issue_number>/CONTRIBUTOR_GUIDE.md`")
    lines.append("")

    for a in run.issues:
        i = a.normalized.issue
        lines.append(f"- Issue #{i.number}: issues/{i.number}/CONTRIBUTOR_GUIDE.md")

    lines.append("")
    return "\n".join(lines)


def _render_maintainer_cost(run: AnalysisRun) -> str:
    lines: list[str] = []
    lines.append("# Maintainer Cost")
    lines.append("")
    lines.append("Cost is a deterministic relative estimate: low / medium / high.")
    lines.append("")

    for a in run.issues:
        i = a.normalized.issue
        lines.append(f"## #{i.number}: {i.title}")
        lines.append("")
        lines.append(f"Estimated cost: **{a.maintainer_cost.level.upper()}**")
        if a.maintainer_cost.reasons:
            lines.append("")
            lines.append("Reasons:")
            for r in a.maintainer_cost.reasons:
                lines.append(f"- {r}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_actions(run: AnalysisRun) -> str:
    lines: list[str] = []
    lines.append("# Maintainer Actions")
    lines.append("")

    for a in run.issues:
        i = a.normalized.issue
        lines.append(f"## #{i.number}: {i.title}")
        lines.append("")
        lines.append("Recommended action:")
        for act in a.maintainer_action.recommended_actions:
            lines.append(f"- {act}")
        if a.maintainer_action.recommended_labels:
            lines.append("")
            lines.append("Recommended labels:")
            for l in a.maintainer_action.recommended_labels:
                lines.append(f"- {l}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_clusters_placeholder(run: AnalysisRun) -> str:
    lines: list[str] = []
    lines.append("# Clusters")
    lines.append("")
    lines.append("Clustering is not implemented in Phase 1.")
    lines.append("")
    return "\n".join(lines)
