"""Tests for the i18n loader and t() accessor."""

import tomllib
from pathlib import Path

from firefly_reports import i18n

TRANSLATIONS_DIR = Path(__file__).parent.parent / "firefly_reports" / "translations"


def _all_dotted_keys(d: dict, prefix: str = "") -> set[str]:
    """Recursively collect all dotted key paths from a nested dict."""
    keys: set[str] = set()
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= _all_dotted_keys(v, full)
        else:
            keys.add(full)
    return keys


def test_en_and_it_have_identical_keys():
    """Every key in en.toml must exist in it.toml and vice versa."""
    with (TRANSLATIONS_DIR / "en.toml").open("rb") as f:
        en = tomllib.load(f)
    with (TRANSLATIONS_DIR / "it.toml").open("rb") as f:
        it = tomllib.load(f)

    en_keys = _all_dotted_keys(en)
    it_keys = _all_dotted_keys(it)

    missing_in_it = en_keys - it_keys
    missing_in_en = it_keys - en_keys

    assert not missing_in_it, f"Keys in en.toml but not in it.toml: {missing_in_it}"
    assert not missing_in_en, f"Keys in it.toml but not in en.toml: {missing_in_en}"


def test_t_returns_correct_english_string():
    """t() returns the expected string after loading English."""
    i18n.load("en")
    assert i18n.t("common.category") == "Category"
    assert i18n.t("common.income") == "Income"
    assert i18n.t("pdf.footer_page").format(page=3) == "Page 3"


def test_t_returns_key_for_missing_entry():
    """t() degrades gracefully: returns the key when the entry is absent."""
    i18n.load("en")
    assert i18n.t("nonexistent.key") == "nonexistent.key"


def test_t_returns_italian_after_load_it():
    """Reloading with 'it' switches the language."""
    i18n.load("it")
    assert i18n.t("common.category") == "Categoria"
    i18n.load("en")  # restore for other tests


def test_t_falls_back_to_english_per_key():
    """A key missing from the active language falls back to the English string."""
    i18n.load("it")
    # simulate a key present in en.toml but missing from the active catalog
    del i18n.T["common"]["category"]
    assert i18n.t("common.category") == "Category"
    i18n.load("en")  # restore for other tests


def test_load_sets_current_lang():
    """load() records the active language in i18n.CURRENT_LANG."""
    i18n.load("it")
    assert i18n.CURRENT_LANG == "it"
    i18n.load("en")  # restore for other tests
    assert i18n.CURRENT_LANG == "en"
