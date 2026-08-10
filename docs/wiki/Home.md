# firefly-reports

[![CI](https://github.com/fran33git/firefly-reports/actions/workflows/ci.yml/badge.svg)](https://github.com/fran33git/firefly-reports/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/fran33git/firefly-reports/blob/main/LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)

Generate **26 financial reports** (PDF + Excel) directly from your [Firefly III](https://www.firefly-iii.org/) instance. Designed for freelancers and small businesses who want a complete annual financial overview without manual data export.

## In 2 commands

```bash
pip install firefly-iii-reports
firefly-reports --url https://firefly.example.com --start 2025-01-01 --end 2025-12-31
```

No Firefly III instance? Run the demo with built-in mock data (from a source checkout):

```bash
python -m firefly_reports.demo
```

## Navigation

| User Guide | Developer Guide |
|-----------|----------------|
| [[Installation]] — prerequisites, install, first run | [[Architecture]] — how the pipeline works |
| [[Configuration]] — all options, TOML config file | [[Adding-a-New-Report\|Adding a New Report]] — extend the tool |
| [[Reports-Reference\|Reports Reference]] — all 26 reports | [[Testing]] — run and write tests |
| [[Troubleshooting]] — common errors and debug log | [[Contributing]] — code style and PR process |

## Output

A typical run produces files in the output directory:

```
output/
├── cash_flow_2025-01-01__2025-12-31.pdf
├── income_expense_2025-01-01__2025-12-31.pdf
├── transaction_register_2025-01-01__2025-12-31.pdf
├── ...                                          (22 more PDFs)
└── firefly_reports_2025-01-01__2025-12-31.xlsx
```

## License

[GPL v3](https://github.com/fran33git/firefly-reports/blob/main/LICENSE)
