from __future__ import annotations

from issue_assistant.models import Issue
from issue_assistant.phases.normalization import normalize_issue
from issue_assistant.phases.duplicates import build_duplicate_groups_md, detect_duplicates_v2


def test_duplicates_v2_groups_by_error_signature_hash() -> None:
    a = Issue(
        number=1,
        title="Crash on startup",
        body="""
```python
Traceback (most recent call last):
ValueError: invalid config 123
```
""".strip(),
        author=None,
    )
    b = Issue(
        number=2,
        title="Startup crash",
        body="""
```python
Traceback (most recent call last):
ValueError: invalid config 999
```
""".strip(),
        author=None,
    )
    c = Issue(
        number=3,
        title="Unrelated",
        body="Something else",
        author=None,
    )

    normalized = [normalize_issue(x) for x in (a, b, c)]
    dup_map = detect_duplicates_v2(normalized)

    assert 1 in dup_map
    assert 2 in dup_map

    md = build_duplicate_groups_md(normalized, dup_map)
    assert "Reason: error signature hash match" in md
    assert "#1" in md
    assert "#2" in md
