"""``demo`` subcommand: every report from built-in sample data (no Firefly III needed)."""

from __future__ import annotations

import argparse
import sys
from typing import Any


def add_demo_parser(sub: Any, common: argparse.ArgumentParser) -> None:
    p = sub.add_parser(
        "demo",
        parents=[common],
        help="Generate every report from built-in sample data (no Firefly III needed)",
        description="Generate every report from built-in sample data (no Firefly III needed).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--out", default=argparse.SUPPRESS, metavar="DIR", help="Output directory")
    p.add_argument("--year", type=int, default=None, metavar="YYYY", help="Year (default: 2025)")


def run_demo(args: argparse.Namespace) -> int:
    """Temporary bridge to the 1.x demo runner (replaced by the pipeline in the next step)."""
    from firefly_reports.demo.__main__ import main as demo_main

    argv = ["demo", "--out", str(args.out or "./output"), "--lang", args.lang or "en"]
    if args.year:
        argv += ["--year", str(args.year)]
    old, sys.argv = sys.argv, argv
    try:
        demo_main()
    finally:
        sys.argv = old
    return 0
