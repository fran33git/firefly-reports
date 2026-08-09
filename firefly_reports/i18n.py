"""Translation loader and accessor for firefly-reports."""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

_TRANSLATIONS_DIR = Path(__file__).parent / "translations"
_FALLBACK_LANG = "en"

T: dict[str, Any] = {}
_T_EN: dict[str, Any] = {}
CURRENT_LANG: str = "en"

_log = logging.getLogger(__name__)


def _load_file(lang: str) -> dict[str, Any]:
    path = _TRANSLATIONS_DIR / f"{lang}.toml"
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load(lang: str) -> None:
    """Load translations for *lang* into the module-level T dict.

    Falls back to 'en' if the requested language file does not exist. The
    English catalog is always kept in ``_T_EN`` as a per-key fallback, and
    ``CURRENT_LANG`` records the active language for locale-aware formatting.
    Both dicts are updated in place so modules that did ``from i18n import T``
    keep a valid reference.
    """
    global CURRENT_LANG
    if not (_TRANSLATIONS_DIR / f"{lang}.toml").exists():
        _log.warning("No translation file for lang=%r, falling back to %r", lang, _FALLBACK_LANG)
        lang = _FALLBACK_LANG
    T.clear()
    T.update(_load_file(lang))
    _T_EN.clear()
    _T_EN.update(T if lang == _FALLBACK_LANG else _load_file(_FALLBACK_LANG))
    CURRENT_LANG = lang


def t(key: str) -> str:
    """Return the translated string for a dotted key like 'pdf.category'.

    Looks in the current language first, then in English, then returns the
    key itself so missing translations degrade gracefully.
    """
    parts = key.split(".", 1)
    if len(parts) == 2:
        section, name = parts
        for catalog in (T, _T_EN):
            value = catalog.get(section, {}).get(name)
            if value is not None:
                return str(value)
        return key
    for catalog in (T, _T_EN):
        if key in catalog:
            return str(catalog[key])
    return key
