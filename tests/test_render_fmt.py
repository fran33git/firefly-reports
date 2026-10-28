"""Shared formatting helpers (number, date, period, row flattening) in both languages."""

from datetime import date
from decimal import Decimal

import pytest

from firefly_reports import i18n
from firefly_reports.render.fmt import flatten_rows, fmt_date, fmt_num, period_str


@pytest.fixture
def lang():
    def use(code):
        i18n.load(code)

    yield use
    i18n.load("en")


def test_fmt_num_negative_in_parentheses_per_language(lang):
    lang("en")
    assert fmt_num(Decimal("-1234.5")) == "(1,234.50)"
    lang("it")
    assert fmt_num(Decimal("-1234.5")) == "(1.234,50)"


def test_fmt_num_symbol_and_plain_negative(lang):
    lang("en")
    assert fmt_num(Decimal("5"), show_sym=True, sym="€") == "€ 5.00"
    assert fmt_num(Decimal("-5"), parens_neg=False) == "5.00"


def test_fmt_date_per_language(lang):
    lang("en")
    assert fmt_date(date(2025, 3, 4)) == "2025-03-04"
    lang("it")
    assert fmt_date(date(2025, 3, 4)) == "04/03/2025"


def test_period_str_same_month_and_range(lang):
    lang("en")
    assert period_str(date(2025, 3, 1), date(2025, 3, 31)) == "march 2025"
    assert period_str(date(2025, 1, 1), date(2025, 6, 30)) == "2025-01-01 – 2025-06-30"


def test_flatten_rows_carries_the_group_balance_to_every_split():
    group = {
        "date": "2025-01-02",
        "description": "Split",
        "type": "withdrawal",
        "running_balance": Decimal("90.00"),
        "splits": [{"amount": Decimal("-4")}, {"amount": Decimal("-6")}],
    }
    rows = flatten_rows([group, {"description": "plain"}])
    assert [r.get("amount") for r in rows] == [Decimal("-4"), Decimal("-6"), None]
    assert all(r["running_balance"] == Decimal("90.00") for r in rows[:2])
    assert rows[0]["date"] == "2025-01-02" and rows[2] == {"description": "plain"}
