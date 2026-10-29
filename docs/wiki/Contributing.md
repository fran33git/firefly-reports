# Contributing

## Code style

- **Linter:** `ruff` with line length 100. Run `ruff check firefly_reports/`.
- **Formatter:** `ruff format`. Run `ruff format firefly_reports/`.
- **Type checker:** `mypy` with `disallow_untyped_defs = true`. All public functions must be fully typed.
- **No emojis** anywhere in source code, docstrings, or comments.
- **No filler docstrings:** do not write "This function handles..." or restate the function name. Every docstring must add information not already obvious from the signature.
- **Monetary values:** always use `Decimal` via `_d()` (in `data_processor.py`) or `_dec()` (in `firefly_client.py`). Never use `float` for money.

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|--------|---------|
| `feat:` | New report, new flag, new behaviour |
| `fix:` | Bug fix |
| `refactor:` | Code change with no behaviour change |
| `test:` | Adding or fixing tests |
| `docs:` | Documentation only |
| `chore:` | Tooling, CI, dependencies |

Examples:
```
feat(pdf): add liquidity forecast renderer
fix(client): use Decimal instead of float in get_annual_totals
docs(wiki): add Troubleshooting page
```

## Pre-commit hooks

Hooks run automatically on `git commit` after `pre-commit install`:

```bash
pre-commit install       # one-time setup
pre-commit run --all-files   # run manually on all files
```

The hooks run `ruff check`, `ruff format --check`, and `mypy`. Fix any issues before committing.

`pre-commit install` also installs a `pre-push` hook (`tools/check-publish.sh`, pre-commit 3.2 or newer) that refuses to push commits containing paths that must not be public (local tool folders, credentials, bundles ...). Maintainers can add a private list of personal strings to check for in `~/.config/firefly-reports/deny-patterns`; contributors do not need it, the script then only runs the path check.

## Pull request checklist

- [ ] `pytest tests/` passes
- [ ] `ruff check firefly_reports/` passes
- [ ] `mypy firefly_reports/` passes
- [ ] `CHANGELOG.md` `[Unreleased]` section updated
- [ ] Report table in `README.md` updated (if adding a report)
- [ ] Wiki [[Reports-Reference|Reports Reference]] updated (if adding a report)
- [ ] No `float` used for monetary values
- [ ] Diagrams in the wiki are Mermaid (` ```mermaid ` blocks, rendered by GitHub); check new ones with `npx @mermaid-js/mermaid-cli` before pushing
- [ ] Wiki pages and `README.md` updated if you changed the ledger export, its options or the mapping file

## Working on the ledger export

* Keep the layering from [[Ledger-Architecture]]: conversion and writers are pure; only `export.py`,
  `validate.py`, `atomic_write()` and the config loader touch files or processes.
* New user-facing strings go to the `[ledger]` section of **both** `en.toml` and `it.toml`; errors use
  `LedgerError("ledger.err_...", **params)` so they are translated when displayed.
* Metadata key translations must match `[a-z][a-zA-Z0-9_-]*` (a test enforces it).
* Install `beancount` locally so the `bean-check` integration tests run instead of being skipped.
* A new output format is a new writer: see "Adding a new format" in [[Ledger-Architecture]].

## Adding a report

See the dedicated [[Adding-a-New-Report|Adding a New Report]] page for the full step-by-step guide.
