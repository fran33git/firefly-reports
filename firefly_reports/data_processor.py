"""Deprecated internal shim: the builders live in ``firefly_reports.reports.<key>.build``.

Removed before 2.0.0 ships.
"""

from firefly_reports.reports._money import _d
from firefly_reports.reports.account_statements.build import build_account_statements
from firefly_reports.reports.all_tags.build import build_all_tags_report
from firefly_reports.reports.audit_log.build import build_audit_log
from firefly_reports.reports.bills.build import build_bills_report
from firefly_reports.reports.budget_forecast.build import build_performance_forecast
from firefly_reports.reports.budget_vs_actual.build import build_budget_vs_actual
from firefly_reports.reports.cash_flow.build import build_cash_flow
from firefly_reports.reports.category_ledger.build import build_category_ledger
from firefly_reports.reports.cumulative_cashflow.build import build_cumulative_cashflow
from firefly_reports.reports.expense_trend.build import build_expense_trend
from firefly_reports.reports.filters import apply_global_filters
from firefly_reports.reports.historical_growth.build import build_historical_report
from firefly_reports.reports.income_concentration.build import build_income_concentration
from firefly_reports.reports.income_expense.build import build_income_expense
from firefly_reports.reports.journal.build import build_journal
from firefly_reports.reports.kpi_scorecard.build import build_kpi_scorecard
from firefly_reports.reports.liabilities.build import build_liabilities_report
from firefly_reports.reports.linkage_audit.build import build_linkage_report
from firefly_reports.reports.liquidity_forecast.build import build_liquidity_forecast
from firefly_reports.reports.net_worth.build import build_net_worth
from firefly_reports.reports.payee_ledger.build import build_payee_ledger
from firefly_reports.reports.savings_goals.build import build_savings_goals
from firefly_reports.reports.summary.build import build_summary
from firefly_reports.reports.tagged.build import build_tagged_report
from firefly_reports.reports.tax_summary.build import build_tax_summary
from firefly_reports.reports.transaction_register.build import build_transaction_register
from firefly_reports.reports.yoy.build import build_yoy_comparison

__all__ = [
    "_d",
    "apply_global_filters",
    "build_account_statements",
    "build_all_tags_report",
    "build_audit_log",
    "build_bills_report",
    "build_budget_vs_actual",
    "build_cash_flow",
    "build_category_ledger",
    "build_cumulative_cashflow",
    "build_expense_trend",
    "build_historical_report",
    "build_income_concentration",
    "build_income_expense",
    "build_journal",
    "build_kpi_scorecard",
    "build_liabilities_report",
    "build_linkage_report",
    "build_liquidity_forecast",
    "build_net_worth",
    "build_payee_ledger",
    "build_performance_forecast",
    "build_savings_goals",
    "build_summary",
    "build_tagged_report",
    "build_tax_summary",
    "build_transaction_register",
    "build_yoy_comparison",
]
