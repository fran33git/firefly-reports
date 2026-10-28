"""Provisional library facade: connect, fetch, build and write reports.

Everything here is **provisional** in 2.x: names and signatures may change in a minor
release until the maintainer declares the API stable. The command line is the stable
contract. The facade never prints, reads the environment or exits the process; progress
is reported through the optional ``progress`` callback and failures are exceptions
(:class:`~firefly_reports.errors.FireflyReportsError`) or entries of
``ReportResult.failures``.

Each call installs ``options.lang`` for its own thread / task only (see
``firefly_reports.i18n.using``), so concurrent calls in different languages are
supported on a best-effort basis. Report data (``ReportData``) is plain dicts and is
explicitly unstable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from firefly_reports import i18n
from firefly_reports.errors import FireflyAPIError
from firefly_reports.reports.events import Progress, no_progress
from firefly_reports.reports.fetch import fetch_source_data
from firefly_reports.reports.options import GlobalFilters, Period, ReportOptions
from firefly_reports.reports.pipeline import FailedFile, GeneratedFile, build_all, write_outputs
from firefly_reports.reports.registry import REPORTS
from firefly_reports.reports.spec import (
    FireflySource,
    ReportContext,
    ReportData,
    ReportSpec,
    SourceData,
)

__all__ = [
    "FailedFile",
    "FireflySource",
    "GeneratedFile",
    "GlobalFilters",
    "Headline",
    "Period",
    "ReportInfo",
    "ReportOptions",
    "ReportResult",
    "SourceData",
    "available_reports",
    "build_reports",
    "connect",
    "fetch_data",
    "generate_reports",
    "write_reports",
]


@dataclass(frozen=True)
class Headline:
    """The figures the CLI prints after processing."""

    total_in: Decimal
    total_out: Decimal
    net: Decimal
    transactions: int
    savings_rate: Decimal
    cash_runway: Decimal


@dataclass(frozen=True)
class ReportResult:
    files: tuple[GeneratedFile, ...]
    failures: tuple[FailedFile, ...]
    headline: Headline

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class ReportInfo:
    key: str
    formats: frozenset[str]
    requires_year: bool
    mode: Literal["any", "standard", "legacy"]


def connect(
    url: str,
    token: str,
    *,
    request_delay: float = 0.2,
    logger: logging.Logger | None = None,
    trust_insecure_ssl: bool = False,
    on_notice: Callable[[Any], None] | None = None,
) -> FireflySource:
    """A Firefly III API client (``requests`` is imported here, not at package import).

    The TLS chain of the server is checked against the CA lists of ``firefly_reports.tlstrust``
    before any request is sent; a blocked key raises ``UntrustedChainError``. With
    ``trust_insecure_ssl=True`` certificate verification is turned off altogether (the token can
    then be intercepted). *on_notice* receives warnings about the TLS connection; the library
    never prints.
    """
    from firefly_reports.firefly_client import FireflyClient

    return FireflyClient(
        url,
        token,
        logger=logger,
        request_delay=request_delay,
        trust_insecure_ssl=trust_insecure_ssl,
        on_notice=on_notice,
    )


def fetch_data(
    source: FireflySource,
    period: Period,
    options: ReportOptions,
    *,
    progress: Progress | None = None,
) -> SourceData:
    """Download everything the reports need; API failures raise ``FireflyAPIError``."""
    import requests

    ctx = ReportContext(period, options)
    with i18n.using(options.lang):
        try:
            return fetch_source_data(source, ctx, progress or no_progress)
        except requests.RequestException as exc:
            raise FireflyAPIError("errors.api_error", reason=str(exc)) from exc


def build_reports(
    data: SourceData, period: Period, options: ReportOptions
) -> Mapping[str, ReportData]:
    """Build every applicable report (pure: no files, no network)."""
    with i18n.using(options.lang):
        return build_all(data, ReportContext(period, options))


def _headline(built: Mapping[str, ReportData]) -> Headline:
    cf, kpi, reg = built["cash_flow"], built["kpi_scorecard"], built["transaction_register"]
    return Headline(
        total_in=cf["total_in"],
        total_out=cf["total_out"],
        net=cf["net"],
        transactions=reg["total_transactions"],
        savings_rate=Decimal(str(kpi["savings_rate"])),
        cash_runway=Decimal(str(kpi["cash_runway"])),
    )


def write_reports(
    built: Mapping[str, ReportData],
    period: Period,
    options: ReportOptions,
    out_dir: Path,
    *,
    progress: Progress | None = None,
) -> ReportResult:
    """Write the PDFs and the workbook; a failing file ends up in ``result.failures``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with i18n.using(options.lang):
        generated, failed = write_outputs(
            built, ReportContext(period, options), out_dir, progress or no_progress
        )
    return ReportResult(tuple(generated), tuple(failed), _headline(built))


def generate_reports(
    source: FireflySource,
    period: Period,
    options: ReportOptions,
    out_dir: Path,
    *,
    progress: Progress | None = None,
) -> ReportResult:
    """Fetch, build and write in one call."""
    data = fetch_data(source, period, options, progress=progress)
    built = build_reports(data, period, options)
    return write_reports(built, period, options, out_dir, progress=progress)


def _applies(spec: ReportSpec, period: Period, legacy: bool) -> bool:
    ctx = ReportContext(period, ReportOptions(legacy=legacy, all_tags=True))
    return bool(spec.applies(ctx))


def available_reports() -> tuple[ReportInfo, ...]:
    """The registered reports with the formats they produce and when they apply."""
    year = Period.for_year(2000)
    span = Period.between(year.start, year.start)
    infos = []
    for spec in REPORTS:
        standard, legacy = _applies(spec, year, False), _applies(spec, year, True)
        mode: Literal["any", "standard", "legacy"] = (
            "any" if standard and legacy else "standard" if standard else "legacy"
        )
        requires_year = not (_applies(spec, span, False) or _applies(spec, span, True))
        formats = frozenset((["pdf"] if spec.pdf else []) + (["xlsx"] if spec.sheet else []))
        infos.append(ReportInfo(spec.key, formats, requires_year, mode))
    return tuple(infos)
