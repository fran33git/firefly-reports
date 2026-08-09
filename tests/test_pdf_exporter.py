"""Smoke tests for PDF render functions — verify no exceptions and non-empty output."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firefly_reports"))

from datetime import date

import pytest

from data_processor import (
    build_cash_flow, build_income_expense, build_transaction_register,
    build_journal,
    build_net_worth, build_account_statements, build_tax_summary,
    build_expense_trend, build_tagged_report, build_budget_vs_actual,
    build_bills_report, build_savings_goals, build_liabilities_report,
    build_kpi_scorecard, build_yoy_comparison, build_cumulative_cashflow,
    build_income_concentration, build_audit_log, build_performance_forecast,
    build_category_ledger, build_payee_ledger, build_linkage_report,
    build_all_tags_report, build_summary,
)
from pdf_exporter import (
    render_cash_flow_pdf, render_income_expense_pdf, render_transaction_register_pdf,
    render_journal_pdf,
    render_net_worth_pdf, render_account_statements_pdf, render_tax_summary_pdf,
    render_expense_trend_pdf, render_tagged_report_pdf, render_budget_vs_actual_pdf,
    render_bills_pdf, render_savings_goals_pdf, render_liabilities_pdf,
    render_kpi_scorecard_pdf, render_yoy_pdf, render_cumulative_cashflow_pdf,
    render_income_concentration_pdf, render_income_expense_dashboard_pdf,
    render_kpi_trend_dashboard_pdf, render_historical_report_pdf,
    render_liquidity_forecast_pdf, render_audit_log_pdf, render_forecast_pdf,
    render_category_ledger_pdf, render_payee_ledger_pdf, render_linkage_audit_pdf,
    render_all_tags_pdf, render_summary_pdf,
)

MIN_PDF_BYTES = 1000


def _check_pdf(path):
    assert path.exists(), f"PDF not created: {path}"
    assert path.stat().st_size > MIN_PDF_BYTES, f"PDF too small: {path.stat().st_size} bytes"


def test_render_cash_flow_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_cash_flow(txn_2025, *period, owner, currency)
    p = tmp_path / "cash_flow.pdf"
    render_cash_flow_pdf(data, str(p))
    _check_pdf(p)


def test_render_income_expense_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_income_expense(txn_2025, *period, owner, currency)
    p = tmp_path / "ie.pdf"
    render_income_expense_pdf(data, str(p))
    _check_pdf(p)


def test_render_transaction_register_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_transaction_register(txn_2025, *period, owner, currency)
    p = tmp_path / "register_legacy.pdf"
    render_transaction_register_pdf(data, str(p), legacy=True)
    _check_pdf(p)


def test_render_transaction_register_modern_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_transaction_register(txn_2025, *period, owner, currency)
    p = tmp_path / "register_modern.pdf"
    render_transaction_register_pdf(data, str(p), legacy=False)
    _check_pdf(p)


def test_render_net_worth_pdf(tmp_path, accounts, period, owner, currency):
    _, end = period
    data = build_net_worth(accounts, end, owner, currency)
    p = tmp_path / "nw.pdf"
    render_net_worth_pdf(data, str(p))
    _check_pdf(p)


def test_render_account_statements_pdf(tmp_path, accounts, txn_2025, period, owner, currency):
    txn_by_account = {"1": txn_2025}
    data = build_account_statements(accounts[:1], txn_by_account, *period, owner, currency)
    p = tmp_path / "stmts.pdf"
    render_account_statements_pdf(data, str(p))
    _check_pdf(p)


def test_render_tax_summary_pdf(tmp_path, txn_2025, owner, currency):
    data = build_tax_summary(txn_2025, 2025, owner, currency)
    p = tmp_path / "tax.pdf"
    render_tax_summary_pdf(data, str(p))
    _check_pdf(p)


def test_render_expense_trend_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_expense_trend(txn_2025, *period, owner, currency)
    p = tmp_path / "trend.pdf"
    render_expense_trend_pdf(data, str(p))
    _check_pdf(p)


def test_render_tagged_report_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_tagged_report(txn_2025, ["tax"], *period, owner, currency)
    p = tmp_path / "tagged.pdf"
    render_tagged_report_pdf(data, str(p))
    _check_pdf(p)


def test_render_budget_vs_actual_pdf(tmp_path, budgets, budget_limits, txn_2025, period, owner, currency):
    data = build_budget_vs_actual(budgets, budget_limits, txn_2025, *period, owner, currency)
    p = tmp_path / "budget.pdf"
    render_budget_vs_actual_pdf(data, str(p))
    _check_pdf(p)


def test_render_bills_pdf(tmp_path, bills, bill_txn, period, owner, currency):
    data = build_bills_report(bills, bill_txn, *period, owner, currency)
    p = tmp_path / "bills.pdf"
    render_bills_pdf(data, str(p))
    _check_pdf(p)


def test_render_savings_goals_pdf(tmp_path, piggy_banks, period, owner, currency):
    _, end = period
    data = build_savings_goals(piggy_banks, end, owner, currency)
    p = tmp_path / "savings.pdf"
    render_savings_goals_pdf(data, str(p))
    _check_pdf(p)


def test_render_liabilities_pdf(tmp_path, liabilities, period, owner, currency):
    start, end = period
    data = build_liabilities_report(liabilities, {}, end, start, end, owner, currency)
    p = tmp_path / "liab.pdf"
    render_liabilities_pdf(data, str(p))
    _check_pdf(p)


def test_render_kpi_scorecard_pdf(tmp_path, txn_2025, accounts, liabilities, period, owner, currency):
    data = build_kpi_scorecard(txn_2025, accounts, liabilities, *period, owner, currency)
    p = tmp_path / "kpi.pdf"
    render_kpi_scorecard_pdf(data, str(p))
    _check_pdf(p)


def test_render_yoy_pdf(tmp_path, txn_2025, txn_2024, period, period_prev, owner, currency):
    data = build_yoy_comparison(txn_2025, txn_2024, *period, *period_prev, owner, currency)
    p = tmp_path / "yoy.pdf"
    render_yoy_pdf(data, str(p))
    _check_pdf(p)


def test_render_cumulative_cashflow_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_cumulative_cashflow(txn_2025, *period, owner, currency)
    p = tmp_path / "cumcf.pdf"
    render_cumulative_cashflow_pdf(data, str(p))
    _check_pdf(p)


def test_render_income_concentration_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_income_concentration(txn_2025, *period, owner, currency)
    p = tmp_path / "conc.pdf"
    render_income_concentration_pdf(data, str(p))
    _check_pdf(p)

def test_render_income_expense_dashboard_pdf(tmp_path, owner, currency):
    data = {
        "owner": owner,
        "period_start": date(2025, 1, 1),
        "period_end": date(2025, 1, 31),
        "currency": currency,
        "expense_by_cat": [
            {"category": "Food", "amount": 100},
            {"category": "Rent", "amount": 500},
            {"category": "Utilities", "amount": 150},
            {"category": "Transport", "amount": 80},
            {"category": "Entertainment", "amount": 120},
            {"category": "Health", "amount": 60},
            {"category": "Education", "amount": 200},
            {"category": "Shopping", "amount": 90},
            {"category": "Misc", "amount": 30},
        ],
        "total_income": 3000,
        "total_expense": 1430,
        "net_savings": 1570,
        "savings_rate": 52.3,
        "monthly_trend": [
            {"month": "2025-01", "income": 3000, "expense": 1430, "net": 1570},
        ],
        "income_by_client": [
            {"client": "Client A", "amount": 1500},
            {"client": "Client B", "amount": 1000},
            {"client": "Client C", "amount": 500},
        ]
    }
    p = tmp_path / "ie_dashboard.pdf"
    render_income_expense_dashboard_pdf(data, str(p))
    _check_pdf(p)


def test_render_kpi_trend_dashboard_pdf(tmp_path, owner, currency):
    data = {
        "owner": owner,
        "period_start": date(2025, 1, 1),
        "period_end": date(2025, 1, 31),
        "currency": currency,
        "monthly_trend": [
            {"month": "2024-08", "income": 2000, "expense": 1500, "net": 500},
            {"month": "2024-09", "income": 2200, "expense": 1600, "net": 600},
            {"month": "2024-10", "income": 2100, "expense": 1700, "net": 400},
            {"month": "2024-11", "income": 2500, "expense": 1800, "net": 700},
            {"month": "2024-12", "income": 2400, "expense": 1900, "net": 500},
            {"month": "2025-01", "income": 3000, "expense": 2000, "net": 1000},
        ],
        "savings_rate": 33.3,
        "burn_rate": 2000,
        "cash_runway": 12.5
    }
    p = tmp_path / "kpi_dashboard.pdf"
    render_kpi_trend_dashboard_pdf(data, str(p))
    _check_pdf(p)


def test_render_historical_report_pdf(tmp_path, owner, currency):
    data = {
        "owner": owner,
        "currency": currency,
        "rows": [
            {
                "year": 2023,
                "income": 40000,
                "expense": 30000,
                "net": 10000,
                "income_growth": 0,
                "expense_growth": 0,
                "net_growth": 0,
            },
            {
                "year": 2024,
                "income": 45000,
                "expense": 32000,
                "net": 13000,
                "income_growth": 12.5,
                "expense_growth": 6.7,
                "net_growth": 30.0,
            },
            {
                "year": 2025,
                "income": 50000,
                "expense": 35000,
                "net": 15000,
                "income_growth": 11.1,
                "expense_growth": 9.4,
                "net_growth": 15.4,
            },
        ]
    }
    p = tmp_path / "historical.pdf"
    render_historical_report_pdf(data, str(p))
    _check_pdf(p)


def test_render_liquidity_forecast_pdf(tmp_path, owner, currency):
    data = {
        "owner": owner,
        "currency": currency,
        "forecast_months": [
            {
                "month": "2025-02",
                "month_label": "February 2025",
                "inflow": 5000,
                "outflow": 4000,
                "fixed_outflow": 2500,
                "variable_outflow": 1500,
                "balance": 11000,
            },
            {
                "month": "2025-03",
                "month_label": "March 2025",
                "inflow": 5000,
                "outflow": 3800,
                "fixed_outflow": 2300,
                "variable_outflow": 1500,
                "balance": 12200,
            },
            {
                "month": "2025-04",
                "month_label": "April 2025",
                "inflow": 5000,
                "outflow": 4200,
                "fixed_outflow": 2700,
                "variable_outflow": 1500,
                "balance": 13000,
            },
            {
                "month": "2025-05",
                "month_label": "May 2025",
                "inflow": 5000,
                "outflow": 4000,
                "fixed_outflow": 2500,
                "variable_outflow": 1500,
                "balance": 14000,
            },
            {
                "month": "2025-06",
                "month_label": "June 2025",
                "inflow": 5000,
                "outflow": 4000,
                "fixed_outflow": 2500,
                "variable_outflow": 1500,
                "balance": 15000,
            },
            {
                "month": "2025-07",
                "month_label": "July 2025",
                "inflow": 5000,
                "outflow": 4000,
                "fixed_outflow": 2500,
                "variable_outflow": 1500,
                "balance": 16000,
            },
        ]
    }
    p = tmp_path / "forecast.pdf"
    render_liquidity_forecast_pdf(data, str(p))
    _check_pdf(p)


def test_render_audit_log_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_audit_log(txn_2025, *period, owner, currency)
    p = tmp_path / "audit_log.pdf"
    render_audit_log_pdf(data, str(p))
    _check_pdf(p)


def test_render_forecast_pdf(tmp_path, txn_2025, budgets, budget_limits, period, owner, currency):
    data = build_performance_forecast(budgets, budget_limits, txn_2025, *period, owner, currency)
    p = tmp_path / "forecast_perf.pdf"
    render_forecast_pdf(data, str(p))
    _check_pdf(p)


def test_render_category_ledger_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_category_ledger(txn_2025, *period, owner, currency)
    p = tmp_path / "category_ledger.pdf"
    render_category_ledger_pdf(data, str(p))
    _check_pdf(p)


def test_render_payee_ledger_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_payee_ledger(txn_2025, *period, owner, currency)
    p = tmp_path / "payee_ledger.pdf"
    render_payee_ledger_pdf(data, str(p))
    _check_pdf(p)


def test_render_linkage_audit_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_linkage_report(txn_2025, [], *period, owner, currency)
    p = tmp_path / "linkage_audit.pdf"
    render_linkage_audit_pdf(data, str(p))
    _check_pdf(p)


def test_render_all_tags_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_all_tags_report(txn_2025, *period, owner, currency)
    p = tmp_path / "all_tags.pdf"
    render_all_tags_pdf(data, str(p))
    _check_pdf(p)


def test_render_journal_pdf(tmp_path, txn_2025, period, owner, currency):
    data = build_journal(txn_2025, *period, owner, currency)
    p = tmp_path / "journal.pdf"
    render_journal_pdf(data, str(p))
    assert p.exists() and p.stat().st_size > MIN_PDF_BYTES


def test_render_cash_flow_pdf_with_waterfall(tmp_path, txn_2025, accounts, liabilities,
                                             period, owner, currency):
    """Waterfall page is rendered when accounts/liabilities are provided."""
    data = build_cash_flow(txn_2025, *period, owner, currency, accounts, liabilities)
    assert data["waterfall"]["closing_cash"] is not None
    p = tmp_path / "cash_flow_wf.pdf"
    render_cash_flow_pdf(data, str(p))
    assert p.exists() and p.stat().st_size > MIN_PDF_BYTES


def test_render_summary_pdf(
    tmp_path, txn_2025, accounts, liabilities, budgets, bills, piggy_banks,
    about, about_user, period, owner, currency,
):
    start, end = period
    data = build_summary(
        txn_2025, accounts, liabilities, budgets, bills, piggy_banks,
        about, about_user, start, end, owner, currency,
    )
    p = tmp_path / "summary.pdf"
    render_summary_pdf(data, str(p))
    _check_pdf(p)
