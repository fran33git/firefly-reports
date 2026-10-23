#!/usr/bin/env python3
"""
Firefly III Report Generator
─────────────────────────────
Generates all 26 financial reports (PDF + Excel) from Firefly III data.

Usage:
  firefly-reports --url https://firefly.yourdomain.com \\
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
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

from firefly_reports import i18n
from firefly_reports.config import load_config
from firefly_reports.errors import ConfigurationError
from firefly_reports.firefly_client import FireflyClient
from firefly_reports.ledger.cli import add_export_parser, run_export_command
from firefly_reports.reports import events
from firefly_reports.reports.fetch import fetch_source_data
from firefly_reports.reports.options import GlobalFilters, Period, ReportOptions
from firefly_reports.reports.pipeline import build_all, write_outputs
from firefly_reports.reports.spec import ReportContext


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments. Supports the 'init' subcommand and report generation."""
    p = argparse.ArgumentParser(
        description="Firefly III -> PDF + Excel report generator (26 reports)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command")
    sub.add_parser("init", help="Create ./firefly-reports.toml interactively")
    add_export_parser(sub)

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

    content = "\n".join(lines) + "\n"
    if token:
        # Create atomically with owner-only permissions before any bytes
        # are written, so the token is never briefly world/group-readable
        # (same convention as ~/.netrc or ~/.pgpass). Also re-applied via
        # fchmod in case a stale, more permissive file already existed.
        fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        config_path.write_text(content, encoding="utf-8")
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


def cmd_export(args: argparse.Namespace, config: dict[str, Any]) -> int:
    """Run ``export <format>``; returns the process exit code."""

    def make_client() -> FireflyClient:
        url, token = _resolve_credentials(args, config)
        return FireflyClient(url, token, logging.getLogger("firefly_reports.client"))

    return run_export_command(args, make_client, _parse_cli_date)


def _console(event: str, /, **f: object) -> None:
    """Map pipeline progress events to the console lines of the 1.x output."""
    if event == events.FETCH_START:
        print("[*] Downloading data...")
    elif event == events.FETCH_TRANSACTIONS:
        print(f"    -> {f['count']} transactions ({f['start']} -> {f['end']})")
    elif event == events.FETCH_TRANSACTIONS_PREV:
        print(f"    -> {f['count']} transactions previous year ({f['start']} -> {f['end']})")
    elif event == events.FETCH_FILTERS:
        print(f"    -> global filters: {f['before']} -> {f['after']} transactions")
    elif event == events.FETCH_ACCOUNTS:
        print(f"    -> {f['count']} asset accounts")
    elif event == events.FETCH_LIABILITIES:
        if f["count"]:
            print(f"    -> {f['count']} liabilities")
    elif event == events.FETCH_STATEMENTS:
        print(f"    -> Account statements: {f['count']} accounts")
    elif event == events.FETCH_BUDGETS:
        print(f"    -> {f['count']} budgets")
    elif event == events.FETCH_BILLS:
        print(f"    -> {f['count']} bills/subscriptions")
    elif event == events.FETCH_PIGGY_BANKS:
        print(f"    -> {f['count']} savings goals")
    elif event == events.FETCH_HISTORY:
        print(f"[*] Fetching historical data ({f['years']} years)...")
    elif event == events.FETCH_HISTORY_YEAR:
        print(f"    -> Year {f['year']}...")
    elif event == events.FETCH_LINKS_DEEP:
        print(f"    -> Deep-fetching {f['count']} linked transactions...")
    elif event == events.FETCH_DONE:
        print(f"    OK Download complete in {float(f['seconds']):.1f}s")  # type: ignore[arg-type]
    elif event == events.WRITE_PDF_START:
        print("[*] Generating PDF reports...")
    elif event == events.WRITE_XLSX_START:
        print("\n[*] Generating Excel...")
    elif event == events.WRITE_OK:
        print(f"    OK  {f['filename']}")
    elif event == events.WRITE_FAIL:
        print(f"    FAIL {f['filename']}: {f['error']}")
    elif event == events.WRITE_SKIPPED:
        print("    -- tagged_report skipped (use --tags TAG1,TAG2 to enable)")


