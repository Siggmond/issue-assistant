from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class IssueAuthor:
    login: str
    id: int | None = None


@dataclass(frozen=True)
class IssueLabel:
    name: str


@dataclass(frozen=True)
class IssueComment:
    id: int
    author: IssueAuthor | None
    body: str
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str
    author: IssueAuthor | None
    labels: tuple[IssueLabel, ...] = ()
    state: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    comments: tuple[IssueComment, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    body: str
    author: IssueAuthor | None
    state: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    merged_at: datetime | None = None
    comments: tuple[IssueComment, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Commit:
    sha: str
    message: str
    author: str | None = None
    authored_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DependencyEndpoint:
    kind: str  # issue | pull_request | commit
    repo: str | None
    identifier: str


@dataclass(frozen=True)
class DependencyLink:
    source: DependencyEndpoint
    target: DependencyEndpoint
    reference_type: str
    evidence: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class NormalizedIssue:
    issue: Issue
    normalized_title: str
    sections: dict[str, str]
    is_low_signal: bool
    low_signal_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class QualityBreakdown:
    completeness: int
    clarity: int
    reproducibility: int
    noise: int
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class TriageClassification:
    category: str
    confidence: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class LifecycleClassification:
    state: str
    confidence: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaintainerCostEstimate:
    level: str
    reasons: tuple[str, ...] = ()
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DuplicateLink:
    issue_number: int
    likely_duplicates_of: tuple[int, ...]
    similarity_reasons: tuple[str, ...]


@dataclass(frozen=True)
class MaintainerAction:
    recommended_actions: tuple[str, ...]
    recommended_labels: tuple[str, ...] = ()
    recommended_assignees: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class IssueAnalysis:
    issue_number: int
    normalized: NormalizedIssue
    quality: QualityBreakdown
    triage: TriageClassification
    lifecycle: LifecycleClassification
    maintainer_cost: MaintainerCostEstimate
    duplicates: DuplicateLink | None
    maintainer_action: MaintainerAction


@dataclass(frozen=True)
class AnalysisRun:
    generated_at: datetime
    repo: str | None
    issues: tuple[IssueAnalysis, ...]
    dependencies: tuple[DependencyLink, ...] = ()
    governance_mode: str = "dry-run"

    def as_json_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "repo": self.repo,
            "governance_mode": self.governance_mode,
            "issues": [issue_analysis_to_json(i) for i in self.issues],
            "dependencies": [dependency_link_to_json(d) for d in self.dependencies],
        }


def _dt(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def issue_to_json(issue: Issue) -> dict[str, Any]:
    return {
        "number": issue.number,
        "title": issue.title,
        "body": issue.body,
        "author": None if issue.author is None else {"login": issue.author.login, "id": issue.author.id},
        "labels": [l.name for l in issue.labels],
        "state": issue.state,
        "created_at": _dt(issue.created_at),
        "updated_at": _dt(issue.updated_at),
        "closed_at": _dt(issue.closed_at),
        "comments": [
            {
                "id": c.id,
                "author": None if c.author is None else {"login": c.author.login, "id": c.author.id},
                "body": c.body,
                "created_at": _dt(c.created_at),
                "updated_at": _dt(c.updated_at),
            }
            for c in issue.comments
        ],
    }


def issue_analysis_to_json(a: IssueAnalysis) -> dict[str, Any]:
    return {
        "issue": issue_to_json(a.normalized.issue),
        "normalized": normalized_issue_to_json(a.normalized),
        "quality": quality_breakdown_to_json(a.quality),
        "triage": {
            "category": a.triage.category,
            "confidence": a.triage.confidence,
            "reasons": list(a.triage.reasons),
        },
        "lifecycle": lifecycle_to_json(a.lifecycle),
        "maintainer_cost": maintainer_cost_to_json(a.maintainer_cost),
        "duplicates": None
        if a.duplicates is None
        else {
            "issue_number": a.duplicates.issue_number,
            "likely_duplicates_of": list(a.duplicates.likely_duplicates_of),
            "similarity_reasons": list(a.duplicates.similarity_reasons),
        },
        "maintainer_action": {
            "recommended_actions": list(a.maintainer_action.recommended_actions),
            "recommended_labels": list(a.maintainer_action.recommended_labels),
            "recommended_assignees": list(a.maintainer_action.recommended_assignees),
            "notes": list(a.maintainer_action.notes),
        },
    }


def normalized_issue_to_json(n: NormalizedIssue) -> dict[str, Any]:
    return {
        "normalized_title": n.normalized_title,
        "sections": dict(n.sections),
        "is_low_signal": n.is_low_signal,
        "low_signal_reasons": list(n.low_signal_reasons),
    }


def quality_breakdown_to_json(q: QualityBreakdown) -> dict[str, Any]:
    return {
        "completeness": q.completeness,
        "clarity": q.clarity,
        "reproducibility": q.reproducibility,
        "noise": q.noise,
        "reasons": list(q.reasons),
    }


def lifecycle_to_json(l: LifecycleClassification) -> dict[str, Any]:
    return {
        "state": l.state,
        "confidence": l.confidence,
        "reasons": list(l.reasons),
    }


def maintainer_cost_to_json(c: MaintainerCostEstimate) -> dict[str, Any]:
    return {
        "level": c.level,
        "reasons": list(c.reasons),
        "signals": dict(c.signals),
    }


def dependency_link_to_json(d: DependencyLink) -> dict[str, Any]:
    return {
        "source": {
            "kind": d.source.kind,
            "repo": d.source.repo,
            "identifier": d.source.identifier,
        },
        "target": {
            "kind": d.target.kind,
            "repo": d.target.repo,
            "identifier": d.target.identifier,
        },
        "reference_type": d.reference_type,
        "evidence": d.evidence,
        "reasons": list(d.reasons),
    }
