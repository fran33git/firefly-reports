# Reports Reference

Reports are generated either for a full calendar year (`--year YYYY`) or for a custom period (`--start`/`--end`); year-only reports (14, 23, 24) require `--year` mode. The `{period}` placeholder in filenames expands to `<start>__<end>` (e.g. `2025-01-01__2025-12-31`).

## Standard reports (always generated)

| # | Name | Description | PDF filename |
|---|------|-------------|--------------|
| 1 | Cash Flow Statement | Income and expenses by category, with monthly in/out/net breakdown | `cash_flow_{period}.pdf` |
| 2 | Income vs Expense | Income and expense by category with percentage share and savings rate | `income_expense_{period}.pdf` |
| 3 | Transaction Register | Chronological list of all transactions with running balance, grouped by transaction group, with Firefly IDs, split lines and notes | `transaction_register_{period}.pdf` |
| 4 | Net Worth | Asset accounts grouped by type (current account, savings, credit card, etc.) with subtotals | `net_worth_{period}.pdf` |
| 5 | Account Statements | Per-account statement with opening/closing balance and running balance for each transaction | `account_statements_{period}.pdf` |
| 6 | Tax Summary | Cash-basis income by category and client, deductible vs non-deductible expenses (configured via `[tax]` in TOML) | `tax_summary_{year}.pdf` |
| 7 | Expense Trend | Category × month matrix showing spending evolution over the period | `expense_trend_{period}.pdf` |
| 8 | Tagged Report | All transactions matching the specified tags, with running balance and category breakdown | `tagged_{tags}_{period}.pdf` |
| 9 | Budget vs Actual | Budget planned amount vs real spending, with pace status (AHEAD / ON TRACK / UNDER) | `budget_vs_actual_{period}.pdf` |
| 10 | Bills & Subscriptions | Recurring bills with expected amount, payment status, and next expected date | `bills_{period}.pdf` |
| 11 | Savings Goals | Piggy bank progress: current vs target, monthly contribution needed, months remaining | `savings_goals_{period}.pdf` |
| 12 | Liabilities | Debt accounts with balance, interest rate, and period payments | `liabilities_{period}.pdf` |
| 13 | KPI Scorecard | Key financial indicators: burn rate, cash runway, savings rate, HHI income concentration | `kpi_scorecard_{period}.pdf` |
| 14 | Year-over-Year | Income and expense comparison vs the same period one year earlier, category by category | `yoy_{prev_year}_vs_{year}.pdf` |
| 15 | Cumulative Cash Flow | Monthly net cash flow and running cumulative total, with peak and low months | `cumulative_cashflow_{period}.pdf` |
| 16 | Income by Client | Income breakdown per client (revenue source) with percentage share | `income_concentration_{period}.pdf` |

Two dashboard PDFs are also generated alongside the standard reports:

| Name | Description | PDF filename |
|------|-------------|--------------|
| Income & Expense Dashboard | KPI cards (totals and savings rate), monthly income-vs-expense chart, spending-by-category donut, top income sources | `dashboard_income_expense_{period}.pdf` |
| KPI Trend Dashboard | KPI cards (savings rate, burn rate, cash runway, net worth), monthly net cash flow trend, cumulative net cash flow | `dashboard_kpi_trend_{period}.pdf` |

## Strategic reports (non-legacy mode)

Generated unless `--legacy-report` is set. Some require additional flags.

| # | Name | Description | Required flag | PDF filename |
|---|------|-------------|---------------|--------------|
| 18 | Budget Performance Forecast | Month-end spending projection based on current daily velocity | — | `budget_forecast_{period}.pdf` |
| 19 | Category Ledger | All transactions grouped alphabetically by category, with category subtotals | — | `ledger_category_{period}.pdf` |
| 20 | Payee Ledger | All transactions grouped alphabetically by payee, with payee subtotals | — | `ledger_payee_{period}.pdf` |
| 21 | Linkage & Reimbursement Report | Linked transaction pairs with link type, linked-amount percentage and completion status | `--fetch-links` enriches data | `audit_linkage_{period}.pdf` |
| 22 | All Tags Ledger | Every transaction grouped by its tags, with tag totals | `--all-tags` | `ledger_all_tags_{period}.pdf` |
| 23 | Historical Growth | Year-over-year income, expense and net comparison across multiple years | `--years 3` or `--years 5` | `historical_growth_{period}.pdf` |
| 24 | Liquidity Forecast | 6-month projected balance based on average income, variable expenses, and scheduled bills | — | `liquidity_forecast_{period}.pdf` |
| 25 | General Journal | Chronological double-entry register (Libro Giornale) with runtime protocol numbers, Debit/Credit accounts, and daily totals | — | `journal_{period}.pdf` |
| 26 | Summary | Firefly instance info, global counts and period statistics (see notes below) | — | `summary_{period}.pdf` |

> **Report 17 — Transaction Audit Log** (`audit_log_{period}.pdf`) is now generated **only when `--legacy-report` is set**. In standard mode the Summary report takes its slot.

## Excel workbook

One workbook is always generated alongside the PDFs:

**`firefly_reports_{period}.xlsx`** — 16 core report sheets (reports 1–16) plus a **Summary** sheet (always present, in both standard and legacy mode). **Report 5 — Account Statements** contributes one sheet per asset account, so the total sheet count varies with the number of accounts.

## Notes on specific reports

**Report 6 — Tax Summary:** Requires `[tax] deductible_keywords` in `firefly-reports.toml` to identify deductible expense categories. Without it, all expenses appear as non-deductible and a warning is printed.

**Report 8 — Tagged Report:** Only generated when `--tags` is provided. The filename slug is derived from the tag list (truncated to 30 characters).

**Report 21 — Linkage & Reimbursement Report:** Generated whenever linked transactions exist in the period, even without `--fetch-links`. The `--fetch-links` flag deep-fetches the details of linked transactions that fall outside the current period, which improves completeness for partial-period reimbursements. Use `--link-delay` to control request pacing.

**Report 23 — Historical Growth:** Fetches annual totals for the selected year plus the 2 or 4 preceding years (`--years 3|5`). This requires additional API calls (2 calls per year: income totals + top categories).

**Report 26 — Summary:** Three blocks of content:

- **Instance info** — from `GET /api/v1/about` and `GET /api/v1/about/user`: Firefly version, API version, OS, PHP version, and the authenticated user's email/role. Firefly III's API does not expose a server timezone, so it is not shown.
- **Global counts** — asset accounts, liabilities, budgets, bills and piggy banks in the instance.
- **Period statistics** — transaction counts by type (deposit/withdrawal/transfer), first and last transaction date, distinct accounts/categories/payees/tags, and average daily income/expense.

The PDF (`summary_{period}.pdf`) is generated only in standard (non-legacy) mode; the Summary Excel sheet is always present in the workbook.
