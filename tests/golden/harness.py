"""Everything the golden tests know about the current import paths (one place to update)."""

from __future__ import annotations

import contextlib
import io
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from firefly_reports import clock, i18n
from firefly_reports.data_processor import (
    build_account_statements,
    build_all_tags_report,
    build_audit_log,
    build_bills_report,
    build_budget_vs_actual,
    build_cash_flow,
    build_category_ledger,
    build_cumulative_cashflow,
    build_expense_trend,
    build_historical_report,
    build_income_concentration,
    build_income_expense,
    build_journal,
    build_kpi_scorecard,
    build_liabilities_report,
    build_linkage_report,
    build_liquidity_forecast,
    build_net_worth,
    build_payee_ledger,
    build_performance_forecast,
    build_savings_goals,
    build_summary,
    build_tagged_report,
    build_tax_summary,
    build_transaction_register,
    build_yoy_comparison,
)
from firefly_reports.demo import data as demo
from firefly_reports.demo.__main__ import main as demo_main

DEMO_CLOCK = datetime(2026, 1, 15, 12, 0)
YEAR = 2025


def build_demo_suite(lang: str) -> dict[str, Any]:
    """Every builder called with the demo inputs exactly as ``demo.main()`` does."""
    start, end = date(YEAR, 1, 1), date(YEAR, 12, 31)
    prev_start, prev_end = date(YEAR - 1, 1, 1), date(YEAR - 1, 12, 31)
    demo.ensure_ids(demo.TXN_2025, "25-")
    demo.ensure_ids(demo.TXN_2024, "24-")
    o, s = demo.OWNER, demo.SYM
    t25, t24 = demo.TXN_2025, demo.TXN_2024
    i18n.load(lang)
    try:
        with clock.frozen(DEMO_CLOCK):
            kpi = build_kpi_scorecard(t25, demo.ACCOUNTS, demo.LIABILITIES, start, end, o, s)
            hist = {
                YEAR - 2 + i: {
                    "total_income": Decimal(inc),
                    "total_expense": Decimal(exp),
                    "top_categories": [
                        {"category": "Rent", "amount": Decimal("12000.00")},
                        {"category": "Groceries", "amount": Decimal(gro)},
                    ],
                }
                for i, (inc, exp, gro) in enumerate(
                    [
                        ("45000.00", "38000.00", "4000.00"),
                        ("48000.00", "39000.00", "4200.00"),
                        ("52000.00", "41000.00", "4500.00"),
                    ]
                )
            }
            return {
                "cash_flow": build_cash_flow(
                    t25, start, end, o, s, demo.ACCOUNTS, demo.LIABILITIES
                ),
                "income_expense": build_income_expense(t25, start, end, o, s),
                "transaction_register": build_transaction_register(t25, start, end, o, s),
                "net_worth": build_net_worth(demo.ACCOUNTS, end, o, s),
                "account_statements": build_account_statements(
                    demo.ACCOUNTS[:2], {"1": t25}, start, end, o, s
                ),
                "tax_summary": build_tax_summary(
                    t25,
                    YEAR,
                    owner_name=o,
                    currency_symbol=s,
                    deductible_keywords=["accountant", "software", "hardware", "marketing"],
                ),
                "expense_trend": build_expense_trend(t25, start, end, o, s),
                "tagged": build_tagged_report(t25, ["tax"], start, end, o, s),
                "budget_vs_actual": build_budget_vs_actual(
                    demo.BUDGETS, demo.BUDGET_LIMITS, t25, start, end, o, s
                ),
                "bills": build_bills_report(demo.BILLS, demo.BILL_TXN, start, end, o, s),
                "savings_goals": build_savings_goals(demo.PIGGY_BANKS, end, o, s),
                "liabilities": build_liabilities_report(
                    demo.LIABILITIES, {}, end, start, end, o, s
                ),
                "kpi_scorecard": kpi,
                "yoy": build_yoy_comparison(t25, t24, start, end, prev_start, prev_end, o, s),
                "cumulative_cashflow": build_cumulative_cashflow(t25, start, end, o, s),
                "income_concentration": build_income_concentration(t25, start, end, o, s),
                "audit_log": build_audit_log(t25, start, end, o, s),
                "summary": build_summary(
                    t25,
                    demo.ACCOUNTS,
                    demo.LIABILITIES,
                    demo.BUDGETS,
                    demo.BILLS,
                    demo.PIGGY_BANKS,
                    demo.ABOUT,
                    demo.ABOUT_USER,
                    start,
                    end,
                    o,
                    s,
                ),
                "journal": build_journal(t25, start, end, o, s),
                "budget_forecast": build_performance_forecast(
                    demo.BUDGETS, demo.BUDGET_LIMITS, t25, start, end, o, s
                ),
                "category_ledger": build_category_ledger(t25, start, end, o, s),
                "payee_ledger": build_payee_ledger(t25, start, end, o, s),
                "linkage_audit": build_linkage_report(
                    t25, demo.TRANSACTION_LINKS, start, end, o, s
                ),
                "all_tags": build_all_tags_report(t25, start, end, o, s),
                "historical_growth": build_historical_report(hist, o, s),
                "liquidity_forecast": build_liquidity_forecast(
                    current_balance=Decimal("15000.00"),
                    avg_income=kpi["avg_monthly_in"],
                    avg_variable_expense=kpi["avg_monthly_out"],
                    bills=demo.BILLS,
                    end_date=end,
                    owner_name=o,
                    currency_symbol=s,
                ),
            }
    finally:
        i18n.load("en")


def render_demo_suite(out_dir: Path, lang: str) -> list[Path]:
    """Run the demo (all 28 PDFs + the workbook) with the clock frozen; return the files."""
    argv = ["demo", "--out", str(out_dir), "--lang", lang, "--year", str(YEAR)]
    old_argv = sys.argv
    sys.argv = argv
    try:
        with clock.frozen(DEMO_CLOCK), contextlib.redirect_stdout(io.StringIO()):
            demo_main()
    finally:
        sys.argv = old_argv
        i18n.load("en")
    return sorted(out_dir.iterdir())
