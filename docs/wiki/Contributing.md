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

## Pull request checklist

- [ ] `PYTHONPATH=firefly_reports pytest tests/` passes
- [ ] `ruff check firefly_reports/` passes
- [ ] `mypy firefly_reports/` passes
- [ ] `CHANGELOG.md` `[Unreleased]` section updated
- [ ] Report table in `README.md` updated (if adding a report)
- [ ] Wiki [[Reports-Reference|Reports Reference]] updated (if adding a report)
- [ ] No `float` used for monetary values
- [ ] No emojis or filler phrases in source code

## Adding a report

See the dedicated [[Adding-a-New-Report|Adding a New Report]] page for the full step-by-step guide.
