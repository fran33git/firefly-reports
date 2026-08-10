# Installation & Quick Start

## Prerequisites

- Python 3.11 or later
- A running [Firefly III](https://www.firefly-iii.org/) instance (v6.x recommended)
- A Firefly III **Personal Access Token** (PAT): Profile → OAuth → Personal Access Tokens → Create
- `pip`

## Install

From PyPI (recommended):

```bash
pip install firefly-iii-reports
```

This installs the `firefly-reports` command. Alternatively, install from source:

```bash
git clone https://github.com/fran33git/firefly-reports.git
cd firefly-reports
pip install -r firefly_reports/requirements.txt
```

## First run

With the PyPI install, use the `firefly-reports` command:

```bash
firefly-reports \
  --url https://your-firefly-instance.example.com \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --owner "Your Name" \
  --out ./output
```

From a source checkout, run the same command as `python -m firefly_reports.main ...` from the repo root.

You will be prompted for your Personal Access Token if it is not set via `--token` or environment variables. See [[Configuration]] for the full credential chain.

The tool prints a progress summary as it runs:

```
[*] Connecting to https://your-firefly-instance.example.com
[*] Downloading data...
    -> 847 transactions (2025-01-01 -> 2025-12-31)
    -> 847 transactions previous year (2024-01-01 -> 2024-12-31)
    -> 4 asset accounts
    -> 2 liabilities
    -> Account statements: 4 accounts
    -> 5 budgets
    -> 12 bills/subscriptions
    -> 3 savings goals

[*] Summary 2025-01-01 -> 2025-12-31:
   Income:       € 48,500.00
   Expenses:     € 31,200.00
   Net:          € 17,300.00
   Transactions: 634
   Savings rate: 35.7%  |  Runway: 8.4 months

[*] Generating PDF reports...
    OK  cash_flow_2025-01-01__2025-12-31.pdf
    ...
[*] All reports written to /path/to/output
```

## Demo mode (no Firefly III required)

Run the demo to see all reports generated from built-in mock data (from the repo root of a source checkout):

```bash
python -m firefly_reports.demo --out ./output
```

This uses realistic English freelancer mock data and produces all 26 PDF reports plus the Excel workbook (full year via `--year 2025`, override with `--year YYYY`). Useful for evaluating the tool before connecting it to a live instance.

## Expected output

After a successful run the output directory contains:

```
output/
├── *.pdf          — one file per report (up to 26 PDFs depending on flags)
└── firefly_reports_<start>__<end>.xlsx
```

See [[Reports-Reference|Reports Reference]] for the full list of output files and what each report contains.

## Developer install

For contributors who want to run tests and linters:

```bash
cd firefly-reports
pip install -e ".[dev]"
pre-commit install
```

See [[Testing]] and [[Contributing]] for next steps.
