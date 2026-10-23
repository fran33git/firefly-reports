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


_OPTIONS = frozenset(["Period", "GlobalFilters", "ReportOptions"])
_SPEC = frozenset(["FireflySource", "SourceData"])
_PIPELINE = frozenset(["GeneratedFile", "FailedFile"])
_API = frozenset(
    [
        "ReportResult",
        "Headline",
        "ReportInfo",
        "connect",
        "fetch_data",
        "build_reports",
        "write_reports",
        "generate_reports",
        "available_reports",
    ]
)
_ERRORS = frozenset(["FireflyReportsError", "ConfigurationError", "FireflyAPIError", "ReportError"])


def __getattr__(name: str) -> Any:
    """Load the facade lazily (PEP 562) with static imports, so the package imports fast."""
    if name in _OPTIONS:
        from firefly_reports.reports import options as module
    elif name in _SPEC:
        from firefly_reports.reports import spec as module  # type: ignore[no-redef]
    elif name in _PIPELINE:
        from firefly_reports.reports import pipeline as module  # type: ignore[no-redef]
    elif name in _API:
        from firefly_reports import api as module  # type: ignore[no-redef]
    elif name in _ERRORS:
        from firefly_reports import errors as module  # type: ignore[no-redef]
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
