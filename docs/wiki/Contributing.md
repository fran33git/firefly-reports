# Contributing

This page is for developers who want to send a change to firefly-reports: how to set up a development
environment, the local gate every commit must pass, the code style, commit conventions and the
pull-request checklist. The design itself is described in [[Architecture]] and the tests in [[Testing]].

## Development setup

The project targets Python 3.11 (CI also runs 3.12). Build the venv from the lock file so that the
golden snapshots agree with CI:

```bash
git clone https://github.com/fran33git/firefly-reports.git
cd firefly-reports
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r firefly_reports/requirements.txt -e ".[dev,beancount]" pyinstaller
.venv/bin/python -m pre_commit install
```

The `beancount` extra provides `bean-check`, so the ledger integration tests run instead of being
skipped; `pyinstaller` is needed only for `tools/test-exe.sh`.

Call the dev tools through the venv's Python (`python -m pytest`, `python -m mypy`, ...): the console
scripts of a moved venv can have broken shebangs.

Check that the setup works with the built-in sample data (no Firefly III needed):

```bash
python -m firefly_reports demo --out "$TMPDIR/demo"
```

## Local gate

All of these must pass before a commit:

```bash
python -m pytest tests -q --cov=firefly_reports --cov-fail-under=90
python -m ruff check firefly_reports tests tools
python -m ruff format --check firefly_reports tests tools
python -m mypy firefly_reports
python -m bandit -q -r firefly_reports -l -ii --exclude firefly_reports/.venv
python -m pip_audit -r firefly_reports/requirements.txt
```

`pip-audit` needs network access to the vulnerability database. Two more checks apply only in specific
cases:

```bash
# Only while refactoring output code: the PDFs must stay byte-identical (see Testing)
python tools/ab_snapshot.py compare "$TMPDIR/ab/baseline"

# Only before touching the PyInstaller build configuration
bash tools/test-exe.sh
```

CI (`.github/workflows/ci.yml`) runs the same lint, type, test (Python 3.11 and 3.12), audit and bandit
jobs on every pull request, plus a Windows executable smoke test.

## Pre-commit hooks

After `pre-commit install`, every `git commit` runs ruff (with `--fix`), ruff format and mypy:

```bash
python -m pre_commit run --all-files
```

The hooks do not run the tests: run the local gate yourself.

## Code style

- **Ruff:** line length 100, target Python 3.11, rules `E, W, F, I, N, UP, B, SIM` (`E501` ignored). The
  only per-file ignore is `N806` in `reports/*/pdf.py`, where ReportLab layout code uses names such as
  `W`, `H` and `COL_W`.
- **Formatting:** `ruff format`, checked in CI.
- **Typing:** mypy is strict everywhere (`disallow_untyped_defs`, `warn_return_any`, no relaxed modules).
- **Imports:** package-qualified absolute imports (`from firefly_reports.reports.options import Period`);
  no `importlib` or `__import__` (PyInstaller follows static imports only).
- **Money:** always `Decimal` with two decimal places via `_d()` (`reports/_money.py`), never a float.
- **Layering:** keep builders pure, `render/` report-agnostic and console I/O inside `cli/`. The rules are
  listed in [[Architecture]] and enforced by `tests/test_architecture.py`.
- **Time:** read the current date through `firefly_reports.clock`, not `datetime.now()`, so output stays
  reproducible in tests.
- **Strings:** every user-facing string goes to **both** `translations/en.toml` and `translations/it.toml`.
- **Python version:** no syntax or APIs that need 3.12 or later.
- **No network** outside `firefly_client.py`; test data stays offline.

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|---|---|
| `feat:` | New report, new flag, new behaviour |
| `fix:` | Bug fix |
| `refactor:` | Code change with no behaviour change |
| `test:` | Adding or fixing tests |
| `docs:` | Documentation only |
| `chore:` | Tooling, CI, dependencies |

Examples:

```text
feat(reports): add the goal deadlines report
fix(client): retry once on HTTP 429 when fetching linked transactions
docs(wiki): describe the [export] config section
```

When a commit regenerates golden snapshots, say why in the message.

Commits are authored as the GitHub account `fran33git` with its `users.noreply.github.com` address. Check
the identity of the next commit with:

```bash
bash tools/check-identity.sh
```

CI runs the same script on the commit range of the maintainer's pull requests.

## Compatibility

- **Stable** (semantic versioning): the command line, that is commands, flags, exit codes, config keys,
  environment variables and output file names.
- **Provisional:** the names in `firefly_reports.__all__` (the facade in `api.py`); they may change in a
  minor release until declared stable.
- **Internal:** everything else (`reports`, `render`, `cli`, `ledger`, `firefly_client`, `i18n`, `clock`,
  `demo`).

Deprecations are announced in one major release (a stderr warning for the CLI, a `DeprecationWarning`
for Python), kept for the rest of that major and removed in the next one. Deprecated in 2.0 and removed
in 3.0: running reports without a subcommand, the hidden root-level `--out/--start/--end`,
`python -m firefly_reports.main` and `python -m firefly_reports.demo`.

## Pull request checklist

- [ ] The local gate passes
- [ ] Golden changes are intended, reviewed and explained in the commit message
- [ ] New strings are in both `en.toml` and `it.toml`
- [ ] New config keys are in `KNOWN_KEYS` (`cli/config.py`) and in the commented template of `cli/init.py`
- [ ] `CHANGELOG.md` updated
- [ ] User documentation updated: the wiki pages under `docs/wiki/` and `README.md` (for example
  [[Reports-Reference|Reports Reference]] when adding a report, [[Configuration]] for a new flag or key)
- [ ] Diagrams in the wiki are Mermaid (` ```mermaid ` blocks, rendered by GitHub), each with a one-line
  caption and a description in the text so the page reads without it; check new ones with
  `npx @mermaid-js/mermaid-cli` before pushing

## Working on the ledger export

- Keep the layering described in [[Ledger-Architecture|Ledger Architecture]]: conversion and writers are
  pure; only `export.py`, `validate.py`, `writers/base.atomic_write()` and `mapping.load_ledger_config()`
  touch files or processes.
- New user-facing strings go to the `[ledger]` section of both translation files; errors use
  `LedgerError("ledger.err_...", **params)` so they are translated when displayed.
- Metadata key translations must match `[a-z][a-zA-Z0-9_-]*` (a test enforces it).
- Keep `docs/wiki/Beancount-Export.md`, `docs/wiki/Ledger-Architecture.md` and `beancount_map.example.yaml`
  in sync with behaviour changes.

## Documentation

`docs/wiki/` is the single source of truth for the wiki: a push to `main` that touches `docs/wiki/**`
publishes the pages to the GitHub Wiki (`.github/workflows/wiki-sync.yml`). Edit the pages only there.

## Adding a report

See [[Adding-a-New-Report|Adding a New Report]].
