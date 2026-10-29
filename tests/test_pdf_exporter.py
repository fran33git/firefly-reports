"""Smoke tests for PDF render functions — verify no exceptions and non-empty output."""

from datetime import date

from firefly_reports import i18n
from firefly_reports.reports.account_statements.build import build_account_statements
from firefly_reports.reports.account_statements.pdf import render_account_statements_pdf
from firefly_reports.reports.all_tags.build import build_all_tags_report
from firefly_reports.reports.all_tags.pdf import render_all_tags_pdf
from firefly_reports.reports.audit_log.build import build_audit_log
from firefly_reports.reports.audit_log.pdf import render_audit_log_pdf
from firefly_reports.reports.bills.build import build_bills_report
from firefly_reports.reports.bills.pdf import render_bills_pdf
from firefly_reports.reports.budget_forecast.build import build_performance_forecast
from firefly_reports.reports.budget_forecast.pdf import render_forecast_pdf
from firefly_reports.reports.budget_vs_actual.build import build_budget_vs_actual
from firefly_reports.reports.budget_vs_actual.pdf import render_budget_vs_actual_pdf
from firefly_reports.reports.cash_flow.build import build_cash_flow
from firefly_reports.reports.cash_flow.pdf import render_cash_flow_pdf
from firefly_reports.reports.category_ledger.build import build_category_ledger
from firefly_reports.reports.category_ledger.pdf import render_category_ledger_pdf
from firefly_reports.reports.cumulative_cashflow.build import build_cumulative_cashflow
from firefly_reports.reports.cumulative_cashflow.pdf import render_cumulative_cashflow_pdf
from firefly_reports.reports.dashboard_income_expense.pdf import render_income_expense_dashboard_pdf
from firefly_reports.reports.dashboard_kpi_trend.pdf import render_kpi_trend_dashboard_pdf
from firefly_reports.reports.expense_trend.build import build_expense_trend
from firefly_reports.reports.expense_trend.pdf import render_expense_trend_pdf
from firefly_reports.reports.historical_growth.pdf import render_historical_report_pdf
from firefly_reports.reports.income_concentration.build import build_income_concentration
from firefly_reports.reports.income_concentration.pdf import render_income_concentration_pdf
from firefly_reports.reports.income_expense.build import build_income_expense
from firefly_reports.reports.income_expense.pdf import render_income_expense_pdf
from firefly_reports.reports.journal.build import build_journal
from firefly_reports.reports.journal.pdf import render_journal_pdf
from firefly_reports.reports.kpi_scorecard.build import build_kpi_scorecard
from firefly_reports.reports.kpi_scorecard.pdf import render_kpi_scorecard_pdf
from firefly_reports.reports.liabilities.build import build_liabilities_report
from firefly_reports.reports.liabilities.pdf import render_liabilities_pdf
from firefly_reports.reports.linkage_audit.build import build_linkage_report
from firefly_reports.reports.linkage_audit.pdf import render_linkage_audit_pdf
from firefly_reports.reports.liquidity_forecast.pdf import render_liquidity_forecast_pdf
from firefly_reports.reports.net_worth.build import build_net_worth
from firefly_reports.reports.net_worth.pdf import render_net_worth_pdf
from firefly_reports.reports.payee_ledger.build import build_payee_ledger
from firefly_reports.reports.payee_ledger.pdf import render_payee_ledger_pdf
from firefly_reports.reports.savings_goals.build import build_savings_goals
from firefly_reports.reports.savings_goals.pdf import render_savings_goals_pdf
from firefly_reports.reports.summary.build import build_summary
from firefly_reports.reports.summary.pdf import render_summary_pdf
from firefly_reports.reports.tagged.build import build_tagged_report
from firefly_reports.reports.tagged.pdf import render_tagged_report_pdf
from firefly_reports.reports.tax_summary.build import build_tax_summary
from firefly_reports.reports.tax_summary.pdf import render_tax_summary_pdf
from firefly_reports.reports.transaction_register.build import build_transaction_register
from firefly_reports.reports.transaction_register.pdf import render_transaction_register_pdf
from firefly_reports.reports.yoy.build import build_yoy_comparison
from firefly_reports.reports.yoy.pdf import render_yoy_pdf
from tests.golden.snapshot import story_recorder

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


def _legend_text(snaps):
    return [
        f["text"]
        for s in snaps
        for f in s.story
        if isinstance(f, dict) and "text" in f and "WIT" in f["text"]
    ]


def test_render_transaction_register_legacy_legend_is_translated(
    tmp_path, txn_2025, period, owner, currency
):
    data = build_transaction_register(txn_2025, *period, owner, currency)
    p = tmp_path / "register_legacy.pdf"
    with story_recorder() as snaps:
        render_transaction_register_pdf(data, str(p), legacy=True)
    legends = _legend_text(snaps)
    assert len(legends) == 1
    legend = legends[0]
    assert legend.startswith("Total transactions in period:")
    # getPlainText() collapses whitespace runs: compare the normalized form in the
    # story, and the exact spacing (three-space separators) in the catalog values.
    assert " ".join(legend.split()) == (
        f"Total transactions in period: {data['total_transactions']} · "
        "WIT = Withdrawal DEP = Deposit TRF = Transfer"
    )
    assert "Prelievo" not in legend
    assert (
        i18n.t("pdf.register_legacy_legend") == "WIT = Withdrawal   DEP = Deposit   TRF = Transfer"
    )
    with i18n.using("it"):
        assert (
            i18n.t("pdf.register_legacy_legend")
            == "WIT = Prelievo   DEP = Versamento   TRF = Giroconto"
        )
        p_it = tmp_path / "register_legacy_it.pdf"
        with story_recorder() as snaps_it:
            render_transaction_register_pdf(data, str(p_it), legacy=True)
    legends_it = _legend_text(snaps_it)
    assert len(legends_it) == 1
    assert legends_it[0].endswith("WIT = Prelievo DEP = Versamento TRF = Giroconto")


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


def test_render_budget_vs_actual_pdf(
    tmp_path, budgets, budget_limits, txn_2025, period, owner, currency
):
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


def test_render_kpi_scorecard_pdf(
    tmp_path, txn_2025, accounts, liabilities, period, owner, currency
):
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
        ],
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
        "cash_runway": 12.5,
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
        ],
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
        ],
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


def test_render_cash_flow_pdf_with_waterfall(
    tmp_path, txn_2025, accounts, liabilities, period, owner, currency
):
    """Waterfall page is rendered when accounts/liabilities are provided."""
    data = build_cash_flow(txn_2025, *period, owner, currency, accounts, liabilities)
    assert data["waterfall"]["closing_cash"] is not None
    p = tmp_path / "cash_flow_wf.pdf"
    render_cash_flow_pdf(data, str(p))
    assert p.exists() and p.stat().st_size > MIN_PDF_BYTES


def test_render_summary_pdf(
    tmp_path,
    txn_2025,
    accounts,
    liabilities,
    budgets,
    bills,
    piggy_banks,
    about,
    about_user,
    period,
    owner,
    currency,
):
    start, end = period
    data = build_summary(
        txn_2025,
        accounts,
        liabilities,
        budgets,
        bills,
        piggy_banks,
        about,
        about_user,
        start,
        end,
        owner,
        currency,
    )
    p = tmp_path / "summary.pdf"
    render_summary_pdf(data, str(p))
    _check_pdf(p)
