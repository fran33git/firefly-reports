# Configuration

This page is the reference for users on how firefly-reports is configured: the order in which command-line
flags, the `firefly-reports.toml` file and environment variables are combined, every supported config key,
the environment variables, what `firefly-reports init` writes, all the flags of `report` and `demo`, and the
exit codes. The options of `export beancount` are in [[Beancount-Export|Beancount Export]].

## Precedence

For **every** setting, including the Firefly III URL and token, the first value found wins in this order:

1. the command-line flag;
2. `firefly-reports.toml` in the current directory;
3. the environment (`FIREFLY_URL`, `FIREFLY_TOKEN`, `FIREFLY_LANG`, `FIREFLY_LEGACY_REPORT`), which a
   `.env` file in the current directory can fill in;
4. the built-in default. For the token only, the last resort is an interactive prompt (hidden input),
   when the terminal is interactive.

A `.env` file never overrides a variable that is already set in the shell.

> **Changed in 2.0:** before 2.0 the environment beat the config file for `url` and `token`. Now a
> `url`/`token` in `firefly-reports.toml` wins over a `FIREFLY_URL`/`FIREFLY_TOKEN` left in the shell.

Settings that are on/off switches (`legacy_report`, `reconciled_only`, `fetch_links`, `all_tags_report`)
are enabled if **any** source enables them: there is no flag to switch them off from the command line.
`show_transfers = false` in the config file and `--hide-transfers` both drop transfers.

## Config file

`firefly-reports` reads `./firefly-reports.toml` from the directory it is started in. A missing file is
fine; a malformed one stops the run with `Config error: firefly-reports.toml is malformed — <details>` and
exit code `1`.

All keys are optional:

```toml
# firefly-reports.toml
url           = "https://firefly.example.com"  # Firefly III base URL
token         = ""                             # Personal Access Token; omit to use the environment or the prompt
owner         = "Your Name"                    # shown in report headers
currency      = "€"                            # currency symbol
lang          = "en"                           # output language: "en" or "it"
legacy_report = false                          # legacy PDF styles (see Reports Reference)
out           = "./output"                     # output directory of `report` only
tags          = ["consulting", "travel"]       # tags for the Tagged Report
year          = 2025                           # default for --year

[reports]
fetch_links      = false   # fetch the details of linked transactions (slower)
link_delay       = 0.2     # seconds between those requests
all_tags_report  = false   # generate the All Tags Ledger
historical_years = 3       # years in Historical Growth: 3 or 5

[filters]
accounts_include   = []        # only these asset account IDs
accounts_exclude   = []        # exclude these asset account IDs
categories_include = []        # only these categories (case-insensitive)
categories_exclude = []        # exclude these categories (case-insensitive)
show_transfers     = true      # false drops transfers from all reports
reconciled_only    = false     # only reconciled transactions
fiscal_year_start  = "01-01"   # MM-DD, year mode only

[tax]
deductible_keywords = ["studio", "software"]   # see below

[export]                       # defaults for `firefly-reports export beancount`
out         = "./ledger"       # output directory of the ledger
layout      = "yearly"         # yearly | single
classify_by = "category"       # category | account
map         = "beancount_map.yaml"
```

> **Security:** never commit a `firefly-reports.toml` that contains a token. Add it to `.gitignore`.

### Key reference

| Key | Flag | Default | Notes |
|---|---|---|---|
| `url` | `--url` | none (required) | Must include the scheme, e.g. `https://` |
| `token` | `--token` | prompt | Also `FIREFLY_TOKEN` |
| `owner` | `--owner` | empty | |
| `currency` | `--currency` | `€` | |
| `lang` | `--lang` | `en` | Also `FIREFLY_LANG`. Applies to every command, including `export` and `demo` |
| `legacy_report` | `--legacy-report` | `false` | Also `FIREFLY_LEGACY_REPORT` (`true` or `1`) |
| `out` | `--out` | `./output` | Used by `report` only; the ledger uses `[export] out`, and `demo` uses `--out` or `./output` |
| `tags` | `--tags` | none | Without tags the Tagged Report is skipped |
| `year` | `--year` | none | While set, `--start/--end` on the command line are rejected (`use either --year or --start/--end, not both`): remove it to run a custom range. Not read by `demo` |
| `[reports] fetch_links` | `--fetch-links` | `false` | |
| `[reports] link_delay` | `--link-delay` | `0.2` | Seconds |
| `[reports] all_tags_report` | `--all-tags` | `false` | |
| `[reports] historical_years` | `--years` | `3` | `3` or `5` |
| `[filters] accounts_include`, `accounts_exclude` | `--accounts-include`, `--accounts-exclude` | none | Asset account IDs; on the command line comma-separated |
| `[filters] categories_include`, `categories_exclude` | `--categories-include`, `--categories-exclude` | none | Category names, case-insensitive |
| `[filters] show_transfers` | `--hide-transfers` | `true` | |
| `[filters] reconciled_only` | `--reconciled-only` | `false` | |
| `[filters] fiscal_year_start` | `--fiscal-year-start` | `01-01` | `MM-DD`, year mode only |
| `[tax] deductible_keywords` | none | none | Expense categories containing one of these words (case-insensitive) are deductible in the Tax Summary. Without it, a warning is printed and every expense is non-deductible |
| `[export] out` | `export --out` | `ledger` | |
| `[export] layout` | `export --layout` | `yearly` | `yearly` or `single` |
| `[export] classify_by` | `export --classify-by` | `category` | `category` or `account`; overrides `classify_by` in the mapping file |
| `[export] map` | `export --map` | `./beancount_map.yaml` if present | |

