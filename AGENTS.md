# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project overview

**firefly-reports** generates 26 financial reports (PDF + Excel) from a [Firefly III](https://www.firefly-iii.org/) instance, targeted at individuals, freelancers and small businesses who want a complete annual financial overview.

- Language: Python >= 3.11
- License: GPL-3.0-or-later
- Repository: https://github.com/fran33git/firefly-reports
- Packaging: setuptools (`pyproject.toml`); dependencies also pinned in `firefly_reports/requirements.txt` (source list in `requirements.in`)
- Runtime dependencies: `requests`, `reportlab` (PDF), `openpyxl` (Excel), `matplotlib` (charts), `python-dateutil`, `python-dotenv`

## Architecture

The pipeline is strictly linear: **API → processor → exporters**.

```
firefly_client.py  →  data_processor.py  →  pdf_exporter.py
                                          →  excel_exporter.py
```

All modules live in `firefly_reports/` and are imported as package-qualified absolute imports (e.g. `from firefly_reports.data_processor import ...`). pytest resolves them via `pythonpath = ["."]` in `pyproject.toml`.

| Module | Role |
|---|---|
| `firefly_client.py` | `FireflyClient` wraps the Firefly III REST API; `_get_paginated()` handles pagination; `get_transactions()` flattens nested splits into a flat list of dicts; `get_about()`/`get_about_user()` fetch instance info for the `summary` report |
| `data_processor.py` | 26 `build_*` functions plus `apply_global_filters()`, each taking flat transaction/account/budget/bills data and returning a plain dict ready for rendering. All monetary values are `Decimal` (2 dp) via `_d()`. Zero I/O. |
| `pdf_exporter.py` | 28 `render_*_pdf(data, path)` functions using ReportLab (26 matching `build_*` + 2 dashboard variants). Colour constants and `_make_header_footer()` at the top of the file. |
| `excel_exporter.py` | `render_all_xlsx()` (3 sheets, legacy) and `render_all_xlsx_full()` (16 core report sheets + Summary, used by `main.py` and `demo.py`; Account Statements contributes one sheet per asset account) |
| `chart_engine.py` | matplotlib (Agg backend) chart generators returning `io.BytesIO` PNG buffers |
| `main.py` | CLI entry point (installed as `firefly-reports`; from source `python -m firefly_reports.main ...`); orchestrates fetch → process → export. Subcommand `firefly-reports init` runs an interactive wizard that creates `firefly-reports.toml` |
| `demo.py` | Exercises all 26 report types using inline English mock data (`TXN_2025`, `TXN_2024`, `ACCOUNTS`, `LIABILITIES`, `BUDGETS`, `BILLS`, `PIGGY_BANKS`, `TRANSACTION_LINKS`) — no Firefly III needed. Writes to `./output` by default (override with `--out`); full year via `--year YYYY` (default 2025); report language selectable with `--lang en\|it` (default `en`) |
| `config.py` | Loads `./firefly-reports.toml` (cwd) via `tomllib`; returns `{}` if missing |
| `i18n.py` | Loads `firefly_reports/translations/{lang}.toml` into a module-level `T` dict; `t("pdf.category")` accessor falls back to `en`, then returns the key itself |
| `translations/` | `en.toml`, `it.toml` — output languages English and Italian |

### Configuration precedence

Token/URL come from CLI flags (`--url`, `--token`), env vars `FIREFLY_URL`/`FIREFLY_TOKEN`, a `.env` file, a `firefly-reports.toml` config file, or an interactive prompt. See `.env.example` and `docs/wiki/Configuration.md` for all keys (including `--tags`, `--all-tags`, `--years`, `--legacy-report`, `--lang`, `--no-pdf`/`--no-excel`). Note: the `audit_log` PDF is generated only when `--legacy-report` is active; the `summary` report takes its slot in standard mode.

### Transaction type semantics

| Firefly type | Behaviour |
|---|---|
| `deposit` | Income (+) |
| `withdrawal` | Expense (−) |
| `transfer` | Shown in the register, neutral for cash flow |
| `opening balance` | Ignored in all reports |

## Build and test commands

There is no compiled build step; it is a plain Python application.

```bash
# Setup (a .venv already exists at .venv/ in the repo root)
pip install -e ".[dev]"          # or: pip install -r firefly_reports/requirements.txt
pre-commit install

# Run against a real instance (or use the installed `firefly-reports` command)
python -m firefly_reports.main --url https://firefly.example.com \
  --start 2025-01-01 --end 2025-12-31 --owner "Your Name" --out ./output

# Run with mock data (no Firefly III needed)
python -m firefly_reports.demo --out ./output

# Tests (no PYTHONPATH needed — pyproject.toml sets pythonpath = ["."])
pytest tests/ -v
pytest tests/ --cov=firefly_reports --cov-report=term-missing

# Lint / type check / security
ruff check firefly_reports/
ruff format --check firefly_reports/
mypy firefly_reports/
bandit -r firefly_reports/ -l -ii --exclude firefly_reports/demo.py,firefly_reports/.venv
pip-audit -r firefly_reports/requirements.txt
```

## Code style guidelines

- Ruff: `line-length = 100`, target `py311`; lint rules `E, W, F, I, N, UP, B, SIM`; `E501` ignored. Per-file ignores exist for `pdf_exporter.py` (`N806`, `E701`) and `excel_exporter.py` (`E701`) — do not "fix" those violations there.
- Ruff format is enforced in CI (`ruff format --check`).
- mypy: `disallow_untyped_defs = true` globally, but relaxed for `pdf_exporter`, `excel_exporter`, `demo`, and `main`. Missing-import stubs ignored for `reportlab`, `openpyxl`, `matplotlib`, `dateutil`.
- Use package-qualified absolute imports (`from firefly_reports.data_processor import ...`) — this is how `main.py`, `demo.py`, and the tests import each other.
- Keep `data_processor.py` free of I/O: it only transforms dicts into dicts. Rendering lives exclusively in the exporters.
- Monetary values are always `Decimal` (2 decimal places) produced via `_d()` in `data_processor.py` — never raw floats for money.

## Testing instructions

- Framework: pytest (with `pytest-cov`; CI enforces `--cov-fail-under=60`, `demo.py` excluded from coverage). Config in `pyproject.toml` (`testpaths = ["tests"]`).
- Run from the repo root with plain pytest (no `PYTHONPATH` needed — `pyproject.toml` sets `pythonpath = ["."]`): `pytest tests/ -v`.
- Tests must not require a live Firefly III instance: fixtures in `tests/conftest.py` derive from the mock data in `demo.py`, and HTTP calls are mocked with the `responses` library (see `tests/test_firefly_client.py`).
- `conftest.py` loads English translations once per session via `i18n.load("en")` — keep this autouse fixture when adding tests that touch rendered strings.

## Adding a new report

1. Add a `build_<name>()` function in `data_processor.py` — return a plain dict.
2. Add `render_<name>_pdf()` in `pdf_exporter.py`.
3. Add a sheet in `render_all_xlsx_full()` in `excel_exporter.py`.
4. Wire it into `demo.py` with mock data to verify output before connecting to a real instance.
5. Add/extend tests under `tests/`; update any user-facing strings in both `translations/en.toml` and `translations/it.toml`.

## CI and deployment

- GitHub Actions (`.github/workflows/ci.yml`) runs on pushes to `main`/`develop` and on all PRs: ruff lint + format check, mypy, pytest matrix on Python 3.11/3.12 with coverage threshold, `pip-audit`, and `bandit`.
- Pre-commit hooks (`.pre-commit-config.yaml`) run ruff (with `--fix`), ruff-format, and mypy on commit.
- Release workflow (`.github/workflows/release.yml`): pushing a tag `v*` checks the tag matches the package version, runs tests, builds the sdist/wheel, publishes to PyPI via OIDC Trusted Publishing (configure the Trusted Publisher on pypi.org), builds a standalone Windows executable with PyInstaller, and creates a GitHub Release. The PyPI distribution is named `firefly-iii-reports` (`firefly-reports` was already taken by an unrelated project); the import package stays `firefly_reports` and the CLI command `firefly-reports`.
- Wiki sync workflow (`.github/workflows/wiki-sync.yml`): a push to `main` touching `docs/wiki/**` pushes the pages to the GitHub Wiki repository automatically.

## Security considerations

- **Never commit tokens.** The Firefly III Personal Access Token comes from `FIREFLY_TOKEN`, `.env`, or `firefly-reports.toml`; `.env` is gitignored (see `.env.example`).
- Bandit runs in CI; `demo.py` and `.venv` are excluded from the scan.
- Dependencies are audited in CI with `pip-audit` against `firefly_reports/requirements.txt`.
- Do not introduce network calls outside `firefly_client.py`; keep mock/test data offline.

## Documentation

Full user/developer documentation mirrors the GitHub Wiki under `docs/wiki/` (Installation, Configuration, Reports Reference, Architecture, Testing, Troubleshooting, Adding a New Report, Contributing). `docs/wiki/` is the single source of truth — edit pages only there; the `wiki-sync` workflow pushes them to the GitHub Wiki automatically. Keep `README.md`, `CONTRIBUTING.md`, `CLAUDE.md`, and the wiki files in sync when changing workflows or report lists.
