"""Firefly III financial report generator: PDF and Excel reports, Beancount export.

Public contract in 2.x: the ``firefly-reports`` command line. The Python names listed in
``__all__`` form a **provisional** library facade (see :mod:`firefly_reports.api`); every
other module (``reports``, ``render``, ``cli``, ``ledger``, ``firefly_client``, ``i18n``,
``clock``, ``demo``) is internal and may change without notice.

Importing this package is cheap: the facade is loaded lazily on first attribute access.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

__version__ = "2.0.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())

_LAZY = {
    "Period": "firefly_reports.reports.options",
    "GlobalFilters": "firefly_reports.reports.options",
    "ReportOptions": "firefly_reports.reports.options",
    "FireflySource": "firefly_reports.reports.spec",
    "SourceData": "firefly_reports.reports.spec",
    "GeneratedFile": "firefly_reports.reports.pipeline",
    "FailedFile": "firefly_reports.reports.pipeline",
    "ReportResult": "firefly_reports.api",
    "Headline": "firefly_reports.api",
    "ReportInfo": "firefly_reports.api",
    "connect": "firefly_reports.api",
    "fetch_data": "firefly_reports.api",
    "build_reports": "firefly_reports.api",
    "write_reports": "firefly_reports.api",
    "generate_reports": "firefly_reports.api",
    "available_reports": "firefly_reports.api",
    "FireflyReportsError": "firefly_reports.errors",
    "ConfigurationError": "firefly_reports.errors",
    "FireflyAPIError": "firefly_reports.errors",
    "ReportError": "firefly_reports.errors",
}

__all__ = [
    "__version__",
    "ConfigurationError",
    "FailedFile",
    "FireflyAPIError",
    "FireflyReportsError",
    "FireflySource",
    "GeneratedFile",
    "GlobalFilters",
    "Headline",
    "Period",
    "ReportError",
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

if TYPE_CHECKING:
    from firefly_reports.api import (
        Headline,
        ReportInfo,
        ReportResult,
        available_reports,
        build_reports,
        connect,
        fetch_data,
        generate_reports,
        write_reports,
    )
    from firefly_reports.errors import (
        ConfigurationError,
        FireflyAPIError,
        FireflyReportsError,
        ReportError,
    )
    from firefly_reports.reports.options import GlobalFilters, Period, ReportOptions
    from firefly_reports.reports.pipeline import FailedFile, GeneratedFile
    from firefly_reports.reports.spec import FireflySource, SourceData


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
