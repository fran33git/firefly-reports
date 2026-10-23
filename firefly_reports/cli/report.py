"""``report`` subcommand: PDF + Excel reports from a Firefly III instance."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping
from typing import Any

from firefly_reports import api
from firefly_reports.cli._console import ProgressPrinter, setup_debug_log
from firefly_reports.cli._options import (
    default_prompt,
    make_client,
    resolve_credentials,
    resolve_report_settings,
)
from firefly_reports.i18n import t

EXAMPLES = """examples:
  firefly-reports report --year 2025 --owner "Mario Rossi"
  firefly-reports report --start 2025-01-01 --end 2025-06-30 --no-excel
"""


def add_report_parser(sub: Any, common: argparse.ArgumentParser) -> None:
    """Register ``report``. Options shared with the root use SUPPRESS defaults so values
    given before the subcommand are kept."""
    p = sub.add_parser(
        "report",
        parents=[common],
        help="Generate the PDF + Excel reports from a Firefly III instance",
        description="Generate the PDF + Excel financial reports from a Firefly III instance.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sup = argparse.SUPPRESS
    p.add_argument("--start", default=sup, metavar="YYYY-MM-DD", help="Start date (YYYY-MM-DD)")
    p.add_argument("--end", default=sup, metavar="YYYY-MM-DD", help="End date   (YYYY-MM-DD)")
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
    p.add_argument("--out", default=sup, metavar="DIR", help="Output directory (default: ./output)")
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


def run_report(args: argparse.Namespace, config: Mapping[str, Any], env: Mapping[str, str]) -> int:
    """Run ``report``; returns the process exit code (3 when some files failed)."""
    settings = resolve_report_settings(args, config, env)
    period, options = settings.period, settings.options
    url, token = resolve_credentials(args.url, args.token, config, env, prompt=default_prompt)

    if period.year_mode:
        if (period.start.month, period.start.day) != (1, 1):
            print(f"[i] Fiscal year: {period.start} -> {period.end}")
    else:
        print("[i] Range mode: year-only reports skipped (yoy, historical, liquidity forecast)")

    out_dir = settings.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    log = setup_debug_log(settings.debug, out_dir, settings.debug_file)
    safe_args = {k: ("***" if k == "token" else v) for k, v in vars(args).items()}
    log.debug("Args: %s", safe_args)

    if not options.deductible_keywords and options.pdf:
        msg = "Warning: No 'deductible_keywords' defined in [tax] section of config. All expenses will be non-deductible."
        log.warning(msg)
        print(f"[*] {msg}")

    progress = ProgressPrinter()
    try:
        print(f"[*] Connecting to {url}")
        client = make_client(url, token, log, settings.link_delay)
        data = api.fetch_data(client, period, options, progress=progress)

        print("\n[*] Processing data...")
        built = api.build_reports(data, period, options)
        cf, kpi = built["cash_flow"], built["kpi_scorecard"]
        reg = built["transaction_register"]
        log.debug("cash_flow: in=%s out=%s net=%s", cf["total_in"], cf["total_out"], cf["net"])
        log.debug(
            "kpi: savings_rate=%s%% runway=%s months hhi=%s",
            kpi["savings_rate"],
            kpi["cash_runway"],
            kpi["hhi"],
        )

        currency = options.currency
        print(f"\n[*] Summary {period.start} -> {period.end}:")
        print(f"   Income:       {currency} {cf['total_in']:>12,.2f}")
        print(f"   Expenses:     {currency} {cf['total_out']:>12,.2f}")
        print(f"   Net:          {currency} {cf['net']:>12,.2f}")
        print(f"   Transactions: {reg['total_transactions']}")
        print(f"   Savings rate: {kpi['savings_rate']}%  |  Runway: {kpi['cash_runway']} months")
        print()

        result = api.write_reports(built, period, options, out_dir, progress=progress)
    except Exception:
        logging.getLogger("firefly_reports").exception("Fatal error")
        raise

    if result.failures:
        files = ", ".join(f.filename for f in result.failures)
        print(f"\n{t('cli.files_failed').format(count=len(result.failures), files=files)}")
        if not settings.debug:
            print(t("cli.rerun_debug"))
        return 3
    print(f"\n[*] All reports written to {out_dir.resolve()}")
    return 0
