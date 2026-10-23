"""``export`` subcommand: argument parser and command runner.

Credentials/client construction is injected by the caller.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import requests

from firefly_reports.errors import ConfigurationError
from firefly_reports.i18n import t
from firefly_reports.ledger.errors import LedgerError
from firefly_reports.ledger.export import (
    DEFAULT_MAP,
    LAYOUT_YEARLY,
    LAYOUTS,
    SCAFFOLD_APPEND,
    SCAFFOLD_OVERWRITE,
    SCAFFOLD_PRINT,
    ExportRequest,
    TransactionSource,
    run_export,
    run_scaffold,
)
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapping import load_ledger_config

DEFAULT_OUT = "ledger"
FORMATS = ["beancount"]


def add_export_parser(sub: Any, common: argparse.ArgumentParser) -> None:
    """Register ``export <format>``. The global options come from *common* and use SUPPRESS
    so values given before the subcommand (e.g. ``--lang it export beancount``) are not
    clobbered."""
    exp = sub.add_parser(
        "export",
        parents=[common],
        help="Export transactions to a plain-text ledger (beancount)",
        description="Export Firefly III transactions to a plain-text accounting ledger.",
        epilog="example: firefly-reports export beancount --scaffold",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    exp.add_argument("format", choices=FORMATS, help="Output format")
    sup = argparse.SUPPRESS
    exp.add_argument("--start", default=sup, help="Start date (YYYY-MM-DD), default: all")
    exp.add_argument("--end", default=sup, help="End date (YYYY-MM-DD), default: all")
    exp.add_argument(
        "--out",
        default=sup,
        metavar="DIR",
        help=f"Output directory (default: {DEFAULT_OUT}/)",
    )
    exp.add_argument(
        "--layout",
        choices=LAYOUTS,
        default=LAYOUT_YEARLY,
        help="yearly: accounts file + one file per year (default, whole history); "
        "single: one file (allows --start/--end)",
    )
    exp.add_argument(
        "--scaffold",
        action="store_true",
        help="First pass: create a draft mapping file from the Firefly accounts "
        "(never overwrites; writes no ledger files)",
    )
    exp.add_argument(
        "--append",
        action="store_true",
        help="With --scaffold: add the missing entries to the existing mapping file "
        "(keeps its lines, saves a .bak copy)",
    )
    exp.add_argument(
        "--overwrite",
        action="store_true",
        help="With --scaffold: replace the existing mapping file with a new draft "
        "(asks for confirmation, keeps a timestamped copy)",
    )
    exp.add_argument(
        "--map",
        default=None,
        metavar="YAML",
        help=f"Mapping file (default: ./{DEFAULT_MAP} if present)",
    )
    exp.add_argument(
        "--classify-by",
        choices=["category", "account"],
        default=None,
        help="Where expense/income accounts come from: the Firefly category (default) or "
        "the counterpart account",
    )
    exp.add_argument(
        "--allow-unmapped",
        action="store_true",
        help="Export even without a mapping file or with categories it does not list yet",
    )
    exp.add_argument("--dry-run", action="store_true", help="Print to stdout, write nothing")
    exp.add_argument("--validate", action="store_true", help="Run bean-check on the result")
    exp.add_argument(
        "--init",
        dest="init_files",
        action="store_true",
        help="Create main.beancount (and empty manual stubs) next to the output if missing",
    )
    exp.add_argument(
        "--no-timestamp",
        action="store_true",
        help="Omit the generation timestamp (byte-for-byte reproducible output)",
    )


def _stdin_is_interactive() -> bool:
    return sys.stdin.isatty()


def confirm_overwrite(path: Path) -> bool:
    """Ask the user to type the file name before a mapping file is replaced."""
    if not _stdin_is_interactive():
        print(t("ledger.err_overwrite_noninteractive").format(path=path), file=sys.stderr)
        return False
    print(t("ledger.overwrite_prompt").format(path=path, word=path.name), file=sys.stderr)
    try:
        answer = input("> ")
    except EOFError:
        return False
    return answer.strip() == path.name


def run_export_command(
    args: argparse.Namespace,
    make_client: Callable[[], TransactionSource],
    parse_date: Callable[[str, str], date],
) -> int:
    """Run ``export <format>`` from parsed arguments; returns the process exit code.

    *make_client* resolves credentials and builds the API client, *parse_date*
    parses a ``YYYY-MM-DD`` flag (exiting with a message on error). Both are
    injected by ``main.py`` so this module does not import it.
    """
    if (args.append or args.overwrite) and (not args.scaffold or (args.append and args.overwrite)):
        print(f"Error: {t('ledger.err_scaffold_flags')}", file=sys.stderr)
        return 1

    try:
        start = parse_date(args.start, "--start") if args.start else None
        end = parse_date(args.end, "--end") if args.end else None
    except ConfigurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if start and end and start > end:
        print(
            f"Error: {t('ledger.err_start_after_end').format(start=args.start, end=args.end)}",
            file=sys.stderr,
        )
        return 1

    if args.layout == LAYOUT_YEARLY and not args.scaffold and (start or end):
        print(f"Error: {t('ledger.err_yearly_filters')}", file=sys.stderr)
        return 1

    map_target = Path(args.map or DEFAULT_MAP)
    map_path: Path | None = map_target if map_target.is_file() else None
    if args.map and map_path is None and not args.scaffold:
        print(t("ledger.map_not_found").format(path=map_target), file=sys.stderr)
        return 1

    try:
        # --overwrite regenerates the draft as if there were no mapping: the file about to be
        # replaced must neither shape the draft nor need to be valid.
        regenerate = args.scaffold and args.overwrite
        ledger_config = load_ledger_config(None if regenerate else map_path)
        if args.classify_by:
            ledger_config = replace(ledger_config, classify_by=args.classify_by)
        labels = LedgerLabels.from_i18n(ledger_config.label_overrides)
        client = make_client()
        request = ExportRequest(
            start=start,
            end=end,
            out=Path(args.out or DEFAULT_OUT),
            config=ledger_config,
            layout=args.layout,
            dry_run=args.dry_run,
            validate=args.validate,
            init=args.init_files,
            timestamp=not args.no_timestamp,
            map_path=map_path,
            allow_unmapped=args.allow_unmapped,
        )
        print(t("ledger.fetching"), file=sys.stderr)
        if args.scaffold:
            mode = SCAFFOLD_APPEND if args.append else SCAFFOLD_PRINT
            if args.overwrite:
                mode = SCAFFOLD_OVERWRITE
            return run_scaffold(
                client, request, labels, map_target, mode=mode, confirm=confirm_overwrite
            )
        return run_export(client, request, labels)
    except LedgerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(t("ledger.err_request").format(reason=exc), file=sys.stderr)
        return 1
