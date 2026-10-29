# firefly-reports

Generate **26 financial reports** plus two dashboards (PDF + Excel) directly from your [Firefly III](https://www.firefly-iii.org/) instance, and export your transactions to a Beancount ledger. Designed for individuals, freelancers and small businesses who want a complete annual financial overview without manual data export. This wiki is the user and developer documentation: start with the User Guide column below.

[![CI](https://github.com/fran33git/firefly-reports/actions/workflows/ci.yml/badge.svg)](https://github.com/fran33git/firefly-reports/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/fran33git/firefly-reports/blob/main/LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)

## In 2 commands

```bash
pip install firefly-iii-reports
firefly-reports report --url https://firefly.example.com --year 2025
```

No Firefly III instance? Generate every report from built-in sample data:

```bash
firefly-reports demo --out ./output
```

## Navigation

| User Guide | Developer Guide |
|-----------|----------------|
| [[Installation]] — prerequisites, install, first run | [[Architecture]] — how the pipeline works<br>[[Ledger-Architecture\|Ledger Architecture]] — Beancount export internals<br>[[Library-API\|Library API]] — the provisional Python facade |
| [[Configuration]] — all options, TOML config file | [[Adding-a-New-Report\|Adding a New Report]] — extend the tool |
| [[Reports-Reference\|Reports Reference]] — all 26 reports and the two dashboards | [[Testing]] — run and write tests |
| [[Beancount-Export\|Beancount Export]] — ledger/Fava export<br>[[Troubleshooting]] — common errors and debug log | [[Contributing]] — code style and PR process |

## Output

A run produces one PDF per generated report (27 for a full year with `--tags` and `--all-tags`, as in the
demo) and one Excel workbook:

```text
output/
├── cash_flow_2025-01-01__2025-12-31.pdf
├── income_expense_2025-01-01__2025-12-31.pdf
├── transaction_register_2025-01-01__2025-12-31.pdf
├── ...
└── firefly_reports_2025-01-01__2025-12-31.xlsx
```

## License

[GPL v3](https://github.com/fran33git/firefly-reports/blob/main/LICENSE)
