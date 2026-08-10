# firefly-reports

[![CI](https://github.com/fran33git/firefly-reports/actions/workflows/ci.yml/badge.svg)](https://github.com/fran33git/firefly-reports/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/firefly-reports)](https://pypi.org/project/firefly-reports/)
[![CodeQL](https://github.com/fran33git/firefly-reports/actions/workflows/codeql.yml/badge.svg)](https://github.com/fran33git/firefly-reports/actions/workflows/codeql.yml)
[![Coverage](docs/coverage_badge.svg)](https://github.com/fran33git/firefly-reports/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)

Generate **26 financial reports** (PDF + Excel) from a [Firefly III](https://www.firefly-iii.org/) instance. Designed for individuals, freelancers and small businesses who want a complete annual financial overview.

## Quick start

```bash
pip install firefly-reports

firefly-reports \
  --url https://your-firefly-instance.example.com \
  --year 2025 \
  --owner "Your Name" --out ./output
```

To run from source instead, clone the repo and use `python -m firefly_reports.main` in place of `firefly-reports` (dependencies: `pip install -r firefly_reports/requirements.txt`).

Use `--year YYYY` for a full calendar year (all reports), or `--start`/`--end` for a custom date range — in date-range mode the year-only reports (YoY, Historical Growth, Liquidity Forecast) are skipped.

The token can be provided via `--token`, the `FIREFLY_TOKEN` environment variable, a `.env` file, a `firefly-reports.toml` config file, or an interactive prompt.

## Reports generated

### Standard (always generated)

| # | Report | Description |
|---|--------|-------------|
| 1 | Cash Flow Statement | Income/expense by category with monthly breakdown |
| 2 | Income vs Expense | Summary with savings rate and budget breakdown |
| 3 | Transaction Register | Chronological list with running balance |
| 4 | Net Worth | Assets grouped by account type |
| 5 | Account Statements | Per-account transaction statement |
| 6 | Tax Summary | Cash-basis income and deductible expenses |
| 7 | Expense Trend | Category × month expense matrix |
| 8 | Tagged Report | Transactions filtered by tag (`--tags`) |
| 9 | Budget vs Actual | Planned vs real spend with pace status |
| 10 | Bills & Subscriptions | Recurring payments with status |
| 11 | Savings Goals | Piggy bank progress |
| 12 | Liabilities | Debt summary with period movement |
| 13 | KPI Scorecard | Burn rate, cash runway, savings rate, HHI |
| 14 | Year-over-Year | Income and expense comparison vs prior year (`--year` mode only) |
| 15 | Cumulative Cash Flow | Monthly cumulative series |
| 16 | Income by Client | Income breakdown per client (revenue source) |

### Strategic (non-legacy mode)

| # | Report | Description |
|---|--------|-------------|
| 18 | Budget Performance Forecast | Month-end projection from current velocity |
| 19 | Category Ledger | Transactions grouped by category |
| 20 | Payee Ledger | Transactions grouped by payee |
| 21 | Linkage & Reimbursement Report | Linked pairs with link type and linked-amount % |
| 22 | All Tags Ledger | Transactions grouped by tag (`--all-tags`) |
| 23 | Historical Growth | Multi-year income/expense comparison (`--years`, `--year` mode only) |
| 24 | Liquidity Forecast | 6-month projected balance (`--year` mode only) |
| 25 | General Journal | Chronological double-entry register with protocol numbers and daily totals (Libro Giornale) |
| 26 | Summary | Firefly instance info (version, API, OS, PHP, user), global counts and period statistics |

> **Report 17 — Transaction Audit Log** (`audit_log_<period>.pdf`) is now generated only when `--legacy-report` is active. The Summary report takes its slot in standard mode.

## Demo (no Firefly III required)

```bash
python -m firefly_reports.demo --out ./output --year 2025 --lang en
```

## Config file

```bash
firefly-reports init     # interactive wizard — creates firefly-reports.toml
```

## Documentation

Full documentation is on the [GitHub Wiki](https://github.com/fran33git/firefly-reports/wiki):

- [Installation & Quick Start](https://github.com/fran33git/firefly-reports/wiki/Installation)
- [Configuration](https://github.com/fran33git/firefly-reports/wiki/Configuration) — all CLI flags, TOML keys, env vars
- [Reports Reference](https://github.com/fran33git/firefly-reports/wiki/Reports-Reference) — all 26 reports
- [Troubleshooting](https://github.com/fran33git/firefly-reports/wiki/Troubleshooting)
- [Architecture](https://github.com/fran33git/firefly-reports/wiki/Architecture)

## Development

```bash
pip install -e ".[dev]"
pre-commit install
pytest tests/ -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Developer Guide](https://github.com/fran33git/firefly-reports/wiki/Contributing) on the wiki.

## License

GPL v3 — see [LICENSE](LICENSE).
