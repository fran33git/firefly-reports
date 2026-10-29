# Installation & Quick Start

This page is for users: it shows how to install firefly-reports, try it on built-in sample data without a
Firefly III instance, and produce the reports from your own instance. Configuration details are in
[[Configuration]]; the list of reports is in [[Reports-Reference|Reports Reference]].

## Prerequisites

- Python 3.11 or later
- For your own data: a running [Firefly III](https://www.firefly-iii.org/) instance (v6.x recommended) and
  a Firefly III **Personal Access Token** (Profile -> OAuth -> Personal Access Tokens -> Create)

## Install

From PyPI (recommended):

```bash
pip install firefly-iii-reports
# optional, only for `export beancount --validate`:
pip install "firefly-iii-reports[beancount]"
```

The distribution is called `firefly-iii-reports`; it installs the `firefly-reports` command. Check it:

```bash
firefly-reports --version
```

From a source checkout, install the pinned dependencies and run the package as a module; every
`firefly-reports ...` command on this wiki then becomes `python -m firefly_reports ...`:

```bash
git clone https://github.com/fran33git/firefly-reports.git
cd firefly-reports
pip install -r firefly_reports/requirements.txt
python -m firefly_reports --version
```

## Commands

| Command | Does |
|---|---|
| `firefly-reports report` | Generates the PDF reports and the Excel workbook from a Firefly III instance |
| `firefly-reports export beancount` | Exports the transactions to a Beancount ledger (see [[Beancount-Export\|Beancount Export]]) |
| `firefly-reports init` | Creates `./firefly-reports.toml` interactively (see [[Configuration]]) |
| `firefly-reports demo` | Generates every report from built-in sample data, no Firefly III needed |

`firefly-reports --help` lists them, and `firefly-reports <command> --help` shows the options of one
command. The global options `--url`, `--token`, `--lang`, `--debug` and `--debug-file` work before or
after the command name.

## Try it without Firefly III

```bash
firefly-reports demo --out ./output
```

The demo runs the real report pipeline on built-in sample data (a freelancer's year, 2025 by default)
and writes 27 PDFs plus the Excel workbook. Options: `--year YYYY`, `--lang en|it`, `--legacy-report`,
`--no-pdf`, `--no-excel`. Example output (abridged):

```text
[*] Demo mode: built-in sample data (no Firefly III needed)
[*] Downloading data...
    -> 30 transactions (2025-01-01 -> 2025-12-31)
    -> 9 transactions previous year (2024-01-01 -> 2024-12-31)
    -> 4 asset accounts
    ...
[*] Summary 2025-01-01 -> 2025-12-31:
   Income:       €    17,150.00
   Expenses:     €     5,598.08
   Net:          €    11,551.92
   Transactions: 30
   Savings rate: 67.4%  |  Runway: 18.5 months

[*] Generating PDF reports...
    OK  cash_flow_2025-01-01__2025-12-31.pdf
    ...
[*] Generating Excel...
    OK  firefly_reports_2025-01-01__2025-12-31.xlsx

[*] All reports written to /path/to/output
```

## First run against your instance

```bash
firefly-reports report \
  --url https://your-firefly-instance.example.com \
  --year 2025 \
  --owner "Your Name" \
  --out ./output
```

- `--year YYYY` produces every report for a full calendar year. `--start YYYY-MM-DD --end YYYY-MM-DD`
  produces a custom range instead; in range mode the year-only reports (Year-over-Year, Historical
  Growth, Liquidity Forecast) are skipped. The two forms cannot be combined.
- If no token is given (`--token`, `firefly-reports.toml`, `FIREFLY_TOKEN` or `.env`), you are asked
  for it when the terminal is interactive. See [[Configuration]] for the full precedence.

The run prints the same kind of progress as the demo, starting with `[*] Connecting to <url>`. When it
ends with `[*] All reports written to ...` the exit code is `0`; if some files could not be written they
are listed and the exit code is `3`.

## Output

```text
output/
├── cash_flow_2025-01-01__2025-12-31.pdf
├── ...                                    one PDF per generated report
└── firefly_reports_2025-01-01__2025-12-31.xlsx
```

Which PDFs appear depends on the mode and the flags; see [[Reports-Reference|Reports Reference]].

## Upgrading from 1.x

- Reports now have their own command: `firefly-reports report --year 2025 ...`. The 1.x form without a
  command (`firefly-reports --year 2025 ...`) still works in 2.x but prints a deprecation warning with the
  equivalent command (the token is masked); it will be removed in 3.0.
- `python -m firefly_reports.main` and `python -m firefly_reports.demo` are deprecated as well (removed
  in 3.0): use `python -m firefly_reports report ...` and `firefly-reports demo`.
- The order of precedence of `url` and `token` changed: see [[Configuration]].

## Developer install

To run the tests and the linters, see [[Contributing]] (development venv and local gate) and [[Testing]].
