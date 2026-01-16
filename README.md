# Issue Assistant

[![PyPI version](https://img.shields.io/pypi/v/issue-assistant.svg)](https://pypi.org/project/issue-assistant/)
[![PyPI downloads](https://img.shields.io/pypi/dm/issue-assistant.svg)](https://pypi.org/project/issue-assistant/)
[![Python versions](https://img.shields.io/pypi/pyversions/issue-assistant.svg)](https://pypi.org/project/issue-assistant/)
[![License](https://img.shields.io/pypi/l/issue-assistant.svg)](LICENSE)
[![Tests](https://github.com/Siggmond/issue-assistant/actions/workflows/issue-assistant.yml/badge.svg)](https://github.com/Siggmond/issue-assistant/actions)
[![GitHub stars](https://img.shields.io/github/stars/Siggmond/issue-assistant.svg?style=social)](https://github.com/Siggmond/issue-assistant)


Issue Assistant is a deterministic GitHub issue triage engine designed for maintainers who want
consistent, explainable signals without automation they can’t trust.

It analyzes GitHub issues and produces **Markdown and JSON artifacts** that help answer:

- Is this issue actionable or missing critical information?
- Does it appear to be a duplicate of existing work?
- How much maintainer effort is likely required?
- Why did the tool reach this conclusion?

All outputs are written to `.issue-assistant/`. Nothing is hidden, guessed, or implicit.

---

## Why this exists

Maintainers spend a disproportionate amount of time triaging issues that are:

- missing reproduction steps, logs, or environment details
- duplicates that fragment discussion
- unclear about expected vs actual behavior
- noisy or low-signal

Issue Assistant provides a **deterministic baseline** for triage so humans can make faster,
more consistent decisions without surrendering control.

---

## Design principles

Issue Assistant is intentionally conservative:

- **Deterministic only** — no LLMs, no probabilistic output
- **Explainable by construction** — every outcome maps to rules and evidence
- **Governance-aware** — safe defaults, no surprise side effects
- **Human-first** — maintainers always make the final call

If a signal cannot be explained clearly, it does not exist.

---

## Installation

Requires **Python 3.10+**.

```bash
pip install issue-assistant
```

---

## Run locally

```bash
issue-assistant analyze \
  --github-token "$GITHUB_TOKEN" \
  --repo owner/name \
  --output-dir .issue-assistant \
  --governance-mode dry-run
```

This performs a full analysis and writes artifacts locally without modifying issues.

---

## GitHub Action

Issue Assistant is available as a GitHub Action:

```yaml
uses: siggmond/issue-assistant@v0.2.0
```

The Action is a thin wrapper around the CLI. You can use the CLI independently or rely
entirely on the Action.

Typical triggers include:

- issue opened / edited / reopened
- scheduled runs (weekly digest)

Artifacts can be uploaded or committed depending on your workflow.

---

## Governance modes

| Mode | Comments | Label suggestions | Intended use |
|------|----------|------------------|--------------|
| dry-run | never | never | analysis only; safest default |
| strict | limited | no | request missing info, flag duplicates |
| aggressive | yes | yes (suggestions) | higher throughput without auto-closing |

Hard constraints:

- issues are never auto-closed
- fixes are never guessed
- maintainer decisions are never overridden

---

## Artifacts generated

A typical run produces:

- ISSUE_SUMMARY.md / issues.json
- MAINTAINER_LOAD.md / maintainer_load.json
- EXPLAINABILITY.md / explainability.json
- per-issue playbooks and explainability JSON

Example outputs are included under `docs/`.

---

## When not to use this tool

Issue Assistant is not a good fit if you want:

- fully automated triage or auto-closing
- subjective or sentiment-based analysis
- invisible automation
- zero repository artifacts

---

## Philosophy

Explainability is a core invariant.

If the tool cannot explain *why* it produced an output,
that output should not exist.
