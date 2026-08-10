# Configuration

## Credential chain

Credentials are resolved in this order (first non-empty value wins):

```
--token CLI flag
  └─► FIREFLY_TOKEN environment variable
        └─► token key in firefly-reports.toml
              └─► token key in .env file
                    └─► interactive prompt (if terminal is attached)
```

The same chain applies to `--url` / `FIREFLY_URL`.

## Config file wizard

Run the interactive wizard to generate `firefly-reports.toml`:

```bash
firefly-reports init
```

The wizard prompts for URL, token, owner name, currency, language, output directory, and tags. It writes `firefly-reports.toml` in the current directory. If the file will contain a token and `firefly-reports.toml` is not in `.gitignore`, the wizard prints a warning.

> **Security:** Never commit `firefly-reports.toml` if it contains a token. Add it to `.gitignore`.

## TOML config file reference

All keys are optional. Keys set on the command line always override the config file.

```toml
# firefly-reports.toml

url      = "https://firefly.example.com"   # Firefly III base URL
token    = ""                              # PAT — omit to be prompted at runtime
owner    = "Your Name"                     # shown in report headers
currency = "€"                             # currency symbol
lang     = "en"                            # output language: "en" or "it"
legacy_report = false                      # use legacy PDF styles (omits strategic reports; generates the audit_log PDF instead of summary)
out      = "./output"                      # output directory
tags     = ["consulting", "travel"]        # tags for the Tagged Report (report 8)

[reports]
historical_years = 3          # years for Historical Growth report: 3 or 5
fetch_links      = false      # deep-fetch linked transactions for Linkage Audit
link_delay       = 0.2        # seconds between requests when fetch_links is true
all_tags_report  = false      # generate the All Tags Ledger report

[tax]
deductible_keywords = ["studio", "software", "formazione", "inps"]
# Expense categories containing any of these keywords (case-insensitive)
# are marked as deductible in the Tax Summary report.
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `FIREFLY_URL` | Firefly III base URL |
| `FIREFLY_TOKEN` | Personal Access Token |
| `FIREFLY_LANG` | Output language (`en` or `it`) |
| `FIREFLY_LEGACY_REPORT` | Set to `true` to use legacy PDF styles |

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
# edit .env with your URL and token
```

## All CLI flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--url URL` | string | — | Firefly III base URL |
| `--token TOKEN` | string | — | Personal Access Token |
| `--year YYYY` | int | — | Full calendar year mode. Unlocks year-only reports (YoY comparison, multi-year historical, liquidity forecast). Mutually exclusive with `--start`/`--end` |
| `--start DATE` | YYYY-MM-DD | — | Period start date (date-range mode; year-only reports are skipped) |
| `--end DATE` | YYYY-MM-DD | — | Period end date (date-range mode) |
| `--owner NAME` | string | `""` | Owner name in report headers |
| `--currency SYM` | string | `€` | Currency symbol |
| `--out DIR` | path | `./output` | Output directory |
| `--lang LANG` | `en`\|`it` | `en` | Output language |
| `--years N` | `3`\|`5` | `3` | Years for Historical Growth report |
| `--tags TAG1,TAG2` | string | `""` | Tags for the Tagged Report |
| `--fetch-links` | flag | off | Deep-fetch linked transactions |
| `--link-delay SEC` | float | `0.2` | Seconds between requests when `--fetch-links` is on |
| `--all-tags` | flag | off | Generate the All Tags Ledger |
| `--legacy-report` | flag | off | Use legacy PDF styles (skips strategic reports; generates the `audit_log` PDF instead of `summary`) |
| `--no-pdf` | flag | off | Skip all PDF generation |
| `--no-excel` | flag | off | Skip Excel generation |
| `--accounts-include ID1,ID2` | string | — | Only these asset account IDs |
| `--accounts-exclude ID1,ID2` | string | — | Exclude these asset account IDs |
| `--categories-include C1,C2` | string | — | Only these categories (case-insensitive) |
| `--categories-exclude C1,C2` | string | — | Exclude these categories (case-insensitive) |
| `--hide-transfers` | flag | off | Drop transfer transactions from all reports |
| `--reconciled-only` | flag | off | Only reconciled transactions |
| `--fiscal-year-start MM-DD` | string | `01-01` | Fiscal year start (year mode only) |
| `--debug` | flag | off | Write debug log to `<out>/debug_<timestamp>.log` |
| `--debug-file PATH` | path | auto | Custom debug log path |
| `init` | subcommand | — | Run the config file wizard |
