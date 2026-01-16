from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from issue_assistant.cli import main


def test_cli_accepts_governance_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    issues_file = tmp_path / "issues.json"
    issues_file.write_text(
        json.dumps(
            [
                {
                    "number": 1,
                    "title": "Crash",
                    "body": "",
                    "state": "open",
                    "labels": [],
                    "comments": [],
                    "created_at": "2026-01-15T00:00:00Z",
                    "updated_at": "2026-01-15T00:00:00Z",
                    "user": {"login": "u", "id": 1},
                }
            ]
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "issue-assistant",
            "analyze",
            "--issues-file",
            str(issues_file),
            "--output-dir",
            str(out_dir),
            "--governance-mode",
            "dry-run",
        ],
    )

    main()

    assert (out_dir / "issues.json").exists()

    payload = json.loads((out_dir / "issues.json").read_text(encoding="utf-8"))
    assert payload.get("governance_mode") == "dry-run"
