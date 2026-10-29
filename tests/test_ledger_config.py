"""Mapping-file sections added for category classification (offline)."""

import pytest

from firefly_reports.ledger.errors import ConfigError
from firefly_reports.ledger.mapping import (
    CLASSIFY_CATEGORY,
    parse_ledger_config,
)


def test_categories_blocks_parsed():
    cfg = parse_ledger_config(
        {
            "categories": {
                "expense": {"Automobile": "Expenses:Veicoli:Auto"},
                "income": {"Invoices": "Income:Professione:Invoices"},
            }
        }
    )
    assert cfg.categories_expense == {"Automobile": "Expenses:Veicoli:Auto"}
    assert cfg.categories_income == {"Invoices": "Income:Professione:Invoices"}


def test_defaults_are_empty_and_category_mode():
    cfg = parse_ledger_config({})
    assert cfg.categories_expense == {} and cfg.categories_income == {}
    assert cfg.classify_by == CLASSIFY_CATEGORY


def test_classify_by_category_accepted():
    assert parse_ledger_config({"classify_by": "category"}).classify_by == CLASSIFY_CATEGORY


def test_classify_by_invalid_rejected():
    with pytest.raises(ConfigError) as exc:
        parse_ledger_config({"classify_by": "tag"})
    assert exc.value.message_key == "ledger.err_config_classify"


def test_category_value_must_match_block_root():
    with pytest.raises(ConfigError) as exc:
        parse_ledger_config({"categories": {"expense": {"Invoices": "Income:Invoices"}}})
    assert exc.value.message_key == "ledger.err_config_category_root"
    with pytest.raises(ConfigError):
        parse_ledger_config({"categories": {"income": {"Auto": "Expenses:Auto"}}})


def test_category_value_must_match_account_regex():
    with pytest.raises(ConfigError):
        parse_ledger_config({"categories": {"expense": {"Auto": "Expenses:auto"}}})


def test_unknown_categories_block_rejected():
    with pytest.raises(ConfigError) as exc:
        parse_ledger_config({"categories": {"transfer": {}}})
    assert exc.value.message_key == "ledger.err_config_block"


def test_duplicate_category_key_after_str_rejected():
    with pytest.raises(ConfigError):
        parse_ledger_config({"categories": {"expense": {12: "Expenses:A", "12": "Expenses:B"}}})


def test_categories_section_must_be_a_mapping():
    with pytest.raises(ConfigError):
        parse_ledger_config({"categories": ["x"]})


def test_example_mapping_file_is_valid():
    """beancount_map.example.yaml stays loadable and shows the category mode."""
    from pathlib import Path

    from firefly_reports.ledger.mapping import load_ledger_config

    config = load_ledger_config(Path(__file__).parent.parent / "beancount_map.example.yaml")
    assert config.categories_expense and config.categories_income
