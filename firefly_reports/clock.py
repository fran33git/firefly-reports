"""Injectable clock: the current time can be frozen for deterministic output."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime

_frozen: ContextVar[datetime | None] = ContextVar("firefly_reports_frozen_now", default=None)


def now() -> datetime:
    """The current local time, or the frozen instant inside :func:`frozen`."""
    at = _frozen.get()
    return at if at is not None else datetime.now()


def today() -> date:
    return now().date()


@contextmanager
def frozen(at: datetime) -> Iterator[None]:
    """Make :func:`now` and :func:`today` return *at* inside the ``with`` block."""
    token = _frozen.set(at)
    try:
        yield
    finally:
        _frozen.reset(token)
