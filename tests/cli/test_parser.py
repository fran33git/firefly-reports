"""Argument parsing of the CLI (root options and the report subcommand)."""

import sys

import pytest

from firefly_reports.cli import build_parser

URL = "https://firefly.example.com"
RANGE_ARGS = ["--start", "2025-01-01", "--end", "2025-06-30"]


def parse_args():
    """Parse sys.argv like the 1.x tests: bare flags mean the report subcommand."""
    argv = sys.argv[1:]
    if not argv or argv[0] not in ("init", "export", "demo", "report"):
        argv = ["report", *argv]
    return build_parser().parse_args(argv)


def test_parse_args_init_subcommand(monkeypatch):
    """The 'init' subcommand is parsed into args.command."""
    monkeypatch.setattr(sys, "argv", ["firefly-reports", "init"])
    args = parse_args()
    assert args.command == "init"


def test_parse_args_defaults(monkeypatch):
    """All optional flags default to None/False/empty when omitted."""
    monkeypatch.setattr(sys, "argv", ["firefly-reports", *RANGE_ARGS])
    args = parse_args()
    assert args.command == "report"
    assert args.url is None
    assert args.token is None
    assert args.year is None
    assert args.owner is None
    assert args.currency is None
    assert args.out is None
    assert args.lang is None
    assert args.years is None
    assert args.tags == ""
    assert args.link_delay is None
    assert args.accounts_include is None
    assert args.accounts_exclude is None
    assert args.categories_include is None
    assert args.categories_exclude is None
    assert args.fiscal_year_start is None
    assert args.debug_file is None
    for flag in ("no_pdf", "no_excel", "debug"):
        assert getattr(args, flag) is False
    # Paired on/off flags stay None until given, so the config file can decide.
    for flag in ("legacy_report", "fetch_links", "all_tags", "show_transfers", "reconciled_only"):
        assert getattr(args, flag) is None


def test_parse_args_all_flags(monkeypatch):
    """Every CLI flag is parsed into the expected attribute and type."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "firefly-reports",
            "--url",
            URL,
            "--token",
            "t",
            "--year",
            "2025",
            "--owner",
            "Me",
            "--currency",
            "$",
            "--out",
            "./out",
            "--lang",
            "it",
            "--years",
            "5",
            "--legacy-report",
            "--tags",
            "a,b",
            "--fetch-links",
            "--link-delay",
            "0.5",
            "--all-tags",
            "--no-pdf",
            "--no-excel",
            "--accounts-include",
            "1,2",
            "--accounts-exclude",
            "3",
            "--categories-include",
            "A",
            "--categories-exclude",
            "B",
            "--hide-transfers",
            "--reconciled-only",
            "--fiscal-year-start",
            "04-01",
            "--debug",
            "--debug-file",
            "x.log",
        ],
    )
    args = parse_args()
    assert args.url == URL
    assert args.year == 2025
    assert args.lang == "it"
    assert args.years == 5
    assert args.link_delay == 0.5
    assert args.accounts_include == "1,2"
    assert args.accounts_exclude == "3"
    assert args.categories_include == "A"
    assert args.categories_exclude == "B"
    assert args.fiscal_year_start == "04-01"
    assert args.debug_file == "x.log"
    for flag in (
        "legacy_report",
        "fetch_links",
        "all_tags",
        "no_pdf",
        "no_excel",
        "reconciled_only",
        "debug",
    ):
        assert getattr(args, flag) is True
    assert args.show_transfers is False  # --hide-transfers


@pytest.mark.parametrize(
    "bad",
    [
        ["--lang", "fr"],
        ["--years", "4"],
        ["--year", "abc"],
        ["--link-delay", "fast"],
    ],
    ids=["bad-lang", "bad-years", "bad-year", "bad-link-delay"],
)
def test_parse_args_rejects_invalid_values(monkeypatch, bad):
    """argparse exits with an error on invalid choices or types."""
    monkeypatch.setattr(sys, "argv", ["firefly-reports", *bad])
    with pytest.raises(SystemExit):
        parse_args()
