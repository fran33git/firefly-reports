"""Beancount (v3) text writer."""

from __future__ import annotations

import re
from datetime import UTC
from decimal import Decimal

from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.model import Amount, Ledger, LedgerTransaction, Posting
from firefly_reports.ledger.writers.base import WriterOptions

_NEWLINES = re.compile(r"\s*[\r\n]+\s*")


def quote(text: str) -> str:
    """Render *text* as a Beancount string literal (escapes ``\\`` and ``"``)."""
    flat = _NEWLINES.sub(" ", text).strip()
    return '"' + flat.replace("\\", "\\\\").replace('"', '\\"') + '"'


def format_number(number: Decimal) -> str:
    """Plain positional notation, never scientific, keeping the original decimals."""
    return format(number, "f")


def _units(amount: Amount) -> str:
    return f"{format_number(amount.number)} {amount.currency}"


class BeancountWriter:
    """Renders a ``Ledger`` as Beancount text (single file or accounts + transactions)."""

    extension = ".beancount"

    def render(self, ledger: Ledger, options: WriterOptions) -> str:
        return self._file(
            options, [*self._directives(ledger, options), *self._transactions(ledger, options)]
        )

    def render_accounts(self, ledger: Ledger, options: WriterOptions) -> str:
        return self._file(options, self._directives(ledger, options))

    def render_transactions(self, ledger: Ledger, options: WriterOptions) -> str:
        # No timestamp here: the per-year files must stay byte-identical between
        # runs so that closed years are never rewritten.
        return self._file(options, self._transactions(ledger, options), stamp=False)

    @staticmethod
    def _file(options: WriterOptions, body: list[str], stamp: bool = True) -> str:
        labels = options.labels
        lines: list[str] = [f"; {labels.header_notice}"]
        if stamp and options.generated_at is not None:
            timestamp = options.generated_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            lines.append("; " + labels.header_generated.format(timestamp=timestamp))
        lines.append("")
        lines.extend(body)
        return "\n".join(lines).rstrip("\n") + "\n"

    def _transactions(self, ledger: Ledger, options: WriterOptions) -> list[str]:
        account_width, number_width = self._widths(ledger)
        lines: list[str] = []
        for tx in ledger.transactions:
            lines.extend(self._transaction(tx, options.labels, account_width, number_width))
            lines.append("")
        return lines

    # ---- directives -------------------------------------------------

    @staticmethod
    def _directives(ledger: Ledger, options: WriterOptions) -> list[str]:
        if not ledger.transactions:
            return []
        earliest = min(tx.date for tx in ledger.transactions)
        currencies = ledger.currencies_first_use()
        for cur in options.commodities:
            currencies.setdefault(cur, earliest)
        lines = [f"{d.isoformat()} commodity {cur}" for cur, d in sorted(currencies.items())]
        lines.append("")
        for account, first in ledger.accounts_first_use().items():
            lines.append(f"{first.isoformat()} open {account}")
            if account in ledger.ibans:
                lines.append(f"  iban: {quote(ledger.ibans[account])}")
        lines.append("")
        return lines

    # ---- transactions -----------------------------------------------

    @staticmethod
    def _widths(ledger: Ledger) -> tuple[int, int]:
        accounts = [p.account for tx in ledger.transactions for p in tx.postings]
        numbers = [
            format_number(p.amount.number) for tx in ledger.transactions for p in tx.postings
        ]
        return (max(map(len, accounts), default=0), max(map(len, numbers), default=0))

    def _transaction(
        self, tx: LedgerTransaction, labels: LedgerLabels, account_width: int, number_width: int
    ) -> list[str]:
        head = f"{tx.date.isoformat()} *"
        if tx.payee:
            head += f" {quote(tx.payee)}"
        head += f" {quote(tx.narration)}"
        for tag in tx.tags:
            head += f" #{tag}"
        for link in tx.links:
            head += f" ^{link}"
        lines = [head]
        lines.append(f"  {labels.meta_firefly_id}: {quote(tx.firefly_id)}")
        if tx.firefly_group_id is not None:
            lines.append(f"  {labels.meta_firefly_group_id}: {quote(tx.firefly_group_id)}")
        lines.extend(self._meta(labels, tx.category, tx.budget, tx.note, tx.extra, indent=2))
        for p in tx.postings:
            lines.extend(self._posting(p, labels, account_width, number_width))
        return lines

    def _posting(
        self, p: Posting, labels: LedgerLabels, account_width: int, number_width: int
    ) -> list[str]:
        number = format_number(p.amount.number).rjust(number_width)
        line = f"  {p.account.ljust(account_width)}  {number} {p.amount.currency}"
        if p.price_total is not None:
            line += f" @@ {_units(p.price_total)}"
        meta = self._meta(labels, p.category, p.budget, p.note, p.extra, indent=4)
        if p.payee:
            meta.insert(0, f"    payee: {quote(p.payee)}")
        return [line, *meta]

    @staticmethod
    def _meta(
        labels: LedgerLabels,
        category: str | None,
        budget: str | None,
        note: str | None,
        extra: tuple[tuple[str, str], ...],
        indent: int,
    ) -> list[str]:
        pad = " " * indent
        items = (
            (labels.meta_category, category),
            (labels.meta_budget, budget),
            (labels.meta_note, note),
        )
        fixed = tuple(sorted(extra))
        return [f"{pad}{key}: {quote(value)}" for key, value in (*items, *fixed) if value]
