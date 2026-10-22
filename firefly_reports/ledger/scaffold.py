"""Mapping-file scaffolding: a reviewable ``beancount_map.yaml`` draft. Pure, no I/O.

The YAML is assembled from text templates (not dumped) so that it can carry
translated comments. Account names are written as JSON strings, which are valid
double-quoted YAML scalars.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping, Sequence

from firefly_reports.i18n import t
from firefly_reports.ledger.accounts import CategoryUse, Resolution

_ROOT_ORDER = ("Assets", "Liabilities", "Income", "Expenses", "Equity")
_ORIGINS = ("explicit", "investment", "special", "fallback", "auto")
_LANES = ("expense", "income")


def _quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _entry(name: str, account: str) -> str:
    return f"{_quote(name)}: {_quote(account)}"


def _split_auto(
    resolutions: Sequence[Resolution],
    collisions: Mapping[str, Sequence[str]],
    skip_names: Collection[str] = (),
) -> tuple[list[Resolution], list[Resolution], dict[str, list[str]]]:
    """Partition auto-named accounts into (safe, colliding, ambiguous-by-name).

    A name shared by several account kinds (e.g. an asset and an expense called
    ``Amazon``) cannot be frozen in ``accounts:`` because that section is keyed
    by name only; such names are left automatic.
    """
    auto = [r for r in resolutions if r.origin == "auto" and r.name and r.name not in skip_names]
    kinds_by_name: dict[str, set[str]] = defaultdict(set)
    for r in auto:
        kinds_by_name[r.name].add(r.kind)
    ambiguous = {name: sorted(kinds) for name, kinds in kinds_by_name.items() if len(kinds) > 1}
    safe: list[Resolution] = []
    clashing: list[Resolution] = []
    for r in auto:
        if r.name in ambiguous:
            continue
        (clashing if r.account in collisions else safe).append(r)
    return safe, clashing, ambiguous


def _grouped(resolutions: Sequence[Resolution]) -> list[tuple[str, list[Resolution]]]:
    by_root: dict[str, list[Resolution]] = defaultdict(list)
    for r in resolutions:
        by_root[r.account.split(":", 1)[0]].append(r)
    roots = [*_ROOT_ORDER, *sorted(set(by_root) - set(_ROOT_ORDER))]
    return [
        (root, sorted(by_root[root], key=lambda r: r.name.lower()))
        for root in roots
        if root in by_root
    ]


def _account_block(
    safe: Sequence[Resolution],
    clashing: Sequence[Resolution],
    ambiguous: Mapping[str, Sequence[str]],
    collisions: Mapping[str, Sequence[str]],
) -> list[str]:
    lines: list[str] = []
    for root, group in _grouped(safe):
        lines.append(f"  # --- {root}")
        lines.extend(f"  {_entry(r.name, r.account)}  # {t('ledger.origin_auto')}" for r in group)
    if clashing:
        lines.append(f"  # --- {t('ledger.scaffold_section_collisions')}")
        for r in sorted(clashing, key=lambda r: (r.account, r.name.lower())):
            others = ", ".join(repr(n) for n in collisions[r.account] if n != r.name)
            note = t("ledger.scaffold_account_collision").format(others=others)
            lines.append(f"  # {_entry(r.name, r.account)}  # TODO {note}")
    for name, kinds in sorted(ambiguous.items(), key=lambda kv: kv[0].lower()):
        note = t("ledger.scaffold_ambiguous").format(types=", ".join(kinds))
        lines.append(f"  # {_quote(name)}  # {note}")
    return lines


def category_entries(
    uses: Sequence[CategoryUse], *, skip: Mapping[str, Collection[str]] | None = None
) -> dict[str, list[str]]:
    """Per lane, the ``"Name": "Account"  # split: N`` entries for the named categories.

    Most used first (the order of *uses*); names in *skip* (already mapped, per lane)
    are left out. Categories whose automatic account is claimed by several of them
    are flagged with a ``TODO`` comment.
    """
    skip = skip or {}
    out: dict[str, list[str]] = {}
    for lane in _LANES:
        wanted = [u for u in uses if u.lane == lane and u.name and u.name not in skip.get(lane, ())]
        claimed = Counter(u.account for u in wanted if u.origin == "auto")
        entries: list[str] = []
        for u in wanted:
            note = t("ledger.scaffold_category_count").format(count=u.splits)
            line = f"{_entry(u.name, u.account)}  # {note}"
            if claimed[u.account] > 1:
                line += f"  # TODO {t('ledger.scaffold_category_collision')}"
            entries.append(line)
        out[lane] = entries
    return out


def new_account_entries(
    resolutions: Sequence[Resolution],
    collisions: Mapping[str, Sequence[str]],
    known_names: Collection[str],
) -> list[str]:
    """Lines (no indentation) for the accounts an existing mapping does not list yet."""
    snippet = render_new_accounts(resolutions, collisions, known_names)
    return [line.removeprefix("  ") for line in snippet.splitlines()]


def render_categories_block(
    uses: Sequence[CategoryUse],
    *,
    skip: Mapping[str, Collection[str]] | None = None,
    header: bool = True,
) -> str:
    """The ``categories:`` section (blocks ``expense``/``income``) for the named categories.

    With *header* false the ``categories:`` line is left out so the blocks can be merged
    into an existing section. Empty string when there is nothing to list.
    """
    entries = category_entries(uses, skip=skip)
    lines: list[str] = []
    for lane in _LANES:
        if entries[lane]:
            lines.append(f"  {lane}:")
            lines.extend(f"    {entry}" for entry in entries[lane])
    if not lines:
        return ""
    if header:
        lines.insert(0, "categories:")
    return "\n".join(lines) + "\n"


def _uncategorized_comment(uses: Sequence[CategoryUse]) -> list[str]:
    counts = {u.lane: u.splits for u in uses if not u.name}
    if not counts:
        return []
    return [
        f"# {t('ledger.scaffold_uncategorized')}",
        *(f"# {lane}: {counts[lane]}" for lane in _LANES if lane in counts),
    ]


def render_scaffold(
    resolutions: Sequence[Resolution],
    collisions: Mapping[str, Sequence[str]],
    *,
    operating: Sequence[str],
    commodities: Sequence[str],
    fallback_expense: str,
    fallback_income: str,
    investment_root: str,
    classify_by: str = "account",
    categories: Sequence[CategoryUse] = (),
) -> str:
    """Full draft of ``beancount_map.yaml`` for the accounts (and categories) found in Firefly."""
    safe, clashing, ambiguous = _split_auto(resolutions, collisions)
    lines = [
        f"# {t('ledger.scaffold_header')}",
        "",
    ]
    if operating:
        lines.append(f"operating_currency: [{', '.join(operating)}]")
    if commodities:
        lines.append(f"commodities: [{', '.join(commodities)}]")
    # Always recorded: the default is category, so an account-mode draft must say so.
    lines.append(f"classify_by: {classify_by}")
    lines.append("")
    lines.append(f"# {t('ledger.scaffold_hint_accounts')}")
    block = _account_block(safe, clashing, ambiguous, collisions)
    # Commented-out entries still need a block, or uncommenting them yields invalid YAML.
    lines.append("accounts:" if block else "accounts: {}")
    lines.extend(block)
    lines.append("")
    if classify_by == "category":
        lines.append(f"# {t('ledger.scaffold_hint_categories')}")
        section = render_categories_block(categories)
        lines.extend(section.rstrip("\n").split("\n") if section else ["categories: {}"])
        lines.extend(_uncategorized_comment(categories))
        lines.append("")
    lines.append(f"# {t('ledger.scaffold_hint_investments').format(root=investment_root)}")
    lines.append("# investment_accounts:")
    for r in sorted(
        (r for r in resolutions if r.kind == "asset" and r.name), key=lambda r: r.name.lower()
    ):
        lines.append(f"#   {_entry(r.name, 'Broker')}")
    lines.append("")
    lines.append(f"# {t('ledger.scaffold_hint_fallback')}")
    lines.append("# fallback:")
    lines.append(f"#   expense: {_quote(fallback_expense)}")
    lines.append(f"#   income: {_quote(fallback_income)}")
    lines.append("#   strict: false")
    return "\n".join(lines) + "\n"


def render_new_accounts(
    resolutions: Sequence[Resolution],
    collisions: Mapping[str, Sequence[str]],
    known_names: Collection[str],
) -> str:
    """YAML lines for accounts that an existing mapping file does not list yet.

    Empty string when everything is covered. The result is meant to be pasted
    under ``accounts:``.
    """
    safe, clashing, ambiguous = _split_auto(resolutions, collisions, skip_names=known_names)
    if not (safe or clashing):
        return ""
    return "\n".join(_account_block(safe, clashing, ambiguous, collisions)) + "\n"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header))]

    def fmt(row: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()

    sep = "  ".join("-" * w for w in widths)
    return "\n".join([fmt(header), sep, *(fmt(r) for r in rows)]) + "\n"


def render_categories_table(uses: Sequence[CategoryUse]) -> str:
    """Aligned table of every category: direction | category | ledger account | origin | splits."""
    rows = [
        (
            u.lane,
            u.name or t("ledger.scaffold_no_category"),
            u.account,
            t(f"ledger.origin_{u.origin}"),
            str(u.splits),
        )
        for u in uses
    ]
    header = (
        t("ledger.scaffold_col_lane"),
        t("ledger.scaffold_col_category"),
        t("ledger.scaffold_col_account"),
        t("ledger.scaffold_col_origin"),
        t("ledger.scaffold_col_splits"),
    )
    return _table(header, rows)


def render_table(resolutions: Sequence[Resolution], collisions: Mapping[str, Sequence[str]]) -> str:
    """Aligned plain-text table: Firefly account | type | ledger account | origin."""
    rows = [
        (
            r.name or "-",
            r.firefly_type or "-",
            r.account,
            t(f"ledger.origin_{r.origin}")
            + (" !" if r.account in collisions and r.origin == "auto" else ""),
        )
        for r in resolutions
        if r.origin in _ORIGINS
    ]
    header = (
        t("ledger.scaffold_col_firefly"),
        t("ledger.scaffold_col_type"),
        t("ledger.scaffold_col_account"),
        t("ledger.scaffold_col_origin"),
    )
    return _table(header, rows)