def main():
    # Avoid UnicodeEncodeError on Windows consoles with legacy codepages
    # (e.g. cp1252): replace characters the console cannot encode.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
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
    if args.command == "export":
        code = cmd_export(args, config)
        if code:
            sys.exit(code)
        return

    filters_cfg = config.get("filters", {})

    year = args.year or config.get("year")
    if year and (args.start or args.end):
        print("Error: use either --year or --start/--end, not both.")
        sys.exit(1)
    if not year and (not args.start or not args.end):
        print("Error: provide --year YYYY (full year, all reports) or both --start and --end.")
        print("Run 'firefly-reports init' to create a config file.")
        sys.exit(1)

    url, token = _resolve_credentials(args, config)

    if year:
        fy = args.fiscal_year_start or filters_cfg.get("fiscal_year_start") or "01-01"
        try:
            period = Period.for_year(year, fy)
        except ConfigurationError as exc:
            print(f"Error: {exc}.")
            sys.exit(1)
        if (period.start.month, period.start.day) != (1, 1):
            print(f"[i] Fiscal year: {period.start} -> {period.end}")
    else:
        start = _parse_cli_date(args.start, "--start")
        end = _parse_cli_date(args.end, "--end")
        if start > end:
            print(f"Error: --start ({args.start}) must not be after --end ({args.end}).")
            sys.exit(1)
        period = Period.between(start, end)
        print("[i] Range mode: year-only reports skipped (yoy, historical, liquidity forecast)")

    # tags: CLI --tags wins; fall back to config file list
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    else:
        tags = config.get("tags", [])

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

    # -- Global filters (CLI flags override config [filters])
    filters = GlobalFilters(
        accounts_include=tuple(
            _csv_list(args.accounts_include)
            or [str(a) for a in filters_cfg.get("accounts_include", [])]
        ),
        accounts_exclude=tuple(
            _csv_list(args.accounts_exclude)
            or [str(a) for a in filters_cfg.get("accounts_exclude", [])]
        ),
        categories_include=tuple(
            _csv_list(args.categories_include)
            or [str(c) for c in filters_cfg.get("categories_include", [])]
        ),
        categories_exclude=tuple(
            _csv_list(args.categories_exclude)
            or [str(c) for c in filters_cfg.get("categories_exclude", [])]
        ),
        show_transfers=bool(not args.hide_transfers and filters_cfg.get("show_transfers", True)),
        reconciled_only=bool(args.reconciled_only or filters_cfg.get("reconciled_only", False)),
    )
    options = ReportOptions(
        owner=args.owner or config.get("owner", ""),
        currency=args.currency or config.get("currency", "€"),
        lang=lang,
        legacy=bool(legacy_report),
        tags=tuple(tags),
        all_tags=bool(all_tags_report),
        fetch_links=bool(fetch_links),
        historical_years=historical_years,
        deductible_keywords=tuple(deductible_keywords),
        filters=filters,
        pdf=not args.no_pdf,
        excel=not args.no_excel,
    )
    ctx = ReportContext(period, options)

    try:
        print(f"[*] Connecting to {url}")
        client = FireflyClient(url, token, logger=log, request_delay=link_delay)
        src = fetch_source_data(client, ctx, _console)

        print("\n[*] Processing data...")
        t0 = time.monotonic()
        built = build_all(src, ctx)
        cf, kpi, reg = built["cash_flow"], built["kpi_scorecard"], built["transaction_register"]
        log.debug("processing: %.2fs", time.monotonic() - t0)
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

        _generated, failed = write_outputs(built, ctx, out_dir, _console)
        errors = [f.filename for f in failed]

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
