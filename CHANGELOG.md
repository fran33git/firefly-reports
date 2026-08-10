# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.2] - 2026-08-10

### Fixed
- Windows executable crashed with `UnicodeEncodeError` on consoles using legacy
  codepages (e.g. cp1252) when printing help or messages containing non-ASCII
  characters (`€`, `—`): console output now replaces unencodable characters
  instead of crashing. The 1.0.1 PyPI release is affected by this bug on
  cp1252 Windows consoles; 1.0.2 supersedes it.

## [1.0.1] - 2026-08-10

### Added
- PyPI packaging: `pip install firefly-iii-reports` with a `firefly-reports` CLI command
  (the distribution is named `firefly-iii-reports` because `firefly-reports` was
  already taken on PyPI by an unrelated project)
- Release workflow: tag `v*` publishes sdist/wheel to PyPI (OIDC Trusted Publishing),
  builds a standalone Windows executable (PyInstaller) and creates a GitHub Release
- Wiki sync workflow: `docs/wiki/` is the single source of truth, pushed
  automatically to the GitHub Wiki on every change

### Changed
- Internal imports converted from flat to package-qualified
  (`from firefly_reports.X import ...`); run from source with
  `python -m firefly_reports.main` and tests with plain `pytest tests/`

### Fixed
- Coverage badge: CI job now commits the generated badge SVG
  (previously skipped because `git diff` ignores untracked files)

## [1.0.0] - 2026-08-09

Initial public release.

### Added

#### Reports
- 26 financial reports in total: Cash Flow, Income vs Expense, Transaction Register,
  Net Worth, Account Statements, Tax Summary, Expense Trend, Tagged Report,
  Budget vs Actual, Bills & Subscriptions, Savings Goals, Liabilities, KPI Scorecard,
  Year-over-Year, Cumulative Cash Flow, Income by Client (reports 1–16)
- Transaction Audit Log with technical IDs, book dates, reconciliation status,
  attachment markers (report 17)
- Budget Performance Forecast based on daily spending velocity (report 18)
- Category Ledger: all transactions grouped alphabetically by category (report 19)
- Payee Ledger: all transactions grouped alphabetically by payee (report 20)
- Linkage & Reimbursement Report: expense/reimbursement pairs with link type and
  linked-amount percentage (report 21)
- All Tags Ledger: transactions grouped by tag (report 22, requires `--all-tags`)
- Historical Growth: multi-year income/expense/net comparison (report 23, `--years 3|5`)
- Liquidity Forecast: 6-month projected balance based on bills and average cash flow (report 24)
- General Journal (report 25, Libro Giornale): chronological double-entry register
  with runtime protocol numbers, Debit/Credit columns and daily totals, landscape A4
- Summary (report 26): Firefly instance details (version, API version, OS, PHP,
  user email/role), global counts and period statistics; PDF in
  standard mode plus an always-present Excel sheet
- Income & Expense Dashboard and KPI Trend Dashboard PDFs sharing one chart
  identity (steel/slate palette, 200 dpi, locale-aware compact number
  formatting): KPI card strip, spending donut with side legend, monthly
  income-vs-expense combo chart with net line, and a cumulative net cash
  flow area chart
- Cash flow statement waterfall section: operating / investing / financing
  activities with opening and closing cash in the Cash Flow PDF

#### Output
- PDF output via ReportLab (landscape A4 for wide reports)
- Excel workbook via openpyxl (16 core report sheets plus Summary; Account
  Statements contributes one sheet per asset account)

#### CLI and configuration
- CLI entry point (`main.py`) with full flag set: `--url`, `--token`, `--start`, `--end`,
  `--owner`, `--currency`, `--out`, `--lang`, `--years`, `--tags`, `--fetch-links`,
  `--link-delay`, `--all-tags`, `--legacy-report`, `--no-pdf`, `--no-excel`,
  `--debug`, `--debug-file`
- `--year YYYY` full-year mode: unlocks year-only reports (YoY, Historical Growth,
  Liquidity Forecast); `--start`/`--end` date-range mode skips them
- Global filters (CLI flags or `[filters]` TOML section): `--accounts-include`/
  `--accounts-exclude`, `--categories-include`/`--categories-exclude`,
  `--hide-transfers`, `--reconciled-only`, `--fiscal-year-start MM-DD`
- `python main.py init` — interactive config file wizard generating `firefly-reports.toml`
- Credential chain: CLI flag → env var → `.env` file → TOML config → interactive prompt
- TOML config file support (`firefly-reports.toml`) with `[reports]` and `[tax]` sections
- i18n support: English and Italian output via `--lang en|it`; per-key English
  fallback in `i18n.t()`
- `--legacy-report` flag to use classic PDF styles, skip strategic reports and
  generate the `audit_log` PDF (the only mode that produces it)

#### API client
- `FireflyClient` with transparent multi-page pagination
- `get_about()` and `get_about_user()` fetch instance info from `/api/v1/about`
  and `/api/v1/about/user` for the Summary report
- Transaction links fetched from the real `/api/v1/transaction-links` and
  `/api/v1/link-types` endpoints; linked journals deep-fetched via
  `/api/v1/transaction-journals/{id}` with configurable rate limiting (`--link-delay`)
- Automatic retry on HTTP 429 with `Retry-After` header support
- Token always redacted in debug logs

#### Developer experience
- Full type hints and Google-style docstrings on all public functions (English)
- 175-test suite covering all `build_*()` functions, client methods, and PDF smoke tests
- GitHub Actions CI: lint (ruff), type check (mypy), tests on Python 3.11 and 3.12,
  dependency security audit (pip-audit)
- Pre-commit hooks: ruff, mypy
- `demo.py` — full demo with realistic mock data, no Firefly III instance required
  (`--year YYYY`, `--lang en|it`)
- `.env.example` for credential configuration
