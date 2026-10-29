"""The report registry: every report, in canonical order (Excel sheet order first)."""

from firefly_reports.reports import (
    account_statements,
    all_tags,
    audit_log,
    bills,
    budget_forecast,
    budget_vs_actual,
    cash_flow,
    category_ledger,
    cumulative_cashflow,
    dashboard_income_expense,
    dashboard_kpi_trend,
    expense_trend,
    historical_growth,
    income_concentration,
    income_expense,
    journal,
    kpi_scorecard,
    liabilities,
    linkage_audit,
    liquidity_forecast,
    net_worth,
    payee_ledger,
    savings_goals,
    summary,
    tagged,
    tax_summary,
    transaction_register,
    yoy,
)
from firefly_reports.reports.spec import ReportSpec

# Canonical order: Excel sheet order (1.x), then the other reports, then the two views.
REPORTS: tuple[ReportSpec, ...] = (
    cash_flow.SPEC,
    income_expense.SPEC,
    transaction_register.SPEC,
    net_worth.SPEC,
    account_statements.SPEC,
    tax_summary.SPEC,
    expense_trend.SPEC,
    tagged.SPEC,
    budget_vs_actual.SPEC,
    bills.SPEC,
    savings_goals.SPEC,
    liabilities.SPEC,
    kpi_scorecard.SPEC,
    yoy.SPEC,
    cumulative_cashflow.SPEC,
    income_concentration.SPEC,
    summary.SPEC,
    audit_log.SPEC,
    journal.SPEC,
    budget_forecast.SPEC,
    category_ledger.SPEC,
    payee_ledger.SPEC,
    linkage_audit.SPEC,
    all_tags.SPEC,
    historical_growth.SPEC,
    liquidity_forecast.SPEC,
    dashboard_income_expense.SPEC,
    dashboard_kpi_trend.SPEC,
)

_BY_KEY = {spec.key: spec for spec in REPORTS}


def get(key: str) -> ReportSpec:
    return _BY_KEY[key]


def keys() -> tuple[str, ...]:
    return tuple(_BY_KEY)
