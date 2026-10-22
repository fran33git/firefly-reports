#!/usr/bin/env python3
"""Demo with mock data — all 26 reports.

Usage:
  python -m firefly_reports.demo [--out ./output] [--lang en|it] [--year YYYY] [--debug]
"""

import argparse
import logging
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

from firefly_reports import i18n
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
from firefly_reports.demo.data import (
    ABOUT,
    ABOUT_USER,
    ACCOUNTS,
    BILL_TXN,
    BILLS,
    BUDGET_LIMITS,
    BUDGETS,
    LIABILITIES,
    OWNER,
    PIGGY_BANKS,
    SYM,
    TRANSACTION_LINKS,
    TXN_2024,
    TXN_2025,
    ensure_ids,
)
from firefly_reports.excel_exporter import render_all_xlsx_full
from firefly_reports.pdf_exporter import (
    render_account_statements_pdf,
    render_all_tags_pdf,
    render_audit_log_pdf,
    render_bills_pdf,
    render_budget_vs_actual_pdf,
    render_cash_flow_pdf,
    render_category_ledger_pdf,
    render_cumulative_cashflow_pdf,
    render_expense_trend_pdf,
    render_forecast_pdf,
    render_historical_report_pdf,
    render_income_concentration_pdf,
    render_income_expense_dashboard_pdf,
    render_income_expense_pdf,
    render_journal_pdf,
    render_kpi_scorecard_pdf,
    render_kpi_trend_dashboard_pdf,
    render_liabilities_pdf,
    render_linkage_audit_pdf,
    render_liquidity_forecast_pdf,
    render_net_worth_pdf,
    render_payee_ledger_pdf,
    render_savings_goals_pdf,
    render_summary_pdf,
    render_tagged_report_pdf,
    render_tax_summary_pdf,
    render_transaction_register_pdf,
    render_yoy_pdf,
)


def _setup_debug_log(debug: bool, out_dir: Path, debug_file: str | None = None) -> logging.Logger:
    logger = logging.getLogger("firefly_reports")
    if not debug:
        logger.addHandler(logging.NullHandler())
        return logger
    logger.setLevel(logging.DEBUG)
    if debug_file:
        log_path = Path(debug_file)
    else:
        from datetime import datetime as _dt

        ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        log_path = out_dir / f"debug_{ts}.log"
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(fh)
    print(f"[*] Debug log: {log_path.resolve()}")
    return logger


