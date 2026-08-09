#!/usr/bin/env python3
"""
Firefly III Report Generator
─────────────────────────────
Generates all 25 financial reports (PDF + Excel) from Firefly III data.

Usage:
  python main.py --url https://firefly.yourdomain.com \\
                 --token <PAT_TOKEN> \\
                 --start 2025-01-01 --end 2025-12-31 \\
                 --owner "Mario Rossi" --out ./output

Alternative env vars for --url and --token:
  FIREFLY_URL, FIREFLY_TOKEN
"""

import argparse
import getpass
import logging
import os
import sys
import time
import tomllib
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import i18n
from config import load_config
from data_processor import (
    apply_global_filters,
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
from dotenv import load_dotenv
from excel_exporter import render_all_xlsx_full
from firefly_client import FireflyClient
from pdf_exporter import (
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


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments. Supports the 'init' subcommand and report generation."""
    p = argparse.ArgumentParser(
        description="Firefly III -> PDF + Excel report generator (25 reports)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command")
    sub.add_parser("init", help="Create ./firefly-reports.toml interactively")

    p.add_argument("--url", default=None, help="Firefly III base URL")
    p.add_argument("--token", default=None, help="Personal Access Token")
    p.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    p.add_argument("--end", default=None, help="End date   (YYYY-MM-DD)")
    p.add_argument(
        "--year",
        type=int,
        default=None,
        metavar="YYYY",
        help="Full calendar year mode (unlocks year-only reports: YoY, historical, "
        "liquidity forecast). Mutually exclusive with --start/--end",
    )
    p.add_argument("--owner", default=None, help="Account owner name (report header)")
    p.add_argument("--currency", default=None, help="Currency symbol (default: €)")
    p.add_argument("--out", default=None, help="Output directory (default: ./output)")
    p.add_argument(
        "--lang", default=None, choices=["en", "it"], help="Output language (default: en)"
    )
    p.add_argument(
        "--years",
        type=int,
        choices=[3, 5],
        help="Number of years for historical analysis (default: 3)",
    )
    p.add_argument("--legacy-report", action="store_true", help="Use legacy PDF report styles")
    p.add_argument(
        "--tags", default="", metavar="TAG1,TAG2", help="Tags for the tagged transaction report"
    )
    p.add_argument(
        "--fetch-links",
        action="store_true",
        help="Fetch full details for linked transactions (slower)",
    )
    p.add_argument(
        "--link-delay",
        type=float,
        default=None,
        metavar="SEC",
        help="Seconds between requests when fetching linked transactions (default: 0.2)",
    )
    p.add_argument(
        "--all-tags", action="store_true", help="Generate a comprehensive report for all tags"
    )
    p.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    p.add_argument("--no-excel", action="store_true", help="Skip Excel generation")
    p.add_argument(
        "--accounts-include", default=None, metavar="ID1,ID2", help="Only these asset account IDs"
    )
    p.add_argument(
        "--accounts-exclude",
        default=None,
        metavar="ID1,ID2",
        help="Exclude these asset account IDs",
    )
    p.add_argument(
        "--categories-include", default=None, metavar="C1,C2", help="Only these categories"
    )
    p.add_argument(
        "--categories-exclude", default=None, metavar="C1,C2", help="Exclude these categories"
    )
    p.add_argument(
        "--hide-transfers", action="store_true", help="Drop transfer transactions from all reports"
    )
    p.add_argument("--reconciled-only", action="store_true", help="Only reconciled transactions")
    p.add_argument(
        "--fiscal-year-start",
        default=None,
        metavar="MM-DD",
        help="Fiscal year start (year mode only, default: 01-01)",
    )
    p.add_argument("--debug", action="store_true", help="Enable debug log to file")
    p.add_argument(
        "--debug-file",
        default=None,
        metavar="PATH",
        help="Log file path (default: <out>/debug_<timestamp>.log)",
    )
    return p.parse_args()


def _resolve_credentials(args: argparse.Namespace, config: dict[str, Any]) -> tuple[str, str]:
    """Resolve URL and token: CLI arg > env var > config file > interactive prompt.

    Returns:
        Tuple of (url, token). Exits with an error message if either is missing
        in a non-interactive context.
    """
    url = (args.url or os.getenv("FIREFLY_URL") or config.get("url") or "").strip()
    token = (args.token or os.getenv("FIREFLY_TOKEN") or config.get("token") or "").strip()

    if not url:
        print(
            "Error: Firefly III URL is required. Use --url, set FIREFLY_URL, or add url to firefly-reports.toml."
        )
        sys.exit(1)

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        print(
            f"Error: invalid Firefly III URL '{url}'. "
            "It must include the scheme, e.g. https://firefly.example.com"
        )
        sys.exit(1)

    if not token:
        if sys.stdin.isatty():
            token = getpass.getpass("Firefly III Personal Access Token: ").strip()
        if not token:
            print(
                "Error: token is required. Use --token, set FIREFLY_TOKEN, "
                "add it to a .env file, or add token to firefly-reports.toml."
            )
            sys.exit(1)

    return url, token


def _parse_cli_date(value: str, flag: str) -> date:
    """Parse a CLI date string (YYYY-MM-DD) or exit with a clear error."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        print(f"Error: invalid date for {flag}: '{value}' (expected format YYYY-MM-DD).")
        sys.exit(1)


def _csv_list(value: str | None) -> list[str]:
    """Split a comma-separated CLI option into a list of non-empty strings."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _setup_debug_log(debug: bool, out_dir: Path, debug_file: str | None = None) -> logging.Logger:
    logger = logging.getLogger("firefly_reports")
    if not debug:
        logger.addHandler(logging.NullHandler())
        return logger

    logger.setLevel(logging.DEBUG)
    if debug_file:
        log_path = Path(debug_file)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
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


def _prev_year_dates(start: date, end: date):
    """Returns (start-1year, end-1year), handling Feb 29."""

    def safe_replace(d):
        try:
            return d.replace(year=d.year - 1)
        except ValueError:
            return d.replace(year=d.year - 1, day=28)

    return safe_replace(start), safe_replace(end)


def cmd_init() -> None:
    """Generate ./firefly-reports.toml interactively."""
    config_path = Path("./firefly-reports.toml")

    if config_path.exists():
        answer = input("Config file already exists. Overwrite? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted. Existing config unchanged.")
            return

    print("Firefly Reports — Config Setup")
    print("(Press Enter to keep the shown default)\n")

    url = input("URL [https://firefly.example.com]: ").strip()
    if not url:
        url = "https://firefly.example.com"

    token = getpass.getpass("Token (leave blank to enter at runtime): ").strip()

    owner = input("Owner name []: ").strip()

    currency = input("Currency symbol [€]: ").strip()
    if not currency:
        currency = "€"

    lang = input("Language [en/it, default en]: ").strip().lower()
    if lang not in ("en", "it"):
        lang = "en"

    legacy_report = input("Use legacy report styles? [y/N]: ").strip().lower() == "y"

    out = input("Output directory [./output]: ").strip()
    if not out:
        out = "./output"

    tags_raw = input("Tags for tagged report (comma-separated) []: ").strip()
    tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]

    lines = [
        "# firefly-reports.toml",
        "# WARNING: do not commit this file if it contains a token.",
        "# Ensure firefly-reports.toml is listed in your .gitignore.",
        "",
        f'url      = "{url}"',
    ]
    if token:
        lines.append(f'token    = "{token}"')
    else:
        lines.append('# token = ""  # leave blank to be prompted at runtime')
    lines += [
        f'owner    = "{owner}"',
        f'currency = "{currency}"',
        f'lang     = "{lang}"',
        f"legacy_report = {'true' if legacy_report else 'false'}",
        f'out      = "{out}"',
    ]
    if tags:
        tags_toml = ", ".join(f'"{tag}"' for tag in tags)
        lines.append(f"tags     = [{tags_toml}]")
    else:
        lines.append("tags     = []")

    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nConfig written to {config_path.resolve()}")

    if token:
        gitignore = Path(".gitignore")
        covered = False
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            covered = any(
                line.strip() in ("firefly-reports.toml", "*.toml")
                for line in content.splitlines()
                if not line.startswith("#")
            )
        if not covered:
            print(
                "\nWARNING: 'firefly-reports.toml' contains a token but is not "
                "listed in .gitignore.\n"
                "         Add the following line to .gitignore to prevent "
                "accidental commits:\n"
                "         firefly-reports.toml"
            )


def main():
    load_dotenv()
    args = parse_args()
    try:
        config = load_config()
    except tomllib.TOMLDecodeError as e:
        print(f"Config error: firefly-reports.toml is malformed — {e}", file=sys.stderr)
        sys.exit(1)

    # i18n resolution: CLI > config file > env var > default "en"
    lang = args.lang or config.get("lang") or os.getenv("FIREFLY_LANG", "en")
    i18n.load(lang)

    # Legacy report resolution: CLI > Config > Env > Default (False)
    legacy_report = (
        args.legacy_report
        or config.get("legacy_report")
        or os.getenv("FIREFLY_LEGACY_REPORT", "false").lower() in ("true", "1")
    )

    reports_config = config.get("reports", {})
    historical_years = args.years or reports_config.get("historical_years") or 3
    fetch_links = args.fetch_links or reports_config.get("fetch_links") or False
    all_tags_report = args.all_tags or reports_config.get("all_tags_report") or False
    link_delay = (
        args.link_delay if args.link_delay is not None else reports_config.get("link_delay", 0.2)
    )

    if args.command == "init":
        cmd_init()
        return

    filters_cfg = config.get("filters", {})

    year = args.year or config.get("year")
    if year and (args.start or args.end):
        print("Error: use either --year or --start/--end, not both.")
        sys.exit(1)
    if not year and (not args.start or not args.end):
        print("Error: provide --year YYYY (full year, all reports) or both --start and --end.")
        print("Run 'python main.py init' to create a config file.")
        sys.exit(1)

    url, token = _resolve_credentials(args, config)

    year_mode = year is not None
    if year_mode:
        try:
            year_int = int(year)
        except (TypeError, ValueError):
            print(f"Error: invalid year '{year}' (expected e.g. 2025).")
            sys.exit(1)
        if not 1900 <= year_int <= 2100:
            print(f"Error: invalid year '{year}' (expected 1900-2100).")
            sys.exit(1)
        fy = args.fiscal_year_start or filters_cfg.get("fiscal_year_start") or "01-01"
        try:
            # Parse against a leap year so 02-29 is accepted and no
            # year-less parsing deprecation warning is raised (CPython #70647).
            fy_dt = datetime.strptime(f"2000-{fy}", "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: invalid fiscal year start '{fy}' (expected MM-DD).")
            sys.exit(1)
        try:
            start = date(year_int, fy_dt.month, fy_dt.day)
        except ValueError:
            print(
                f"Error: fiscal year start '{fy}' is not valid for year {year_int} "
                "(02-29 requires a leap year)."
            )
            sys.exit(1)
        try:
            fy_next = date(year_int + 1, fy_dt.month, fy_dt.day)
        except ValueError:
            # 02-29 anniversary in a non-leap following year → fiscal year
            # ends on 02-28.
            fy_next = date(year_int + 1, 3, 1)
        end = fy_next - timedelta(days=1)
        if (start.month, start.day) != (1, 1):
            print(f"[i] Fiscal year: {start} -> {end}")
    else:
        start = _parse_cli_date(args.start, "--start")
        end = _parse_cli_date(args.end, "--end")
        if start > end:
            print(f"Error: --start ({args.start}) must not be after --end ({args.end}).")
            sys.exit(1)
        print("[i] Range mode: year-only reports skipped (yoy, historical, liquidity forecast)")

    # tags: CLI --tags wins; fall back to config file list
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    else:
        tags = config.get("tags", [])

    owner = args.owner or config.get("owner", "")
    currency = args.currency or config.get("currency", "€")
    lang = args.lang or config.get("lang", "en")
    out_dir = Path(args.out or config.get("out", "./output"))
    out_dir.mkdir(parents=True, exist_ok=True)

    log = _setup_debug_log(args.debug, out_dir, args.debug_file)
    safe_args = {k: ("***" if k == "token" else v) for k, v in vars(args).items()}
    log.debug("Args: %s", safe_args)

    tax_config = config.get("tax", {})
    deductible_keywords = tax_config.get("deductible_keywords", [])

    if not deductible_keywords and not args.no_pdf:
        msg = "Warning: No 'deductible_keywords' defined in [tax] section of config. All expenses will be non-deductible."
        log.warning(msg)
        print(f"[*] {msg}")

    period_tag = f"{start}__{end}"

    try:
        print(f"[*] Connecting to {url}")
        client = FireflyClient(url, token, logger=log, request_delay=link_delay)

        # -- Current period transactions
        print("[*] Downloading data...")
        t0 = time.monotonic()
        transactions = client.get_transactions(start, end)
        log.debug("get_transactions: %.2fs, %d tx", time.monotonic() - t0, len(transactions))
        print(f"    -> {len(transactions)} transactions ({start} -> {end})")

        # -- Previous year transactions (YoY — year mode only)
        transactions_prev: list[dict[str, Any]] = []
        start_prev, end_prev = _prev_year_dates(start, end)
        if year_mode:
            transactions_prev = client.get_transactions(start_prev, end_prev)
            log.debug("transactions_prev: %d tx", len(transactions_prev))
            print(
                f"    -> {len(transactions_prev)} transactions previous year "
                f"({start_prev} -> {end_prev})"
            )

        # -- Global filters (spec sez. 5 — CLI flags override config [filters])
        accounts_include = _csv_list(args.accounts_include) or [
            str(a) for a in filters_cfg.get("accounts_include", [])
        ]
        accounts_exclude = _csv_list(args.accounts_exclude) or [
            str(a) for a in filters_cfg.get("accounts_exclude", [])
        ]
        categories_include = _csv_list(args.categories_include) or [
            str(c) for c in filters_cfg.get("categories_include", [])
        ]
        categories_exclude = _csv_list(args.categories_exclude) or [
            str(c) for c in filters_cfg.get("categories_exclude", [])
        ]
        show_transfers = not args.hide_transfers and filters_cfg.get("show_transfers", True)
        reconciled_only = bool(args.reconciled_only or filters_cfg.get("reconciled_only", False))

        if (
            accounts_include
            or accounts_exclude
            or categories_include
            or categories_exclude
            or not show_transfers
            or reconciled_only
        ):
            before = len(transactions)
            transactions = apply_global_filters(
                transactions,
                accounts_include=accounts_include,
                accounts_exclude=accounts_exclude,
                categories_include=categories_include,
                categories_exclude=categories_exclude,
                show_transfers=show_transfers,
                show_reconciled_only=reconciled_only,
            )
            transactions_prev = apply_global_filters(
                transactions_prev,
                accounts_include=accounts_include,
                accounts_exclude=accounts_exclude,
                categories_include=categories_include,
                categories_exclude=categories_exclude,
                show_transfers=show_transfers,
                show_reconciled_only=reconciled_only,
            )
            print(f"    -> global filters: {before} -> {len(transactions)} transactions")

        # -- Asset accounts
        accounts = client.get_asset_accounts()
        if accounts_include or accounts_exclude:
            accounts = [
                a
                for a in accounts
                if (not accounts_include or str(a.get("id", "")) in accounts_include)
                and str(a.get("id", "")) not in accounts_exclude
            ]
        log.debug("asset_accounts: %d", len(accounts))
        print(f"    -> {len(accounts)} asset accounts")

        # -- Liabilities
        liability_accounts = client.get_liability_accounts()
        log.debug("liability_accounts: %d", len(liability_accounts))
        if liability_accounts:
            print(f"    -> {len(liability_accounts)} liabilities")

        # -- Transactions per account (account statements)
        txn_by_account = {}
        for acc in accounts:
            acc_id = str(acc.get("id", ""))
            txn_by_account[acc_id] = client.get_account_transactions(int(acc_id), start, end)
        log.debug("txn_by_account: %d accounts", len(txn_by_account))
        print(f"    -> Account statements: {len(accounts)} accounts")

        # -- Transactions per liability
        liab_txn = {}
        for acc in liability_accounts:
            acc_id = str(acc.get("id", ""))
            liab_txn[acc_id] = client.get_liability_transactions(int(acc_id), start, end)

        # -- Budgets
        budgets = client.get_budgets()
        budget_limits = {}
        for b in budgets:
            bid = str(b.get("id", ""))
            budget_limits[bid] = client.get_budget_limits(bid, start, end)
        log.debug("budgets: %d", len(budgets))
        print(f"    -> {len(budgets)} budgets")

        # -- Bills
        bills = client.get_bills()
        bill_txn = {}
        for bill in bills:
            bid = str(bill.get("id", ""))
            bill_txn[bid] = client.get_bill_transactions(bid, start, end)
        log.debug("bills: %d", len(bills))
        print(f"    -> {len(bills)} bills/subscriptions")

        # -- Piggy banks
        piggy_banks = client.get_piggy_banks()
        log.debug("piggy_banks: %d", len(piggy_banks))
        print(f"    -> {len(piggy_banks)} savings goals")

        # -- Instance info (summary report)
        about = client.get_about()
        about_user = client.get_about_user()
        log.debug("about: version=%s", about.get("version", "?"))

        # -- Historical Data (year mode only, if not legacy)
        hist_data = []
        if year_mode and not legacy_report:
            print(f"[*] Fetching historical data ({historical_years} years)...")
            current_year = start.year
            for i in range(0, historical_years):  # include the selected year itself
                y = current_year - i
                print(f"    -> Year {y}...")
                totals = client.get_annual_totals(y)
                cats = client.get_top_categories_for_year(y)
                hist_data.append(
                    {
                        "year": y,
                        "income": totals["income"],
                        "expense": totals["expense"],
                        "top_categories": cats,
                    }
                )

        elapsed_fetch = time.monotonic() - t0
        print(f"    OK Download complete in {elapsed_fetch:.1f}s")

        # -- Processing data
        print("\n[*] Processing data...")
        t0 = time.monotonic()

        cf = build_cash_flow(
            transactions, start, end, owner, currency, accounts, liability_accounts
        )
        ie = build_income_expense(transactions, start, end, owner, currency)
        reg = build_transaction_register(transactions, start, end, owner, currency)
        nw = build_net_worth(accounts, end, owner, currency)
        stmts = build_account_statements(accounts, txn_by_account, start, end, owner, currency)
        tax = build_tax_summary(
            transactions,
            start.year,
            owner_name=owner,
            currency_symbol=currency,
            deductible_keywords=deductible_keywords,
        )
        trend = build_expense_trend(transactions, start, end, owner, currency)
        tagged = build_tagged_report(transactions, tags, start, end, owner, currency)
        budget = build_budget_vs_actual(
            budgets, budget_limits, transactions, start, end, owner, currency
        )
        bills_d = build_bills_report(bills, bill_txn, start, end, owner, currency)
        savings = build_savings_goals(piggy_banks, end, owner, currency)
        liab = build_liabilities_report(
            liability_accounts, liab_txn, end, start, end, owner, currency
        )
        kpi = build_kpi_scorecard(
            transactions, accounts, liability_accounts, start, end, owner, currency
        )
        yoy = (
            build_yoy_comparison(
                transactions, transactions_prev, start, end, start_prev, end_prev, owner, currency
            )
            if year_mode
            else None
        )
        cum_cf = build_cumulative_cashflow(transactions, start, end, owner, currency)
        conc = build_income_concentration(transactions, start, end, owner, currency)
        audit = (
            build_audit_log(transactions, start, end, owner, currency) if legacy_report else None
        )
        summary = build_summary(
            transactions,
            accounts,
            liability_accounts,
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
        journal = build_journal(transactions, start, end, owner, currency)
        forecast = build_performance_forecast(
            budgets, budget_limits, transactions, start, end, owner, currency
        )

        # Strategic Reports
        hist_report = None
        if hist_data:
            hist_dict = {
                d["year"]: {
                    "total_income": d["income"],
                    "total_expense": d["expense"],
                    "net_savings": d["income"] - d["expense"],
                    "top_categories": d["top_categories"],
                }
                for d in hist_data
            }
            hist_report = build_historical_report(hist_dict, owner, currency)

        liquid_forecast = None
        if year_mode and not legacy_report:
            # Only positive balances: consistent with build_kpi_scorecard logic.
            # Negative asset accounts (e.g. credit cards) reduce runway separately.
            liquid_assets = sum(
                (
                    Decimal(str(acc.get("attributes", acc).get("current_balance", 0)))
                    for acc in accounts
                    if Decimal(str(acc.get("attributes", acc).get("current_balance", 0))) > 0
                ),
                Decimal(0),
            )
            liquid_forecast = build_liquidity_forecast(
                current_balance=liquid_assets,
                avg_income=kpi["avg_monthly_in"],
                avg_variable_expense=kpi["avg_monthly_out"],
                bills=bills,
                end_date=end,
                owner_name=owner,
                currency_symbol=currency,
            )

        # Ledgers
        cat_ledger = build_category_ledger(transactions, start, end, owner, currency)
        payee_ledger = build_payee_ledger(transactions, start, end, owner, currency)

        # Linkage Audit (with deep-fetch if enabled)
        links = client.get_transaction_links()
        log.debug("transaction_links: %d", len(links))
        linkage_txns = transactions
        if fetch_links:
            linked_ids = set()
            for lnk in links:
                if lnk.get("inward_id"):
                    linked_ids.add(str(lnk["inward_id"]))
                if lnk.get("outward_id"):
                    linked_ids.add(str(lnk["outward_id"]))

            known_ids = {
                str(tx.get("id") or tx.get("transaction_journal_id")) for tx in transactions
            }
            missing_ids = [tid for tid in linked_ids if tid and tid not in known_ids]

            if missing_ids:
                print(f"    -> Deep-fetching {len(missing_ids)} linked transactions...")
                fetched = client.fetch_link_details(missing_ids)
                linkage_txns = transactions + fetched

        linkage = build_linkage_report(linkage_txns, links, start, end, owner, currency)

        # All Tags Report
        all_tags_data = None
        if all_tags_report:
            all_tags_data = build_all_tags_report(transactions, start, end, owner, currency)

        log.debug("processing: %.2fs", time.monotonic() - t0)
        log.debug("cash_flow: in=%s out=%s net=%s", cf["total_in"], cf["total_out"], cf["net"])
        log.debug(
            "kpi: savings_rate=%s%% runway=%s months hhi=%s",
            kpi["savings_rate"],
            kpi["cash_runway"],
            kpi["hhi"],
        )

        print(f"\n[*] Summary {start} -> {end}:")
        print(f"   Income:       {currency} {cf['total_in']:>12,.2f}")
        print(f"   Expenses:     {currency} {cf['total_out']:>12,.2f}")
        print(f"   Net:          {currency} {cf['net']:>12,.2f}")
        print(f"   Transactions: {reg['total_transactions']}")
        print(f"   Savings rate: {kpi['savings_rate']}%  |  Runway: {kpi['cash_runway']} months")
        print()

        errors = []

        # -- PDF
        if not args.no_pdf:
            print("[*] Generating PDF reports...")

            legacy = legacy_report  # Resolved earlier in main()

            jobs = [
                (render_cash_flow_pdf, cf, f"cash_flow_{period_tag}.pdf"),
                (render_income_expense_pdf, ie, f"income_expense_{period_tag}.pdf"),
                (render_transaction_register_pdf, reg, f"transaction_register_{period_tag}.pdf"),
                (render_net_worth_pdf, nw, f"net_worth_{period_tag}.pdf"),
                (render_tax_summary_pdf, tax, f"tax_summary_{start.year}.pdf"),
                (render_expense_trend_pdf, trend, f"expense_trend_{period_tag}.pdf"),
                (render_budget_vs_actual_pdf, budget, f"budget_vs_actual_{period_tag}.pdf"),
                (render_bills_pdf, bills_d, f"bills_{period_tag}.pdf"),
                (render_savings_goals_pdf, savings, f"savings_goals_{period_tag}.pdf"),
                (render_liabilities_pdf, liab, f"liabilities_{period_tag}.pdf"),
                (render_kpi_scorecard_pdf, kpi, f"kpi_scorecard_{period_tag}.pdf"),
                (render_cumulative_cashflow_pdf, cum_cf, f"cumulative_cashflow_{period_tag}.pdf"),
                (render_income_concentration_pdf, conc, f"income_concentration_{period_tag}.pdf"),
                (
                    render_income_expense_dashboard_pdf,
                    {**ie, "monthly_trend": kpi["monthly_trend"]},
                    f"dashboard_income_expense_{period_tag}.pdf",
                ),
                (render_kpi_trend_dashboard_pdf, kpi, f"dashboard_kpi_trend_{period_tag}.pdf"),
            ]

            if yoy:
                jobs.append((render_yoy_pdf, yoy, f"yoy_{start_prev.year}_vs_{start.year}.pdf"))

            if legacy and audit is not None:
                jobs.append((render_audit_log_pdf, audit, f"audit_log_{period_tag}.pdf"))

            if not legacy:
                jobs += [
                    (render_summary_pdf, summary, f"summary_{period_tag}.pdf"),
                    (render_journal_pdf, journal, f"journal_{period_tag}.pdf"),
                    (render_forecast_pdf, forecast, f"budget_forecast_{period_tag}.pdf"),
                    (render_category_ledger_pdf, cat_ledger, f"ledger_category_{period_tag}.pdf"),
                    (render_payee_ledger_pdf, payee_ledger, f"ledger_payee_{period_tag}.pdf"),
                ]

                # Only include linkage audit if there are actually linked transactions or fetch_links is on
                if linkage["groups"] or fetch_links:
                    jobs.append(
                        (render_linkage_audit_pdf, linkage, f"audit_linkage_{period_tag}.pdf")
                    )

                if all_tags_report and all_tags_data:
                    jobs.append(
                        (render_all_tags_pdf, all_tags_data, f"ledger_all_tags_{period_tag}.pdf")
                    )

                if hist_report:
                    jobs.append(
                        (
                            render_historical_report_pdf,
                            hist_report,
                            f"historical_growth_{period_tag}.pdf",
                        )
                    )

                if liquid_forecast:
                    jobs.append(
                        (
                            render_liquidity_forecast_pdf,
                            liquid_forecast,
                            f"liquidity_forecast_{period_tag}.pdf",
                        )
                    )

            for render_fn, data, fname in jobs:
                t0 = time.monotonic()
                try:
                    render_fn(data, str(out_dir / fname), legacy=legacy)
                    log.debug("%s: %.2fs", fname, time.monotonic() - t0)
                    print(f"    OK  {fname}")
                except Exception as e:
                    log.exception("Error generating %s", fname)
                    print(f"    FAIL {fname}: {e}")
                    errors.append(fname)

            # Account statements (different signature: receives list)
            fname = f"account_statements_{period_tag}.pdf"
            t0 = time.monotonic()
            try:
                render_account_statements_pdf(stmts, str(out_dir / fname), legacy=legacy)
                log.debug("%s: %.2fs", fname, time.monotonic() - t0)
                print(f"    OK  {fname}")
            except Exception as e:
                log.exception("Error generating %s", fname)
                print(f"    FAIL {fname}: {e}")
                errors.append(fname)

            # Tagged report (only if --tags specified)
            if tags:
                tags_slug = "_".join(tags)[:30]
                fname = f"tagged_{tags_slug}_{period_tag}.pdf"
                t0 = time.monotonic()
                try:
                    render_tagged_report_pdf(tagged, str(out_dir / fname), legacy=legacy)
                    log.debug("%s: %.2fs", fname, time.monotonic() - t0)
                    print(f"    OK  {fname}")
                except Exception as e:
                    log.exception("Error generating %s", fname)
                    print(f"    FAIL {fname}: {e}")
                    errors.append(fname)
            else:
                print("    -- tagged_report skipped (use --tags TAG1,TAG2 to enable)")

        # -- Excel
        if not args.no_excel:
            print("\n[*] Generating Excel...")
            xl_path = out_dir / f"firefly_reports_{period_tag}.xlsx"
            t0 = time.monotonic()
            try:
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
                        "bills": bills_d,
                        "savings": savings,
                        "liabilities": liab,
                        "kpi": kpi,
                        "yoy": yoy,
                        "cumulative_cf": cum_cf,
                        "concentration": conc,
                        "summary": summary,
                    },
                    str(xl_path),
                )
                log.debug("Excel: %.2fs -> %s", time.monotonic() - t0, xl_path)
                print(f"    OK  {xl_path.name}")
            except Exception as e:
                log.exception("Error generating Excel")
                print(f"    FAIL {xl_path.name}: {e}")
                errors.append(xl_path.name)

        if errors:
            print(f"\n[!] {len(errors)} files failed: {', '.join(errors)}")
            if not args.debug:
                print("    -> Re-run with --debug for detailed error log.")
        else:
            print(f"\n[*] All reports written to {out_dir.resolve()}")

    except Exception:
        log.exception("Fatal error")
        raise


if __name__ == "__main__":
    main()
