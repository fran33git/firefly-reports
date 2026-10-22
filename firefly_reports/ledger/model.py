"""Neutral, format-independent ledger model.

Everything here is a plain frozen dataclass: no I/O, no Firefly specifics, no
output syntax. Writers (Beancount today, hledger tomorrow) consume this model.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

# Metadata keys written verbatim (not translated, not overridable through ``labels:``).
FIXED_META_KEYS = (
    "bill",
    "reference",
    "external_id",
    "external_url",
    "book_date",
    "interest_date",
)


@dataclass(frozen=True)
class Amount:
    number: Decimal
    currency: str


@dataclass(frozen=True)
class Posting:
    account: str
    amount: Amount
    # Total price of the posting expressed in another currency (Beancount ``@@``).
    price_total: Amount | None = None
    category: str | None = None
    budget: str | None = None
    note: str | None = None
    # Counterpart name, set only when the splits of a group have different counterparts.
    payee: str | None = None
    # Fixed-key metadata (see ``FIXED_META_KEYS``) that differs between splits.
    extra: tuple[tuple[str, str], ...] = ()

    @property
    def weight(self) -> Amount:
        """Amount that counts towards the transaction balance."""
        if self.price_total is None:
            return self.amount
        sign = -1 if self.amount.number < 0 else 1
        return Amount(self.price_total.number.copy_abs() * sign, self.price_total.currency)


@dataclass(frozen=True)
class LedgerTransaction:
    date: dt.date
    narration: str
    postings: tuple[Posting, ...]
    firefly_id: str
    firefly_group_id: str | None = None
    payee: str | None = None
    tags: tuple[str, ...] = ()
    # Transaction-level metadata, only set when identical across all splits.
    category: str | None = None
    budget: str | None = None
    note: str | None = None
    # Fixed-key metadata that is identical across all splits.
    extra: tuple[tuple[str, str], ...] = ()
    # Beancount link names (``^name``) shared with the linked transactions.
    links: tuple[str, ...] = ()

    @property
    def sort_key(self) -> tuple[dt.date, int, str]:
        digits = self.firefly_id.isdigit()
        return (self.date, int(self.firefly_id) if digits else 0, self.firefly_id)

    def balance(self) -> dict[str, Decimal]:
        """Residual per currency; every value must be zero for a valid transaction."""
        totals: dict[str, Decimal] = {}
        for p in self.postings:
            w = p.weight
            totals[w.currency] = totals.get(w.currency, Decimal(0)) + w.number
        return totals


@dataclass(frozen=True)
class Ledger:
    transactions: tuple[LedgerTransaction, ...]
    # Ledger account -> IBAN, written on the ``open`` directive (accounts file only).
    ibans: Mapping[str, str] = field(default_factory=dict)
    # Firefly links dropped because one end is not part of the export.
    skipped_links: int = 0

    def by_year(self) -> dict[int, Ledger]:
        """Split into one ledger per calendar year, ordered by year."""
        years: dict[int, list[LedgerTransaction]] = {}
        for tx in self.transactions:
            years.setdefault(tx.date.year, []).append(tx)
        return {year: Ledger(tuple(txs)) for year, txs in sorted(years.items())}

    def accounts_first_use(self) -> dict[str, dt.date]:
        """Account -> date of the first transaction touching it, sorted by account."""
        first: dict[str, dt.date] = {}
        for tx in self.transactions:
            for p in tx.postings:
                if p.account not in first or tx.date < first[p.account]:
                    first[p.account] = tx.date
        return dict(sorted(first.items()))

    def currencies_first_use(self) -> dict[str, dt.date]:
        """Currency -> date of the first transaction using it (also as price), sorted."""
        first: dict[str, dt.date] = {}
        for tx in self.transactions:
            for p in tx.postings:
                currencies = [p.amount.currency]
                if p.price_total is not None:
                    currencies.append(p.price_total.currency)
                for cur in currencies:
                    if cur not in first or tx.date < first[cur]:
                        first[cur] = tx.date
        return dict(sorted(first.items()))
