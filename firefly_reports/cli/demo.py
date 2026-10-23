"""``demo`` subcommand: every report from built-in sample data (no Firefly III needed)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from firefly_reports.cli._console import setup_debug_log
from firefly_reports.cli._options import resolve_language
from firefly_reports.cli.report import execute
from firefly_reports.demo import data
from firefly_reports.demo.client import DemoClient
from firefly_reports.i18n import t
from firefly_reports.reports.options import Period, ReportOptions

DEFAULT_YEAR = 2025
DEDUCTIBLE = ("accountant", "software", "hardware", "marketing")


def add_demo_parser(sub: Any, common: argparse.ArgumentParser) -> None:
    p = sub.add_parser(
        "demo",
        parents=[common],
        help="Generate every report from built-in sample data (no Firefly III needed)",
        description="Generate every report from built-in sample data (no Firefly III needed).",
        epilog="example: firefly-reports demo --out ./output --lang it",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--out",
        default=argparse.SUPPRESS,
        metavar="DIR",
        help="Output directory (default: ./output)",
    )
    p.add_argument(
        "--year",
        type=int,
        default=None,
        metavar="YYYY",
        help=f"Full calendar year mode (default: {DEFAULT_YEAR})",
    )
    p.add_argument("--legacy-report", action="store_true", help="Use legacy PDF report styles")
    p.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    p.add_argument("--no-excel", action="store_true", help="Skip Excel generation")


def run_demo(args: argparse.Namespace, config: Mapping[str, Any], env: Mapping[str, str]) -> int:
    """Run the report pipeline on ``DemoClient``; returns the process exit code."""
    if getattr(args, "url", None) or getattr(args, "token", None):
        print(t("cli.warn_demo_ignores_credentials"), file=sys.stderr)
    period = Period.for_year(args.year or DEFAULT_YEAR)
    options = ReportOptions(
        owner=data.OWNER,
        currency="€",
        lang=resolve_language(args, config, env),
        legacy=bool(args.legacy_report),
        tags=("tax",),
        all_tags=True,
        deductible_keywords=DEDUCTIBLE,
        pdf=not args.no_pdf,
        excel=not args.no_excel,
    )
    out_dir = Path(args.out or "./output")
    out_dir.mkdir(parents=True, exist_ok=True)
    setup_debug_log(bool(args.debug), out_dir, args.debug_file)
    print("[*] Demo mode: built-in sample data (no Firefly III needed)")
    return execute(DemoClient(), period, options, out_dir, debug=bool(args.debug))
