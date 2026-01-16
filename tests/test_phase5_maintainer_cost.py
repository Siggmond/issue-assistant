from __future__ import annotations

from issue_assistant.models import Issue, QualityBreakdown
from issue_assistant.phases.maintainer_cost import estimate_maintainer_cost
from issue_assistant.phases.normalization import normalize_issue


def test_maintainer_cost_high_for_many_files_and_no_repro() -> None:
    body = """
This breaks.

Related: a.py b.py c.py d.py e.py
""".strip()

    n = normalize_issue(Issue(number=1, title="Bug", body=body, author=None))
    q = QualityBreakdown(completeness=0, clarity=0, reproducibility=0, noise=80, reasons=())

    c = estimate_maintainer_cost(normalized=n, quality=q)
    assert c.level in ("medium", "high")


def test_maintainer_cost_low_when_reproducible_and_short() -> None:
    body = """
### Steps to reproduce
1. Run X
2. Observe Y

### Logs
ValueError: boom
""".strip()

    n = normalize_issue(Issue(number=2, title="Crash", body=body, author=None))
    q = QualityBreakdown(completeness=80, clarity=50, reproducibility=100, noise=0, reasons=())

    c = estimate_maintainer_cost(normalized=n, quality=q)
    assert c.level == "low"
