"""Safe textual insertion of new entries into an existing mapping file (offline)."""

import yaml

from firefly_reports.ledger.mapfile import append_entries, holds_entries
from firefly_reports.ledger.mapping import parse_ledger_config

A = '"New": "Assets:New"  # new'
E = '"Auto": "Expenses:Auto"  # split: 4'
I = '"Invoices": "Income:Invoices"  # split: 2'  # noqa: E741


def load(text):
    return yaml.safe_load(text)


def in_order(original: str, result: str) -> bool:
    """Every original line survives, unchanged and in the same order."""
    it = iter(result.splitlines())
    return all(any(line == other for other in it) for line in original.splitlines())


BASE = (
    "# my mapping\n"
    "operating_currency: [EUR]\n"
    "\n"
    "accounts:\n"
    '  "Bank": "Assets:Bank"  # keep me\n'
    "  # --- a comment inside the block\n"
    '  "Savings": "Assets:Savings"\n'
    "\n"
    "# fallback below\n"
    "fallback:\n"
    "  strict: false\n"
)


def test_existing_lines_untouched():
    out = append_entries(BASE, accounts=[A], expense=[], income=[])
    assert in_order(BASE, out) and A in out
    assert out.count("accounts:") == 1


def test_appends_into_accounts_block_before_the_next_section():
    out = append_entries(BASE, accounts=[A], expense=[], income=[])
    lines = out.splitlines()
    assert lines.index("  " + A) > lines.index('  "Savings": "Assets:Savings"')
    assert lines.index("  " + A) < lines.index("fallback:")
    assert load(out)["accounts"]["New"] == "Assets:New"
    assert load(out)["accounts"]["Bank"] == "Assets:Bank"


CATS = (
    "categories:\n"
    "  expense:\n"
    '    "Food": "Expenses:Food"\n'
    "  # --- income\n"
    "  income:\n"
    '    "Other": "Income:Other"\n'
    "fallback: {}\n"
)


def test_appends_into_expense_and_income_blocks():
    out = append_entries(CATS, accounts=[], expense=[E], income=[I])
    data = load(out)["categories"]
    assert data["expense"] == {"Food": "Expenses:Food", "Auto": "Expenses:Auto"}
    assert data["income"] == {"Other": "Income:Other", "Invoices": "Income:Invoices"}
    assert in_order(CATS, out)
    lines = out.splitlines()
    assert lines.index("    " + E) < lines.index("  # --- income")


def test_creates_missing_categories_section_at_the_end():
    out = append_entries(BASE, accounts=[], expense=[E], income=[I])
    assert in_order(BASE, out)
    data = load(out)["categories"]
    assert data["expense"] == {"Auto": "Expenses:Auto"} and data["income"] == {
        "Invoices": "Income:Invoices"
    }
    assert out.count("categories:") == 1


def test_creates_missing_income_block_inside_existing_categories():
    text = 'categories:\n  expense:\n    "Food": "Expenses:Food"\n'
    out = append_entries(text, accounts=[], expense=[], income=[I])
    assert in_order(text, out)
    assert load(out)["categories"]["income"] == {"Invoices": "Income:Invoices"}


def test_creates_missing_accounts_section():
    out = append_entries("operating_currency: [EUR]\n", accounts=[A], expense=[], income=[])
    assert load(out)["accounts"] == {"New": "Assets:New"}


def test_empty_flow_mapping_is_replaced():
    out = append_entries("accounts: {}\n", accounts=[A], expense=[], income=[])
    assert load(out) == {"accounts": {"New": "Assets:New"}}
    assert out.count("accounts:") == 1


def test_empty_flow_expense_block_is_replaced():
    text = "categories:\n  expense: {}\n"
    out = append_entries(text, accounts=[], expense=[E], income=[])
    assert load(out)["categories"]["expense"] == {"Auto": "Expenses:Auto"}


def test_nonempty_flow_style_returns_none():
    assert (
        append_entries('accounts: {"a": "Assets:A"}\n', accounts=[A], expense=[], income=[]) is None
    )
    text = 'categories:\n  expense: {"x": "Expenses:X"}\n'
    assert append_entries(text, accounts=[], expense=[E], income=[]) is None


def test_duplicate_top_level_key_returns_none():
    text = 'accounts:\n  "a": "Assets:A"\naccounts:\n  "b": "Assets:B"\n'
    assert append_entries(text, accounts=[A], expense=[], income=[]) is None


def test_crlf_and_missing_final_newline_preserved():
    text = 'accounts:\r\n  "Bank": "Assets:Bank"'  # CRLF, no newline at the end
    out = append_entries(text, accounts=[A], expense=[E], income=[])
    assert "\n" not in out.replace("\r\n", "")  # no bare LF anywhere
    assert out.startswith(text) and out.endswith("\r\n")
    data = load(out)
    assert data["accounts"]["New"] == "Assets:New"
    assert data["categories"]["expense"] == {"Auto": "Expenses:Auto"}


def test_four_space_indentation_is_followed():
    text = 'accounts:\n    "Bank": "Assets:Bank"\n'
    out = append_entries(text, accounts=[A], expense=[], income=[])
    assert "\n    " + A in out
    assert load(out)["accounts"]["New"] == "Assets:New"


def test_comment_only_file_gets_sections_appended():
    text = "# nothing here yet\n"
    out = append_entries(text, accounts=[A], expense=[E], income=[I])
    assert in_order(text, out)
    assert set(load(out)) == {"accounts", "categories"}


def test_nothing_to_add_returns_the_text_unchanged():
    assert append_entries(BASE, accounts=[], expense=[], income=[]) == BASE


def test_holds_entries_checks_every_new_entry():
    out = append_entries(BASE, accounts=[A], expense=[E], income=[I])
    assert holds_entries(out, accounts=[A], expense=[E], income=[I])
    assert not holds_entries(BASE, accounts=[A], expense=[], income=[])
    assert not holds_entries(out, accounts=[], expense=['"Altra": "Expenses:Altra"'], income=[])


def test_holds_entries_ignores_comment_lines_and_checks_the_lane():
    out = append_entries(BASE, accounts=[], expense=[E], income=[])
    assert holds_entries(out, accounts=["# --- a comment"], expense=[E], income=[])
    assert not holds_entries(out, accounts=[], expense=[], income=[E])  # wrong lane


def test_result_is_a_valid_mapping_with_all_previous_entries():
    out = append_entries(BASE, accounts=[A], expense=[E], income=[I])
    cfg = parse_ledger_config(load(out))
    assert cfg.accounts["Bank"] == "Assets:Bank" and cfg.accounts["New"] == "Assets:New"
    assert cfg.categories_expense == {"Auto": "Expenses:Auto"}
    assert cfg.categories_income == {"Invoices": "Income:Invoices"}
