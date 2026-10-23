"""Console behaviour of the CLI: stream setup, debug log, progress lines and errors."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from firefly_reports import clock
from firefly_reports.reports import events


def reconfigure_streams() -> None:
    """Avoid UnicodeEncodeError on Windows consoles with legacy codepages (e.g. cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")


def print_error(message: object) -> None:
    print(f"Error: {message}", file=sys.stderr)


def setup_debug_log(debug: bool, out_dir: Path, debug_file: str | None = None) -> logging.Logger:
    logger = logging.getLogger("firefly_reports")
    if not debug:
        if not any(isinstance(h, logging.NullHandler) for h in logger.handlers):
            logger.addHandler(logging.NullHandler())
        return logger

    logger.setLevel(logging.DEBUG)
    if debug_file:
        log_path = Path(debug_file)
    else:
        ts = clock.now().strftime("%Y%m%d_%H%M%S")
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


class ProgressPrinter:
    """Maps pipeline progress events to the console lines of the 1.x output."""

    def __call__(self, event: str, /, **f: object) -> None:
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
