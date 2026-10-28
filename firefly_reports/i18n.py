"""Translation catalogs and accessors for firefly-reports.

The active language is a ``Translator``: a process-wide default set by :func:`load`,
overridable per thread / task with :func:`using` (a ``ContextVar``), so concurrent
renderings in different languages never see each other's catalog.
"""

from __future__ import annotations

import logging
import tomllib
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

_TRANSLATIONS_DIR = Path(__file__).parent / "translations"
_FALLBACK_LANG = "en"

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Translator:
    """One language: its catalog plus the English catalog as per-key fallback."""

    lang: str
    catalog: Mapping[str, Any] = field(compare=False, repr=False)
    fallback: Mapping[str, Any] = field(compare=False, repr=False)

    def t(self, key: str) -> str:
        """Translated string for a dotted key like ``pdf.category``.

        Looks in this language first, then in English, then returns the key itself so
        missing translations degrade gracefully.
        """
        parts = key.split(".", 1)
        if len(parts) == 2:
            section, name = parts
            for catalog in (self.catalog, self.fallback):
                value = catalog.get(section, {}).get(name)
                if value is not None:
                    return str(value)
            return key
        for catalog in (self.catalog, self.fallback):
            if key in catalog:
                return str(catalog[key])
        return key

    def section(self, name: str) -> Mapping[str, Any]:
        """A whole section of this language's catalog (``{}`` when absent)."""
        value = self.catalog.get(name, {})
        return value if isinstance(value, Mapping) else {}


@cache
def _load_file(lang: str) -> dict[str, Any]:
    with (_TRANSLATIONS_DIR / f"{lang}.toml").open("rb") as fh:
        return tomllib.load(fh)


def _build(lang: str) -> Translator:
    if not (_TRANSLATIONS_DIR / f"{lang}.toml").exists():
        _log.warning("No translation file for lang=%r, falling back to %r", lang, _FALLBACK_LANG)
        lang = _FALLBACK_LANG
    return Translator(lang, _load_file(lang), _load_file(_FALLBACK_LANG))


_default: Translator | None = None
_override: ContextVar[Translator | None] = ContextVar("firefly_reports_translator", default=None)


def available_languages() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in _TRANSLATIONS_DIR.glob("*.toml")))


def load(lang: str) -> None:
    """Set the process default language (unknown languages fall back to English)."""
    global _default
    _default = _build(lang)


@contextmanager
def using(lang: str) -> Iterator[Translator]:
    """Use *lang* inside the block, in this thread / task only."""
    translator = _build(lang)
    token = _override.set(translator)
    try:
        yield translator
    finally:
        _override.reset(token)


def current() -> Translator:
    """The translator in effect: the ``using`` override, else the process default, else English."""
    override = _override.get()
    if override is not None:
        return override
    global _default
    if _default is None:
        _default = _build(_FALLBACK_LANG)
    return _default


def t(key: str) -> str:
    """Return the translated string for a dotted key (see :meth:`Translator.t`)."""
    return current().t(key)
