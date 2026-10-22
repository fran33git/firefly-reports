"""Category -> ledger account resolution (offline)."""

import pytest

from firefly_reports.ledger.accounts import AccountResolver
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapping import parse_ledger_config


def resolver(**data):
    return AccountResolver(parse_ledger_config(data), LedgerLabels.from_i18n())


MAPPED = {
    "classify_by": "category",
    "categories": {
        "expense": {"Automobile": "Expenses:Veicoli:Auto", "Carburante": "Expenses:Veicoli:Auto"},
        "income": {"Fatture": "Income:Professione:Fatture"},
    },
}


def test_classify_by_comes_from_config():
    assert resolver(**MAPPED).classify_by == "category"
    assert resolver().classify_by == "category"
    assert resolver(classify_by="account").classify_by == "account"


def test_mapped_category_uses_mapping():
    r = resolver(**MAPPED)
    assert r.resolve_category("Automobile", "expense") == "Expenses:Veicoli:Auto"
    assert r.resolve_category("Fatture", "income") == "Income:Professione:Fatture"


def test_unmapped_category_gets_auto_name():
    r = resolver()
    assert r.resolve_category("Bar e Ristoranti", "expense") == "Expenses:Bar-e-Ristoranti"
    assert r.resolve_category("Bar e Ristoranti", "income") == "Income:Bar-e-Ristoranti"


@pytest.mark.parametrize("name", [None, "", "  "])
def test_empty_category_uses_fallback_account(name):
    r = resolver()
    assert r.resolve_category(name, "expense") == "Expenses:Uncategorized"
    assert r.resolve_category(name, "income") == "Income:Uncategorized"


def test_fallback_strict_applies_to_unmapped_categories_only():
    r = resolver(**MAPPED, fallback={"strict": True})
    assert r.resolve_category("Bar", "expense") == "Expenses:Uncategorized"
    assert r.resolve_category("Automobile", "expense") == "Expenses:Veicoli:Auto"


def test_unnormalizable_name_uses_fallback():
    r = resolver()
    assert r.resolve_category("???", "expense") == "Expenses:Uncategorized"
    assert r.resolve_category("???", "income") == "Income:Uncategorized"


def test_category_on_both_lanes_is_independent():
    r = resolver(categories={"expense": {"Rimborsi": "Expenses:Rimborsi"}})
    r.resolve_category("Rimborsi", "expense")
    r.resolve_category("Rimborsi", "income")
    assert [(u.lane, u.name) for u in r.unmapped_categories()] == [("income", "Rimborsi")]


def test_unmapped_categories_excludes_mapped_and_uncategorized():
    r = resolver(**MAPPED)
    for name in ("Automobile", "Nuova", None):
        r.resolve_category(name, "expense")
    assert [u.name for u in r.unmapped_categories()] == ["Nuova"]


def test_two_auto_categories_with_same_name_collide():
    r = resolver()
    r.resolve_category("A b", "expense")
    r.resolve_category("A-b", "expense")
    assert r.collisions() == {"Expenses:A-b": ["A b", "A-b"]}


def test_auto_category_named_like_the_fallback_collides():
    r = resolver()
    r.resolve_category(None, "expense")
    r.resolve_category("Uncategorized", "expense")
    assert "Expenses:Uncategorized" in r.collisions()


def test_explicit_grouping_is_allowed():
    r = resolver(**MAPPED)
    r.resolve_category("Automobile", "expense")
    r.resolve_category("Carburante", "expense")
    assert r.collisions() == {}


def test_unused_mapping_keys_are_reported():
    r = resolver(**MAPPED)
    r.resolve_category("Automobile", "expense")
    assert r.unused_category_keys() == [("expense", "Carburante"), ("income", "Fatture")]


def test_split_counts_and_ordering():
    r = resolver()
    for name in ("B", "A", "A", "C", "C", "C"):
        r.resolve_category(name, "expense")
    r.resolve_category("Z", "income")
    uses = r.category_uses()
    assert [(u.lane, u.name, u.splits) for u in uses] == [
        ("expense", "C", 3),
        ("expense", "A", 2),
        ("expense", "B", 1),
        ("income", "Z", 1),
    ]


def test_uncategorized_is_listed_with_empty_name():
    r = resolver()
    r.resolve_category(None, "expense")
    (use,) = r.category_uses()
    assert (use.name, use.origin, use.splits) == ("", "fallback", 1)


def test_category_origin_values():
    r = resolver(**MAPPED)
    r.resolve_category("Automobile", "expense")
    r.resolve_category("Nuova", "expense")
    origins = {u.name: u.origin for u in r.category_uses()}
    assert origins == {"Automobile": "explicit", "Nuova": "auto"}


def test_resolutions_exclude_categories():
    r = resolver()
    r.resolve_category("Bar", "expense")
    r.resolve("Conto", "Asset account")
    assert [x.name for x in r.resolutions()] == ["Conto"]


@pytest.mark.parametrize(
    "firefly_type, expected",
    [
        ("Expense account", True),
        ("Beneficiary account", True),
        ("Revenue account", True),
        ("Something new", True),
        (None, True),
        ("Asset account", False),
        ("Default account", False),
        ("Cash account", False),
        ("Loan", False),
        ("Mortgage", False),
        ("Initial balance account", False),
        ("Reconciliation account", False),
        ("Import account", False),
        ("Liability credit account", False),
    ],
)
def test_is_counterpart(firefly_type, expected):
    assert resolver().is_counterpart(firefly_type) is expected


@pytest.mark.parametrize(
    "firefly_type, side, lane",
    [
        ("Expense account", "destination", "expense"),
        ("Beneficiary account", "destination", "expense"),
        ("Revenue account", "source", "income"),
        ("Something new", "destination", "expense"),
        ("Something new", "source", "income"),
    ],
)
def test_lane(firefly_type, side, lane):
    assert resolver().lane(firefly_type, side) == lane
