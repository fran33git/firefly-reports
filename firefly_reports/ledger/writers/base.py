"""Writer interface and shared helpers (atomic file replacement)."""

from __future__ import annotations

import contextlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.model import Ledger


@dataclass(frozen=True)
class WriterOptions:
    labels: LedgerLabels
    # Extra commodities to declare even if no transaction uses them.
    commodities: tuple[str, ...] = ()
    # None -> omit the timestamp (byte-for-byte reproducible output).
    generated_at: datetime | None = None


class LedgerWriter(Protocol):
    """A text-format backend: turns the neutral ``Ledger`` into file content.

    All three methods return a complete file (header included):
    ``render`` is the self-contained single-file layout, ``render_accounts`` only
    the commodity/open directives and ``render_transactions`` only transactions
    (the two halves of the per-year layout).
    """

    extension: str

    def render(self, ledger: Ledger, options: WriterOptions) -> str: ...

    def render_accounts(self, ledger: Ledger, options: WriterOptions) -> str: ...

    def render_transactions(self, ledger: Ledger, options: WriterOptions) -> str: ...


def atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* via a temp file in the same directory + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