def main():
    # Avoid UnicodeEncodeError on Windows consoles with legacy codepages
    # (e.g. cp1252): replace characters the console cannot encode.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description="Demo Firefly report generator (mock data)")
    parser.add_argument("--out", default="./output", help="Output directory (default: ./output)")
    parser.add_argument(
        "--lang",
        choices=["en", "it"],
        default="en",
        help="Report language (default: en)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        metavar="YYYY",
        help="Full calendar year mode (default: 2025)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug log to file")
    parser.add_argument(
        "--debug-file",
        default=None,
        metavar="PATH",
        help="Debug log file path (default: <out>/debug_<timestamp>.log)",
    )
    args = parser.parse_args()
    i18n.load(args.lang)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    log = _setup_debug_log(args.debug, out_dir, args.debug_file)

    year = args.year
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    start_prev = date(year - 1, 1, 1)
    end_prev = date(year - 1, 12, 31)
    tag = f"{start}__{end}"

    print("[*] Processing data...")

    ensure_ids(TXN_2025, "25-")
    ensure_ids(TXN_2024, "24-")

    # ── Reports 1–8
    cf = build_cash_flow(TXN_2025, start, end, OWNER, SYM, ACCOUNTS, LIABILITIES)
    ie = build_income_expense(TXN_2025, start, end, OWNER, SYM)
    reg = build_transaction_register(TXN_2025, start, end, OWNER, SYM)
    nw = build_net_worth(ACCOUNTS, end, OWNER, SYM)
    stmts = build_account_statements(ACCOUNTS[:2], {"1": TXN_2025}, start, end, OWNER, SYM)
    tax = build_tax_summary(
        TXN_2025,
        year,
        owner_name=OWNER,
        currency_symbol=SYM,
        deductible_keywords=["accountant", "software", "hardware", "marketing"],
    )
    trend = build_expense_trend(TXN_2025, start, end, OWNER, SYM)
    tagged = build_tagged_report(TXN_2025, ["tax"], start, end, OWNER, SYM)

    # ── Reports 9–24 (extended)
    budget = build_budget_vs_actual(BUDGETS, BUDGET_LIMITS, TXN_2025, start, end, OWNER, SYM)
    bills = build_bills_report(BILLS, BILL_TXN, start, end, OWNER, SYM)
    savings = build_savings_goals(PIGGY_BANKS, end, OWNER, SYM)
    liab = build_liabilities_report(LIABILITIES, {}, end, start, end, OWNER, SYM)
    kpi = build_kpi_scorecard(TXN_2025, ACCOUNTS, LIABILITIES, start, end, OWNER, SYM)
    yoy = build_yoy_comparison(TXN_2025, TXN_2024, start, end, start_prev, end_prev, OWNER, SYM)
    cum_cf = build_cumulative_cashflow(TXN_2025, start, end, OWNER, SYM)
    conc = build_income_concentration(TXN_2025, start, end, OWNER, SYM)
    audit = build_audit_log(TXN_2025, start, end, OWNER, SYM)
    summary = build_summary(
        TXN_2025,
        ACCOUNTS,
        LIABILITIES,
        BUDGETS,
        BILLS,
        PIGGY_BANKS,
        ABOUT,
        ABOUT_USER,
        start,
        end,
        OWNER,
        SYM,
    )
    journal = build_journal(TXN_2025, start, end, OWNER, SYM)
    forecast = build_performance_forecast(BUDGETS, BUDGET_LIMITS, TXN_2025, start, end, OWNER, SYM)

    # Phase 6A reports
    cat_ledger = build_category_ledger(TXN_2025, start, end, OWNER, SYM)
    payee_ledger = build_payee_ledger(TXN_2025, start, end, OWNER, SYM)
    linkage = build_linkage_report(TXN_2025, TRANSACTION_LINKS, start, end, OWNER, SYM)
    all_tags = build_all_tags_report(TXN_2025, start, end, OWNER, SYM)

    # Strategic reports (Phase 6B)
    # Mock historical data for 3 years ending at --year
    hist_amounts = [
        ("45000.00", "38000.00", "4000.00"),
        ("48000.00", "39000.00", "4200.00"),
        ("52000.00", "41000.00", "4500.00"),
    ]
    hist_dict = {
        year - 2 + i: {
            "total_income": Decimal(inc),
            "total_expense": Decimal(exp),
            "top_categories": [
                {"category": "Rent", "amount": Decimal("12000.00")},
                {"category": "Groceries", "amount": Decimal(gro)},
            ],
        }
        for i, (inc, exp, gro) in enumerate(hist_amounts)
    }
    hist_report = build_historical_report(hist_dict, OWNER, SYM)

    # Mock balance for forecast
    liquid_assets = Decimal("15000.00")
    liquid_forecast = build_liquidity_forecast(
        current_balance=liquid_assets,
        avg_income=kpi["avg_monthly_in"],
        avg_variable_expense=kpi["avg_monthly_out"],
        bills=BILLS,
        end_date=end,
        owner_name=OWNER,
        currency_symbol=SYM,
    )

    print(f"    KPI: savings rate {kpi['savings_rate']}%")
    print(f"    Income by client: {conc['client_count']} clients")
    print(
        f"    Savings goals: {savings['goal_count']} goals, overall progress {savings['overall_pct']}%"
    )
    print(
        f"    Liabilities: {liab['liability_count']} liabilities, total debt {liab['total_debt']}"
    )

    # ── PDF
    print("\n[*] Generating PDFs...")
    jobs = [
        (render_cash_flow_pdf, cf, f"cash_flow_{tag}.pdf"),
        (render_income_expense_pdf, ie, f"income_expense_{tag}.pdf"),
        (render_transaction_register_pdf, reg, f"transaction_register_{tag}.pdf"),
        (render_net_worth_pdf, nw, f"net_worth_{tag}.pdf"),
        (render_tax_summary_pdf, tax, f"tax_summary_{year}.pdf"),
        (render_expense_trend_pdf, trend, f"expense_trend_{tag}.pdf"),
        (render_tagged_report_pdf, tagged, f"tagged_tax_{tag}.pdf"),
        (render_budget_vs_actual_pdf, budget, f"budget_vs_actual_{tag}.pdf"),
        (render_bills_pdf, bills, f"bills_{tag}.pdf"),
        (render_savings_goals_pdf, savings, f"savings_goals_{tag}.pdf"),
        (render_liabilities_pdf, liab, f"liabilities_{tag}.pdf"),
        (render_kpi_scorecard_pdf, kpi, f"kpi_scorecard_{tag}.pdf"),
        (render_yoy_pdf, yoy, f"yoy_comparison_{year - 1}_vs_{year}.pdf"),
        (render_cumulative_cashflow_pdf, cum_cf, f"cumulative_cashflow_{tag}.pdf"),
        (render_income_concentration_pdf, conc, f"income_concentration_{tag}.pdf"),
        (
            render_income_expense_dashboard_pdf,
            {**ie, "monthly_trend": kpi["monthly_trend"]},
            f"dashboard_income_expense_{tag}.pdf",
        ),
        (render_kpi_trend_dashboard_pdf, kpi, f"dashboard_kpi_trend_{tag}.pdf"),
        (render_audit_log_pdf, audit, f"audit_log_{tag}.pdf"),
        (render_summary_pdf, summary, f"summary_{tag}.pdf"),
        (render_journal_pdf, journal, f"journal_{tag}.pdf"),
        (render_forecast_pdf, forecast, f"budget_forecast_{tag}.pdf"),
        (render_category_ledger_pdf, cat_ledger, f"ledger_category_{tag}.pdf"),
        (render_payee_ledger_pdf, payee_ledger, f"ledger_payee_{tag}.pdf"),
        (render_linkage_audit_pdf, linkage, f"audit_linkage_{tag}.pdf"),
        (render_all_tags_pdf, all_tags, f"ledger_all_tags_{tag}.pdf"),
        (render_historical_report_pdf, hist_report, f"historical_growth_{tag}.pdf"),
        (render_liquidity_forecast_pdf, liquid_forecast, f"liquidity_forecast_{tag}.pdf"),
    ]
    errors = []
    for fn, data_arg, fname in jobs:
        t0 = time.monotonic()
        try:
            fn(data_arg, str(out_dir / fname))
            elapsed = time.monotonic() - t0
            log.debug("%s: %.2fs", fname, elapsed)
            print(f"    OK  {fname}")
        except Exception as e:
            log.exception("Error generating %s", fname)
            print(f"    FAIL {fname}: {e}")
            errors.append(fname)

    # account statements: different signature
    try:
        t0 = time.monotonic()
        render_account_statements_pdf(stmts, str(out_dir / f"account_statements_{tag}.pdf"))
        log.debug("account_statements: %.2fs", time.monotonic() - t0)
        print(f"    OK  account_statements_{tag}.pdf")
    except Exception as e:
        log.exception("Error generating account_statements")
        print(f"    FAIL account_statements_{tag}.pdf: {e}")
        errors.append(f"account_statements_{tag}.pdf")

    # ── Single Excel workbook
    print("\n[*] Generating Excel (17 core sheets)...")
    try:
        t0 = time.monotonic()
        render_all_xlsx_full(
            {
                "cf": cf,
                "ie": ie,
                "reg": reg,
                "net_worth": nw,
                "statements": stmts,
                "tax": tax,
                "trend": trend,
                "tagged": tagged,
                "budget": budget,
                "bills": bills,
                "savings": savings,
                "liabilities": liab,
                "kpi": kpi,
                "yoy": yoy,
                "cumulative_cf": cum_cf,
                "concentration": conc,
                "summary": summary,
            },
            str(out_dir / f"firefly_reports_complete_{tag}.xlsx"),
        )
        log.debug("Excel complete: %.2fs", time.monotonic() - t0)
        print(f"    OK  firefly_reports_complete_{tag}.xlsx")
    except Exception as e:
        log.exception("Error generating Excel")
        print(f"    FAIL firefly_reports_complete_{tag}.xlsx: {e}")
        errors.append(f"firefly_reports_complete_{tag}.xlsx")

    if errors:
        print(f"\n[!] {len(errors)} files failed: {', '.join(errors)}")
        if not args.debug:
            print("    Rerun with --debug for detailed error logs.")
    else:
        print(f"\nDone. Output: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
