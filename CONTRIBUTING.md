# Contributing

Thanks for helping with firefly-reports. This file is the short version for developers: how to set up the
environment and the checks every change must pass. The full guide (code style, layering rules, commit
messages, pull-request checklist) is on the wiki.

## Development setup

Use Python 3.11 and build the venv from the lock file, so the golden snapshot tests agree with CI:

```bash
git clone https://github.com/fran33git/firefly-reports.git
cd firefly-reports
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r firefly_reports/requirements.txt -e ".[dev,beancount]" pyinstaller
.venv/bin/python -m pre_commit install
```

The `beancount` extra provides `bean-check`, so the ledger integration tests run instead of being skipped.
Call the tools through the venv's Python (`python -m <tool>`): the console scripts of a moved venv can have
broken shebangs.

Try the setup with the built-in sample data (no Firefly III needed):

```bash
python -m firefly_reports demo --out "$TMPDIR/demo"
```

## Local gate

All of these must pass before a commit (no `PYTHONPATH` needed: `pyproject.toml` sets `pythonpath`):

```bash
python -m pytest tests -q --cov=firefly_reports --cov-fail-under=90
python -m ruff check firefly_reports tests tools
python -m ruff format --check firefly_reports tests tools
python -m mypy firefly_reports
python -m bandit -q -r firefly_reports -l -ii --exclude firefly_reports/.venv
python -m pip_audit -r firefly_reports/requirements.txt
```

Ruff, ruff format and mypy also run on `git commit` through pre-commit. Golden snapshots are regenerated
only on purpose (`FIREFLY_UPDATE_GOLDEN=1 python -m pytest -m golden`), with the reason in the commit
message. While refactoring output code, `python tools/ab_snapshot.py write|compare DIR` checks that the
PDFs stay byte-identical; before touching the PyInstaller build, run `bash tools/test-exe.sh`.

Commits are authored as `fran33git` with the GitHub noreply address; `bash tools/check-identity.sh`
checks the identity of the next commit.

To also run the Beancount export integration tests (they call `bean-check` and are skipped otherwise):

```bash
pip install beancount
pytest tests/test_ledger.py tests/test_ledger_cli.py -v
```

Design notes for the export: wiki page *Ledger Architecture* (`docs/wiki/Ledger-Architecture.md`).

## Full developer documentation

See the [GitHub Wiki](https://github.com/fran33git/firefly-reports/wiki) (sources in `docs/wiki/`):

- [Architecture](https://github.com/fran33git/firefly-reports/wiki/Architecture): packages, pipeline, registry, layering rules
- [Adding a New Report](https://github.com/fran33git/firefly-reports/wiki/Adding-a-New-Report)
- [Testing](https://github.com/fran33git/firefly-reports/wiki/Testing): goldens, A/B harness, ledger tests
- [Contributing Guide](https://github.com/fran33git/firefly-reports/wiki/Contributing): code style, commit messages, PR checklist
- [Ledger Architecture](https://github.com/fran33git/firefly-reports/wiki/Ledger-Architecture): the Beancount export internals