An invalid `[export] layout` or `classify_by` value stops the command with
`Error: Config error: export.layout must be one of yearly, single (got '...').` (exit code `1`).

### Unknown keys

A key that nothing reads, typically a typo, is not an error: it is ignored and a warning is printed on
stderr, in the output language, with a suggestion when a known key is close:

```text
Warning: unknown key 'export.layot' in firefly-reports.toml is ignored. Did you mean 'export.layout'?
Warning: unknown key 'filtres' in firefly-reports.toml is ignored. Did you mean 'filters'?
```

## Environment variables

| Variable | Setting |
|---|---|
| `FIREFLY_URL` | Firefly III base URL |
| `FIREFLY_TOKEN` | Personal Access Token |
| `FIREFLY_LANG` | Output language, `en` or `it` |
| `FIREFLY_LEGACY_REPORT` | `true` or `1` enables the legacy PDF styles of `report` |

Copy `.env.example` to `.env` (it is in `.gitignore`) and fill in your values:

```bash
cp .env.example .env
```

## `firefly-reports init`

`init` creates `./firefly-reports.toml` interactively. It asks, with defaults in brackets:

- the URL (`https://firefly.example.com`), the token (hidden input; leave it blank to be asked at
  run time), the owner name, the currency symbol (`€`), the language (`en` or `it`), whether to use the
  legacy report styles, the output directory (`./output`) and the tags (comma-separated).

It writes those values (a blank token becomes a commented `# token = ""` line), followed by every other
supported key commented out, so the file documents what can be set: `year`, the `[reports]`,
`[filters]` and `[tax]` sections and the `[export]` section with their defaults.

If the file already exists, `init` asks before overwriting it. A file that contains a token is created
readable by its owner only (mode `0600`), and `init` warns if `firefly-reports.toml` is not listed in
`.gitignore`.

## `report` flags

| Flag | Default | Description |
|---|---|---|
| `--url URL` | | Firefly III base URL |
| `--token TOKEN` | | Personal Access Token |
| `--year YYYY` | | Full (fiscal) year mode: every report, including the year-only ones (Year-over-Year, Historical Growth, Liquidity Forecast). Mutually exclusive with `--start/--end` |
| `--start YYYY-MM-DD`, `--end YYYY-MM-DD` | | Custom range: the year-only reports are skipped |
| `--owner NAME` | empty | Owner name in report headers |
| `--currency SYM` | `€` | Currency symbol |
| `--out DIR` | `./output` | Output directory |
| `--lang en\|it` | `en` | Output language |
| `--years 3\|5` | `3` | Years in Historical Growth |
| `--tags TAG1,TAG2` | | Tags for the Tagged Report |
| `--fetch-links` | off | Fetch full details of linked transactions (slower) |
| `--link-delay SEC` | `0.2` | Seconds between requests when fetching linked transactions |
| `--all-tags` | off | Generate the All Tags Ledger |
| `--legacy-report` | off | Legacy PDF styles (see [[Reports-Reference\|Reports Reference]]) |
| `--no-pdf`, `--no-excel` | off | Skip the PDFs or the workbook |
| `--accounts-include ID1,ID2`, `--accounts-exclude ID1,ID2` | | Asset account filters |
| `--categories-include C1,C2`, `--categories-exclude C1,C2` | | Category filters (case-insensitive) |
| `--hide-transfers` | off | Drop transfers from all reports |
| `--reconciled-only` | off | Only reconciled transactions |
| `--trust-insecure-ssl` | off | Turns TLS certificate verification **and** the CA lists off (self-signed, expired and blocklisted certificates are all accepted); your token can be intercepted. Also available on `export beancount`. Command line only: it is not read from `firefly-reports.toml` or the environment, and a warning is printed on every run |
| `--fiscal-year-start MM-DD` | `01-01` | Fiscal year start (year mode only) |
| `--debug` | off | Write a debug log, by default `<out>/debug_<timestamp>.log` |
| `--debug-file PATH` | | Path of the debug log |

## `demo` flags

`demo` takes `--out DIR` (default `./output`), `--year YYYY` (default `2025`), `--legacy-report`,
`--no-pdf`, `--no-excel` and the global `--lang`, `--debug` and `--debug-file`. It needs no URL or token
and uses fixed sample settings (owner, currency, tags and tax keywords); from the config file it reads
only `lang`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Error: configuration, credentials, Firefly III API, or ledger export. The message is printed on stderr |
| `2` | Usage error (invalid flags), or `firefly-reports` run without a command and without a `year` in the config file (the help is printed) |
| `3` | The run finished but some output files could not be written (they are listed; rerun with `--debug` for details) |
| `130` | Interrupted with Ctrl-C |

`export beancount --validate` also returns `2` when `bean-check` is not installed; see
[[Beancount-Export|Beancount Export]].
