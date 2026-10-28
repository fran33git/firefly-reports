# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- TLS trust lists: before any request is sent, the verified certificate chain of the Firefly III server
  is compared (by SPKI SHA-256) with an internal blocklist, which refuses the connection, and a
  greylist, which only warns. Initial content from the eMudhra incident of October 2026: the eight
  intermediates with recoverable private keys (also their Sectigo cross-signed certificates) and
  `emSign ECC Root CA - G3` are blocked; the remaining emSign roots warn. Works on Python 3.11 to 3.13+
  and in the Windows executable; `--debug` logs every step
- `--trust-insecure-ssl` for `report` and `export`: turns TLS certificate verification (and the lists)
  off. Command line only (not in `firefly-reports.toml`, not an environment variable); a warning is
  printed on every run

### Security
- A connection whose chain contains a blocked key is refused before the Personal Access Token is sent
  (exit code 1). An unreadable chain connects with an explicit warning. Installed versions and
  executables keep the lists they shipped with: update to receive new entries

## [2.0.0] - 2026-10-23

Major release: uniform subcommands, a registry of report packages, a Beancount export and a
provisional library facade. Report content (PDF layout, Excel sheets) is unchanged by the
restructuring: with the same dependency versions the PDFs and workbooks are identical to the
pre-refactor code.

### Added
- Subcommands `firefly-reports report | export | init | demo`, `--version`, and
  `python -m firefly_reports`. Global options (`--url`, `--token`, `--lang`, `--debug`,
  `--debug-file`) work before or after the subcommand
- `firefly-reports demo`: every report from built-in sample data, no Firefly III needed
  (`--out`, `--lang`, `--year`, `--legacy-report`, `--no-pdf`, `--no-excel`)
- `firefly-reports export beancount`: export the transactions to a Beancount v3 ledger (Fava-ready)
  - expense and income accounts come from the Firefly **category** (`--classify-by account` keeps the
    counterpart accounts); transfers never touch the profit and loss accounts
  - two-pass mapping: `--scaffold` drafts `beancount_map.yaml` with the number of splits per category,
    `--append` adds the missing entries (keeps a `.bak` copy), `--overwrite` regenerates it after an
    explicit confirmation; the export stops without a mapping or with unlisted categories unless
    `--allow-unmapped`
  - layouts `--layout yearly` (default: `accounts.beancount` plus one `firefly-YYYY.beancount` per year,
    closed years stay byte-identical) and `single`; atomic writes; `--dry-run`, `--validate`
    (`bean-check`), `--init` (creates `main.beancount` with a Fava `language` setting plus empty
    `investments.beancount` and `prices.beancount`) and `--no-timestamp`
  - payee, tags, notes, bill, reference, dates and IBAN as native Beancount data; linked transactions share
    a `^firefly-link-<id>` link; the transaction flag is always `*`
  - investment accounts, foreign amounts via `@@`, explicit account-name collision errors, deterministic
    output, translated (en/it). See `docs/wiki/Beancount-Export.md`
- Provisional library facade (`firefly_reports.api`, names in `firefly_reports.__all__`): `connect`,
  `fetch_data`, `build_reports`, `write_reports`, `generate_reports`, `available_reports`, with immutable
  `Period`, `ReportOptions` and `ReportResult`. Typed (`py.typed`); not covered by semantic versioning
  until declared stable
- Error hierarchy `FireflyReportsError` (`ConfigurationError`, `FireflyAPIError`, `ReportError`,
  `LedgerError`) with messages translated at display time
- `FireflyClient.get_transactions()` accepts optional `start`/`end` and a type filter;
  `get_transaction_links()`
- New dependency `pyyaml`; optional extra `beancount` for `--validate`
- CI runs the `bean-check` tests; the coverage threshold is 90%
- `firefly-reports.toml`: an `[export]` section (`out`, `layout`, `classify_by`, `map`) gives
  defaults to `export beancount` (CLI > config > built-in default); `firefly-reports init` now
  writes every supported key as a commented template
- Keys in `firefly-reports.toml` that nothing reads (typos) produce a translated warning on
  stderr, with a suggestion, instead of being ignored silently; `.env.example` lists
  `FIREFLY_LANG` and `FIREFLY_LEGACY_REPORT`

### Changed
- Every on/off option can be switched off from the command line: `--no-legacy-report`, `--no-fetch-links`,
  `--no-all-tags`, `--no-reconciled-only` and `--show-transfers` override a `true` in `firefly-reports.toml`
  (before, a `true` in the config file or the environment could not be undone from the command line)
- A range given with `--start`/`--end` now wins over a `year` kept in the config file (before it was an
  error); `--year` together with a range is still an error
- Warnings and the failed-files summary (`[!] N files failed`, the missing `deductible_keywords` notice) go to
  stderr instead of stdout; results and progress lines stay on stdout
- `firefly-reports demo` warns on stderr that `--url` and `--token` are ignored
- `--url`/`--token` now follow the same precedence as every other setting: CLI > `firefly-reports.toml` >
  environment (`FIREFLY_URL`/`FIREFLY_TOKEN`, `.env`) > prompt. Before, the environment beat the config file
  for these two: a config file with `url`/`token` now overrides a stale variable in the shell
- Errors (configuration, credentials, dates, API) are printed to stderr; Firefly III request failures no
  longer end in a traceback. Messages follow `--lang`
- Exit codes: `3` when the run finished but some files could not be written (was `0`), `2` for a bare
  `firefly-reports` without a configured year (prints the help; was `1`), `130` on Ctrl-C
- The PDFs are written in registry order, so the order of the console `OK` lines differs; the set of
  files is unchanged
- `demo` writes the same file names as `report` (`yoy_<prev>_vs_<year>.pdf`,
  `firefly_reports_<period>.xlsx`) and produces the `audit_log` only with `--legacy-report`
- The matplotlib backend is no longer switched at import time (charts use the object-oriented API) and
  the translation catalog is context-local instead of a module global

### Deprecated (removed in 3.0.0)
- Running reports without a subcommand (`firefly-reports --year 2025 ...`): it still works and prints the
  equivalent `report` command on stderr (the token is masked)
- The hidden root-level `--out`, `--start`, `--end` placed before a subcommand
- `python -m firefly_reports.main` and `python -m firefly_reports.demo`

### Removed
- Internal modules `data_processor`, `pdf_exporter`, `excel_exporter`, `chart_engine` and `config`
  (replaced by `firefly_reports.reports`, `firefly_reports.render` and `firefly_reports.cli`). The command
  line is the stable interface; these modules were never public
- The legacy workbook entry points `render_all_xlsx` and `render_all_xlsx_extended` (unused)

## [1.0.2] - 2026-08-10

### Fixed
- Windows executable crashed with `UnicodeEncodeError` on consoles using legacy
  codepages (e.g. cp1252) when printing help or messages containing non-ASCII
  characters (`€`, `—`): console output now replaces unencodable characters
  instead of crashing. The 1.0.1 PyPI release is affected by this bug on
  cp1252 Windows consoles; 1.0.2 supersedes it.
- Windows executable was built without the translation files (`--collect-data`
  silently collects nothing when the package is not installed), crashing with
  `FileNotFoundError` on any run past `--help`: the bundle now includes
  `translations/*.toml` via an explicit `--add-data`, and the CI smoke test
  probes translation loading instead of only `--help`
- `--help` description still said "25 reports" (now 26) and showed the
  module-invocation usage line; it now shows the `firefly-reports` command

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
