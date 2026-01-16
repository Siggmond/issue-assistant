# Contributing

Thanks for taking the time to contribute.

This project prioritizes determinism, clarity, and safety over cleverness.
Small, focused changes are preferred.

---

## Development setup

- Python 3.10 or newer
- Create and activate a virtual environment
- Install in editable mode

```bash
pip install -e .
```

---

## Running tests

```bash
python -m pytest -q
```

All tests must pass before submitting a pull request.

---

## Design constraints

When contributing, please preserve:

- deterministic behavior
- explainability guarantees
- governance boundaries (dry-run must be a hard no-op)

If a change alters outputs, update tests and documentation accordingly.

---

## Reporting bugs

Please include:

- what you expected to happen
- what actually happened
- steps to reproduce
- your OS and Python version
- any relevant logs or artifacts
