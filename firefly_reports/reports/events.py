"""Progress events emitted by the fetch and write phases (the CLI maps them to console lines)."""

from __future__ import annotations

from typing import Protocol


class Progress(Protocol):
    """Receives ``(event, **fields)``; library callers may pass any callable or ``None``."""

    def __call__(self, event: str, /, **fields: object) -> None: ...


def no_progress(event: str, /, **fields: object) -> None:
    """The default sink: events are dropped."""


FETCH_START = "fetch.start"
FETCH_TRANSACTIONS = "fetch.transactions"  # count, start, end
FETCH_TRANSACTIONS_PREV = "fetch.transactions_prev"  # count, start, end
FETCH_FILTERS = "fetch.filters"  # before, after
FETCH_ACCOUNTS = "fetch.accounts"  # count
FETCH_LIABILITIES = "fetch.liabilities"  # count
FETCH_STATEMENTS = "fetch.statements"  # count
FETCH_BUDGETS = "fetch.budgets"  # count
FETCH_BILLS = "fetch.bills"  # count
FETCH_PIGGY_BANKS = "fetch.piggy_banks"  # count
FETCH_HISTORY = "fetch.history"  # years
FETCH_HISTORY_YEAR = "fetch.history_year"  # year
FETCH_LINKS_DEEP = "fetch.links_deep"  # count
FETCH_DONE = "fetch.done"  # seconds

WRITE_PDF_START = "write.pdf_start"
WRITE_XLSX_START = "write.xlsx_start"
WRITE_OK = "write.ok"  # filename
WRITE_FAIL = "write.fail"  # filename, error
WRITE_SKIPPED = "write.skipped"  # report, reason
