"""CLI option handling: credentials, dates, comma lists and the report settings precedence."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

from firefly_reports.errors import ConfigurationError
from firefly_reports.firefly_client import FireflyClient
from firefly_reports.reports.options import GlobalFilters, Period, ReportOptions


def load_environment() -> None:
    """Load a ``.env`` file (does not override variables that are already set)."""
    load_dotenv()


def csv_list(value: str | None) -> list[str]:
    """Split a comma-separated CLI option into a list of non-empty strings."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def parse_cli_date(value: str, flag: str) -> date:
    """Parse a CLI date string (YYYY-MM-DD)."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ConfigurationError("cli.err_invalid_date", flag=flag, value=value) from None


def default_prompt(question: str) -> str | None:
    """Ask for a secret on an interactive terminal; ``None`` when stdin is not a TTY."""
    if not sys.stdin.isatty():
        return None
    import getpass

    return getpass.getpass(question)


def resolve_credentials(
    url: str | None,
    token: str | None,
    config: Mapping[str, Any],
    env: Mapping[str, str],
    *,
    prompt: Callable[[str], str | None] | None = None,
) -> tuple[str, str]:
    """URL and token: CLI value > config file > environment > prompt (token only).

    Same order as every other setting (``resolve_report_settings``). Before 2.0 the
    environment beat the config file for these two.
    """
    url = (url or config.get("url") or env.get("FIREFLY_URL") or "").strip()
    token = (token or config.get("token") or env.get("FIREFLY_TOKEN") or "").strip()

    if not url:
        raise ConfigurationError("cli.err_url_required")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ConfigurationError("cli.err_url_invalid", url=url)
    if not token and prompt is not None:
        token = (prompt("Firefly III Personal Access Token: ") or "").strip()
    if not token:
        raise ConfigurationError("cli.err_token_required")
    return url, token


def make_client(
    url: str, token: str, logger: logging.Logger | None = None, request_delay: float = 0.2
) -> FireflyClient:
    return FireflyClient(url, token, logger=logger, request_delay=request_delay)


@dataclass(frozen=True)
class ReportSettings:
    period: Period
    options: ReportOptions
    out_dir: Path
    link_delay: float
    debug: bool
    debug_file: str | None


def resolve_language(
    args: argparse.Namespace, config: Mapping[str, Any], env: Mapping[str, str]
) -> str:
    """CLI > config file > FIREFLY_LANG > en."""
    return str(getattr(args, "lang", None) or config.get("lang") or env.get("FIREFLY_LANG", "en"))


def _first_set(*values: Any, default: bool = False) -> bool:
    """The first value that is not ``None`` (a flag given or a key present), else *default*."""
    for value in values:
        if value is not None:
            return bool(value)
    return default


def _env_flag(env: Mapping[str, str], name: str) -> bool | None:
    """An on/off environment variable: ``None`` when unset, else ``true``/``1`` mean on."""
    raw = env.get(name)
    return None if raw is None else raw.lower() in ("true", "1")


def resolve_report_settings(
    args: argparse.Namespace, config: Mapping[str, Any], env: Mapping[str, str]
) -> ReportSettings:
    """Merge CLI flags, config file and environment into immutable report settings.

    Precedence (first value given wins): CLI > config file > environment > default. Every
    on/off setting has an explicit "off" on the command line (``--no-...``,
    ``--show-transfers``), so a ``true`` in the config file can be overridden.
    """
    filters_cfg = config.get("filters", {})
    reports_cfg = config.get("reports", {})

    if args.year and (args.start or args.end):
        raise ConfigurationError("cli.err_year_and_range")
    # A range given on the command line wins over a ``year`` kept in the config file.
    year = None if (args.start or args.end) else (args.year or config.get("year"))
    if not year and (not args.start or not args.end):
        raise ConfigurationError("cli.err_missing_period")

    if year:
        fiscal = args.fiscal_year_start or filters_cfg.get("fiscal_year_start") or "01-01"
        period = Period.for_year(year, fiscal)
    else:
        start = parse_cli_date(args.start, "--start")
        end = parse_cli_date(args.end, "--end")
        if start > end:
            raise ConfigurationError("cli.err_start_after_end", start=args.start, end=args.end)
        period = Period.between(start, end)

    tags = csv_list(args.tags) or list(config.get("tags", []))
    legacy = _first_set(
        args.legacy_report, config.get("legacy_report"), _env_flag(env, "FIREFLY_LEGACY_REPORT")
    )
    link_delay = (
        args.link_delay if args.link_delay is not None else reports_cfg.get("link_delay", 0.2)
    )
    filters = GlobalFilters(
        accounts_include=tuple(
            csv_list(args.accounts_include)
            or [str(a) for a in filters_cfg.get("accounts_include", [])]
        ),
        accounts_exclude=tuple(
            csv_list(args.accounts_exclude)
            or [str(a) for a in filters_cfg.get("accounts_exclude", [])]
        ),
        categories_include=tuple(
            csv_list(args.categories_include)
            or [str(c) for c in filters_cfg.get("categories_include", [])]
        ),
        categories_exclude=tuple(
            csv_list(args.categories_exclude)
            or [str(c) for c in filters_cfg.get("categories_exclude", [])]
        ),
        show_transfers=_first_set(
            args.show_transfers, filters_cfg.get("show_transfers"), default=True
        ),
        reconciled_only=_first_set(args.reconciled_only, filters_cfg.get("reconciled_only")),
    )
    options = ReportOptions(
        owner=args.owner or config.get("owner", ""),
        currency=args.currency or config.get("currency", "€"),
        lang=resolve_language(args, config, env),
        legacy=legacy,
        tags=tuple(tags),
        all_tags=_first_set(args.all_tags, reports_cfg.get("all_tags_report")),
        fetch_links=_first_set(args.fetch_links, reports_cfg.get("fetch_links")),
        historical_years=args.years or reports_cfg.get("historical_years") or 3,
        deductible_keywords=tuple(config.get("tax", {}).get("deductible_keywords", [])),
        filters=filters,
        pdf=not args.no_pdf,
        excel=not args.no_excel,
    )
    return ReportSettings(
        period=period,
        options=options,
        out_dir=Path(args.out or config.get("out", "./output")),
        link_delay=float(link_delay),
        debug=bool(args.debug),
        debug_file=args.debug_file,
    )
