"""Precedence of report settings: CLI > config file > environment > default (one row each)."""

from datetime import date
from pathlib import Path

import pytest

from firefly_reports.cli import build_parser
from firefly_reports.cli._options import resolve_report_settings
from firefly_reports.errors import ConfigurationError


def settings(argv=(), config=None, env=None):
    args = build_parser().parse_args(["report", "--year", "2025", *argv])
    return resolve_report_settings(args, config or {}, env or {})


def settings_range(argv=(), config=None, env=None):
    args = build_parser().parse_args(
        ["report", "--start", "2025-01-01", "--end", "2025-03-31", *argv]
    )
    return resolve_report_settings(args, config or {}, env or {})


@pytest.mark.parametrize(
    ("argv", "config", "env", "attr", "expected"),
    [
        # lang: CLI > config > FIREFLY_LANG > en
        (["--lang", "it"], {"lang": "en"}, {"FIREFLY_LANG": "en"}, "lang", "it"),
        ([], {"lang": "it"}, {"FIREFLY_LANG": "en"}, "lang", "it"),
        ([], {}, {"FIREFLY_LANG": "it"}, "lang", "it"),
        ([], {}, {}, "lang", "en"),
        # legacy: CLI > config > env > false
        (["--legacy-report"], {}, {}, "legacy", True),
        ([], {"legacy_report": True}, {}, "legacy", True),
        ([], {}, {"FIREFLY_LEGACY_REPORT": "true"}, "legacy", True),
        ([], {}, {"FIREFLY_LEGACY_REPORT": "0"}, "legacy", False),
        # an explicit "off" wins at every level
        (
            ["--no-legacy-report"],
            {"legacy_report": True},
            {"FIREFLY_LEGACY_REPORT": "1"},
            "legacy",
            False,
        ),
        ([], {"legacy_report": False}, {"FIREFLY_LEGACY_REPORT": "1"}, "legacy", False),
        # historical years: CLI > [reports] > 3
        (["--years", "5"], {"reports": {"historical_years": 3}}, {}, "historical_years", 5),
        ([], {"reports": {"historical_years": 5}}, {}, "historical_years", 5),
        ([], {}, {}, "historical_years", 3),
        # on/off flags: CLI (on or off) > config > default
        (["--fetch-links"], {}, {}, "fetch_links", True),
        (["--no-fetch-links"], {"reports": {"fetch_links": True}}, {}, "fetch_links", False),
        (["--no-all-tags"], {"reports": {"all_tags_report": True}}, {}, "all_tags", False),
        ([], {"reports": {"fetch_links": True}}, {}, "fetch_links", True),
        ([], {}, {}, "fetch_links", False),
        (["--all-tags"], {}, {}, "all_tags", True),
        ([], {"reports": {"all_tags_report": True}}, {}, "all_tags", True),
        # tags: CLI csv > config list
        (["--tags", "a, b"], {"tags": ["z"]}, {}, "tags", ("a", "b")),
        ([], {"tags": ["z"]}, {}, "tags", ("z",)),
        ([], {}, {}, "tags", ()),
        # owner / currency
        (["--owner", "Me"], {"owner": "Cfg"}, {}, "owner", "Me"),
        ([], {"owner": "Cfg"}, {}, "owner", "Cfg"),
        ([], {}, {}, "owner", ""),
        (["--currency", "$"], {"currency": "£"}, {}, "currency", "$"),
        ([], {}, {}, "currency", "€"),
        # deductible keywords: config only
        ([], {"tax": {"deductible_keywords": ["x"]}}, {}, "deductible_keywords", ("x",)),
        # pdf / excel switches
        (["--no-pdf"], {}, {}, "pdf", False),
        (["--no-excel"], {}, {}, "excel", False),
    ],
)
def test_option_precedence(argv, config, env, attr, expected):
    assert getattr(settings(argv, config, env).options, attr) == expected


@pytest.mark.parametrize(
    ("argv", "config", "attr", "expected"),
    [
        (
            ["--accounts-include", "1,2"],
            {"filters": {"accounts_include": [9]}},
            "accounts_include",
            ("1", "2"),
        ),
        ([], {"filters": {"accounts_include": [9]}}, "accounts_include", ("9",)),
        (["--categories-exclude", "A"], {}, "categories_exclude", ("A",)),
        (["--hide-transfers"], {}, "show_transfers", False),
        ([], {"filters": {"show_transfers": False}}, "show_transfers", False),
        ([], {}, "show_transfers", True),
        (["--show-transfers"], {"filters": {"show_transfers": False}}, "show_transfers", True),
        (
            ["--no-reconciled-only"],
            {"filters": {"reconciled_only": True}},
            "reconciled_only",
            False,
        ),
        (["--reconciled-only"], {}, "reconciled_only", True),
        ([], {"filters": {"reconciled_only": True}}, "reconciled_only", True),
    ],
)
def test_filter_precedence(argv, config, attr, expected):
    assert getattr(settings(argv, config).options.filters, attr) == expected


def test_out_dir_and_link_delay_precedence():
    assert settings(["--out", "o"], {"out": "c"}).out_dir == Path("o")
    assert settings([], {"out": "c"}).out_dir == Path("c")
    assert settings().out_dir == Path("./output")
    assert settings(["--link-delay", "0"], {"reports": {"link_delay": 1}}).link_delay == 0.0
    assert settings([], {"reports": {"link_delay": 1}}).link_delay == 1.0
    assert settings().link_delay == 0.2


def test_fiscal_year_start_precedence():
    assert settings(["--fiscal-year-start", "04-01"]).period.start == date(2025, 4, 1)
    cfg = {"filters": {"fiscal_year_start": "07-01"}}
    assert settings([], cfg).period.start == date(2025, 7, 1)
    assert settings(["--fiscal-year-start", "04-01"], cfg).period.start == date(2025, 4, 1)


def test_year_comes_from_the_config_file_and_a_cli_range_overrides_it():
    args = build_parser().parse_args(["report"])
    assert resolve_report_settings(args, {"year": 2024}, {}).period.start == date(2024, 1, 1)
    # A range on the command line wins over the config year...
    rng = build_parser().parse_args(["report", "--start", "2025-01-01", "--end", "2025-03-31"])
    got = resolve_report_settings(rng, {"year": 2024}, {})
    assert got.period.start == date(2025, 1, 1) and not got.period.year_mode
    # ...but half a range is incomplete, and --year with a range is still a clash.
    half = build_parser().parse_args(["report", "--start", "2025-01-01"])
    with pytest.raises(ConfigurationError, match="provide --year"):
        resolve_report_settings(half, {"year": 2024}, {})
    clash = build_parser().parse_args(["report", "--year", "2025", "--start", "2025-01-01"])
    with pytest.raises(ConfigurationError, match="either --year or --start/--end"):
        resolve_report_settings(clash, {}, {})
    with pytest.raises(ConfigurationError, match="provide --year"):
        resolve_report_settings(build_parser().parse_args(["report"]), {}, {})


def test_range_mode_validates_dates():
    assert not settings_range().period.year_mode
    bad = build_parser().parse_args(["report", "--start", "2025-02-01", "--end", "2025-01-01"])
    with pytest.raises(ConfigurationError, match="must not be after"):
        resolve_report_settings(bad, {}, {})
