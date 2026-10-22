"""Firefly splits -> neutral ledger model. Pure: no I/O, no network.

Input is the flat per-split list produced by ``FireflyClient.get_transactions``.
Splits sharing a ``group_id`` become ONE ledger transaction with one posting
pair (source -amount / destination +amount) per split.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from firefly_reports.ledger.accounts import AccountResolver
from firefly_reports.ledger.errors import ConversionError
from firefly_reports.ledger.mapping import CURRENCY_RE
from firefly_reports.ledger.model import (
    FIXED_META_KEYS,
    Amount,
    Ledger,
    LedgerTransaction,
    Posting,
)

_TAG_RE = re.compile(r"[^A-Za-z0-9_/.-]+")
_PLACEHOLDER_PAYEES = {"", "(no name)", "(empty)", "(cash)"}
# Firefly split field -> fixed metadata key (see ``FIXED_META_KEYS``).
_EXTRA_FIELDS = {
    "bill_name": "bill",
    "internal_reference": "reference",
    "external_id": "external_id",
    "external_url": "external_url",
    "book_date": "book_date",
    "interest_date": "interest_date",
}
_DATE_KEYS = ("book_date", "interest_date")

Split = Mapping[str, Any]
# The postings of one split and the index of the one that carries per-split metadata.
SplitPostings = tuple[list[Posting], int]


def _journal_id(split: Split) -> str:
    return str(split.get("transaction_journal_id") or split.get("group_id") or "")


def _decimal(value: object, split: Split) -> Decimal:
    """Parse a Firefly amount string strictly (no float, no silent zero)."""
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        raise ConversionError("ledger.err_amount", id=_journal_id(split), value=value) from None
    if not number.is_finite():
        raise ConversionError("ledger.err_amount", id=_journal_id(split), value=value)
    return number


def _optional_decimal(value: object, split: Split) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return _decimal(value, split)


def _negate(number: Decimal) -> Decimal:
    """-number without producing a negative zero."""
    return -number if number else number


def _currency(value: object, split: Split) -> str:
    code = str(value or "").strip().upper()
    if not code:
        raise ConversionError("ledger.err_currency", id=_journal_id(split))
    if not CURRENCY_RE.match(code):
        raise ConversionError("ledger.err_currency_invalid", id=_journal_id(split), value=code)
    return code


def _split_date(split: Split) -> date:
    raw = str(split.get("date") or "")
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        raise ConversionError("ledger.err_date", id=_journal_id(split), value=raw) from None


def _clean(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def normalize_tag(tag: str) -> str:
    """Beancount tags allow only letters, digits and ``_ / . -``."""
    return _TAG_RE.sub("-", tag.strip()).strip("-")


def _extras(split: Split) -> tuple[tuple[str, str], ...]:
    """Fixed-key metadata present on a split, sorted by key; dates as ``YYYY-MM-DD``."""
    items: dict[str, str] = {}
    for field, key in _EXTRA_FIELDS.items():
        value = _clean(split.get(field))
        if value is None:
            continue
        items[key] = value[:10] if key in _DATE_KEYS else value
    return tuple(sorted(items.items()))


def _split_postings(split: Split, resolver: AccountResolver) -> SplitPostings:
    """The posting pair for one split, handling foreign amounts with ``@@``.

    When classifying by category and exactly one side is an expense/revenue
    counterpart, that side's account comes from the Firefly category instead of
    the counterpart name (which then lives only in the ``payee``). That posting
    is the *carrier* of the per-split metadata; otherwise the carrier is the
    destination, as before.
    """
    tx_type = str(split.get("type") or "").lower()
    number = _decimal(split.get("amount"), split)
    currency = _currency(split.get("currency_code"), split)
    src_type, dst_type = split.get("source_type"), split.get("destination_type")
    category = _clean(split.get("category_name"))

    src_counterpart = resolver.is_counterpart(src_type)
    dst_counterpart = resolver.is_counterpart(dst_type)
    by_category = resolver.classify_by == "category" and src_counterpart != dst_counterpart

    def real(side: str) -> str:
        return resolver.resolve(
            split.get(f"{side}_name"),
            split.get(f"{side}_type"),
            split.get(f"{side}_id"),
            side,
        )

    if by_category and dst_counterpart:
        carrier = 1
        src = real("source")
        dst = resolver.resolve_category(category, resolver.lane(dst_type, "destination"))
    elif by_category:
        carrier = 0
        src = resolver.resolve_category(category, resolver.lane(src_type, "source"))
        dst = real("destination")
    else:
        carrier = 1
        src, dst = real("source"), real("destination")

    src_amount = Amount(_negate(number), currency)
    dst_amount = Amount(number, currency)
    src_price: Amount | None = None
    dst_price: Amount | None = None

    foreign_code = str(split.get("foreign_currency_code") or "").strip().upper()
    foreign_number = _optional_decimal(split.get("foreign_amount"), split)
    if foreign_code and foreign_code != currency and foreign_number:
        if not CURRENCY_RE.match(foreign_code):
            raise ConversionError(
                "ledger.err_currency_invalid", id=_journal_id(split), value=foreign_code
            )
        price = Amount(number.copy_abs(), currency)
        # In Firefly, `amount` is in the asset account's currency; the foreign amount
        # belongs to the counterpart (revenue for deposits, otherwise the destination).
        if tx_type == "deposit":
            src_amount = Amount(_negate(foreign_number), foreign_code)
            src_price = price
        else:
            dst_amount = Amount(foreign_number, foreign_code)
            dst_price = price

    budget = _clean(split.get("budget_name"))
    note = _clean(split.get("notes"))
    postings = [Posting(src, src_amount, src_price), Posting(dst, dst_amount, dst_price)]
    # By category the category is the account itself and the counterpart survives as payee.
    postings[carrier] = replace(
        postings[carrier],
        category=None if by_category else category,
        budget=budget,
        note=note,
        payee=_counterpart(split) if by_category else None,
        extra=_extras(split),
    )
    return postings, carrier


def _without(p: Posting, attr: str) -> Posting:
    """Copy of *p* with one of its metadata fields cleared."""
    if attr == "category":
        return replace(p, category=None)
    if attr == "budget":
        return replace(p, budget=None)
    return replace(p, note=None)


def _merge_postings(postings: list[Posting]) -> list[Posting]:
    """Sum plain postings that hit the same account and currency (first-seen order)."""
    merged: dict[tuple[str, str], Posting] = {}
    out: list[Posting | tuple[str, str]] = []
    for p in postings:
        plain = p.price_total is None and not (
            p.category or p.budget or p.note or p.payee or p.extra
        )
        if not plain:
            out.append(p)
            continue
        key = (p.account, p.amount.currency)
        if key in merged:
            prev = merged[key]
            merged[key] = Posting(p.account, Amount(prev.amount.number + p.amount.number, key[1]))
        else:
            merged[key] = p
            out.append(key)
    return [merged[item] if isinstance(item, tuple) else item for item in out]


def _counterpart(split: Split) -> str | None:
    tx_type = str(split.get("type") or "").lower()
    name = {"withdrawal": "destination_name", "deposit": "source_name"}.get(tx_type)
    value = _clean(split.get(name)) if name else None
    return None if value is None or value.lower() in _PLACEHOLDER_PAYEES else value


def _convert_group(
    group_id: str, splits: list[Split], resolver: AccountResolver
) -> LedgerTransaction:
    splits = sorted(splits, key=lambda s: int(_journal_id(s)) if _journal_id(s).isdigit() else 0)
    first = splits[0]
    multi = len(splits) > 1

    postings: list[Posting] = []
    carriers: list[int] = []
    for sp in splits:
        pair, carrier = _split_postings(sp, resolver)
        carriers.append(len(postings) + carrier)
        postings.extend(pair)

    # category / budget / note: transaction-level when every split agrees, else per posting.
    uniform: dict[str, str | None] = {}
    for attr in ("category", "budget", "note"):
        values = {getattr(postings[i], attr) for i in carriers}
        uniform[attr] = values.pop() if len(values) == 1 else None
        if uniform[attr] is not None:
            postings = [_without(p, attr) for p in postings]

    descriptions = [d for sp in splits if (d := _clean(sp.get("description")))]
    group_title = _clean(first.get("group_title"))
    if multi:
        unique = list(dict.fromkeys(descriptions))
        narration = group_title or "; ".join(unique)
    else:
        narration = descriptions[0] if descriptions else (group_title or "")

    # Fixed-key metadata follows the same rule: transaction-level only if every split has it equal.
    tx_extra: list[tuple[str, str]] = []
    for key in FIXED_META_KEYS:
        values = {dict(postings[i].extra).get(key) for i in carriers}
        if len(values) == 1 and None not in values:
            tx_extra.append((key, values.pop() or ""))
            postings = [
                replace(p, extra=tuple(kv for kv in p.extra if kv[0] != key)) for p in postings
            ]

    counterparts = {c for sp in splits if (c := _counterpart(sp))}
    if len(counterparts) == 1:
        # One counterpart: it is the transaction payee, not per-posting metadata.
        postings = [replace(p, payee=None) for p in postings]
    tags = sorted(
        {tag for sp in splits for raw in (sp.get("tags") or []) if (tag := normalize_tag(str(raw)))}
    )

    tx = LedgerTransaction(
        date=min(_split_date(sp) for sp in splits),
        narration=narration,
        postings=tuple(_merge_postings(postings)),
        firefly_id=_journal_id(first),
        firefly_group_id=group_id if multi else None,
        payee=counterparts.pop() if len(counterparts) == 1 else None,
        tags=tuple(tags),
        category=uniform["category"],
        budget=uniform["budget"],
        note=uniform["note"],
        extra=tuple(tx_extra),
    )
    residual = {cur: n for cur, n in tx.balance().items() if n}
    if residual:
        raise ConversionError("ledger.err_unbalanced", id=tx.firefly_id, residual=residual)
    return tx


def _collect_ibans(splits: Iterable[Split], resolver: AccountResolver) -> dict[str, str]:
    """Ledger account -> IBAN for real accounts: the most frequent value, ties alphabetical."""
    seen: Counter[tuple[str, str]] = Counter()
    for sp in splits:
        for side in ("source", "destination"):
            iban = _clean(sp.get(f"{side}_iban"))
            firefly_type = sp.get(f"{side}_type")
            if iban is None or resolver.is_counterpart(firefly_type):
                continue
            account = resolver.resolve(
                sp.get(f"{side}_name"), firefly_type, sp.get(f"{side}_id"), side
            )
            seen[(account, iban)] += 1
    best: dict[str, tuple[int, str]] = {}
    for (account, iban), count in seen.items():
        if account not in best or (-count, iban) < (-best[account][0], best[account][1]):
            best[account] = (count, iban)
    return {account: iban for account, (_, iban) in sorted(best.items())}


def _attach_links(
    transactions: list[LedgerTransaction],
    groups: Mapping[str, list[Split]],
    links: Iterable[Mapping[str, Any]],
) -> tuple[list[LedgerTransaction], int]:
    """Give both ends of every Firefly link the same ``^firefly-link-<id>`` name.

    A link with an end outside the converted set is dropped and counted; a link
    joining two splits of one transaction carries no information and is ignored.
    """
    index_by_group = {gid: i for i, gid in enumerate(groups)}
    index_by_journal = {
        _journal_id(sp): index_by_group[gid] for gid, sps in groups.items() for sp in sps
    }
    names: dict[int, set[str]] = {}
    skipped = 0
    for link in links:
        ends = (
            index_by_journal.get(str(link.get("inward_id"))),
            index_by_journal.get(str(link.get("outward_id"))),
        )
        name = normalize_tag(f"firefly-link-{link.get('id')}")
        if None in ends or not link.get("id") or not name:
            skipped += 1
            continue
        first, second = ends
        if first == second or first is None or second is None:
            continue
        names.setdefault(first, set()).add(name)
        names.setdefault(second, set()).add(name)
    return (
        [
            replace(tx, links=tuple(sorted(names[i]))) if i in names else tx
            for i, tx in enumerate(transactions)
        ],
        skipped,
    )


def build_ledger(
    splits: Iterable[Split],
    resolver: AccountResolver,
    *,
    check_collisions: bool = True,
    links: Iterable[Mapping[str, Any]] = (),
) -> Ledger:
    """Group flat Firefly splits by transaction group and convert them.

    Raises ``AccountCollisionError`` after conversion if automatically generated
    account names clash, unless *check_collisions* is false (the scaffold command
    reports them instead). *links* are Firefly transaction links
    (``id``, ``inward_id``, ``outward_id`` as journal ids).
    """
    split_list = list(splits)
    groups: dict[str, list[Split]] = {}
    for sp in split_list:
        key = str(sp.get("group_id") or _journal_id(sp))
        groups.setdefault(key, []).append(sp)

    transactions = [_convert_group(gid, sps, resolver) for gid, sps in groups.items()]
    transactions, skipped = _attach_links(transactions, groups, links)
    ibans = _collect_ibans(split_list, resolver)
    if check_collisions:
        resolver.raise_on_collisions()
    transactions.sort(key=lambda tx: tx.sort_key)
    return Ledger(tuple(transactions), ibans=ibans, skipped_links=skipped)
