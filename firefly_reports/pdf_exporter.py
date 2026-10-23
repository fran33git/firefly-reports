"""Deprecated internal shim: the PDF renderers live in ``firefly_reports.reports.<key>.pdf``.

Removed before 2.0.0 ships.
"""

from firefly_reports.reports.account_statements.pdf import render_account_statements_pdf
from firefly_reports.reports.all_tags.pdf import render_all_tags_pdf
from firefly_reports.reports.audit_log.pdf import render_audit_log_pdf
from firefly_reports.reports.bills.pdf import render_bills_pdf
from firefly_reports.reports.budget_forecast.pdf import render_forecast_pdf
from firefly_reports.reports.budget_vs_actual.pdf import render_budget_vs_actual_pdf
from firefly_reports.reports.cash_flow.pdf import render_cash_flow_pdf
from firefly_reports.reports.category_ledger.pdf import render_category_ledger_pdf
from firefly_reports.reports.cumulative_cashflow.pdf import render_cumulative_cashflow_pdf
from firefly_reports.reports.dashboard_income_expense.pdf import render_income_expense_dashboard_pdf
from firefly_reports.reports.dashboard_kpi_trend.pdf import render_kpi_trend_dashboard_pdf
from firefly_reports.reports.expense_trend.pdf import render_expense_trend_pdf
from firefly_reports.reports.historical_growth.pdf import render_historical_report_pdf
from firefly_reports.reports.income_concentration.pdf import render_income_concentration_pdf
from firefly_reports.reports.income_expense.pdf import render_income_expense_pdf
from firefly_reports.reports.journal.pdf import render_journal_pdf
from firefly_reports.reports.kpi_scorecard.pdf import render_kpi_scorecard_pdf
from firefly_reports.reports.liabilities.pdf import render_liabilities_pdf
from firefly_reports.reports.linkage_audit.pdf import render_linkage_audit_pdf
from firefly_reports.reports.liquidity_forecast.pdf import render_liquidity_forecast_pdf
from firefly_reports.reports.net_worth.pdf import render_net_worth_pdf
from firefly_reports.reports.payee_ledger.pdf import render_payee_ledger_pdf
from firefly_reports.reports.savings_goals.pdf import render_savings_goals_pdf
from firefly_reports.reports.summary.pdf import render_summary_pdf
from firefly_reports.reports.tagged.pdf import render_tagged_report_pdf
from firefly_reports.reports.tax_summary.pdf import render_tax_summary_pdf
from firefly_reports.reports.transaction_register.pdf import render_transaction_register_pdf
from firefly_reports.reports.yoy.pdf import render_yoy_pdf

__all__ = [
    "render_account_statements_pdf",
    "render_all_tags_pdf",
    "render_audit_log_pdf",
    "render_bills_pdf",
    "render_budget_vs_actual_pdf",
    "render_cash_flow_pdf",
    "render_category_ledger_pdf",
    "render_cumulative_cashflow_pdf",
    "render_expense_trend_pdf",
    "render_forecast_pdf",
    "render_historical_report_pdf",
    "render_income_concentration_pdf",
    "render_income_expense_dashboard_pdf",
    "render_income_expense_pdf",
    "render_journal_pdf",
    "render_kpi_scorecard_pdf",
    "render_kpi_trend_dashboard_pdf",
    "render_liabilities_pdf",
    "render_linkage_audit_pdf",
    "render_liquidity_forecast_pdf",
    "render_net_worth_pdf",
    "render_payee_ledger_pdf",
    "render_savings_goals_pdf",
    "render_summary_pdf",
    "render_tagged_report_pdf",
    "render_tax_summary_pdf",
    "render_transaction_register_pdf",
    "render_yoy_pdf",
]
