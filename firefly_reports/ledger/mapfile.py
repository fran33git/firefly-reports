"""Safe textual insertion of new entries into an existing ``beancount_map.yaml``. Pure, no I/O.

The file is edited line by line (never parsed and dumped) so the comments, order and
formatting the user wrote stay exactly as they are. Anything the insertion cannot handle
with certainty makes ``append_entries`` return ``None`` and the caller falls back to
printing a snippet.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import yaml

_KEY = re.compile(r"^(\s*)([A-Za-z_][\w-]*)\s*:(.*)$")
_DEFAULT_INDENT = 2


class _UnsafeError(Exception):
    """The file has a shape the insertion does not handle with certainty."""


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_content(line: str) -> bool:
    """A non-blank, non-comment line."""
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def _value(rest: str) -> str:
    """What follows ``key:`` on its line, without a trailing comment."""
    rest = rest.strip()
    if rest.startswith("#"):
        return ""
    return re.sub(r"\s+#.*$", "", rest).strip()


def _find_top(lines: list[str], key: str) -> int | None:
    hits = [
        i
        for i, line in enumerate(lines)
        if (m := _KEY.match(line)) and not m.group(1) and m.group(2) == key
    ]
    if len(hits) > 1:
        raise _UnsafeError
    return hits[0] if hits else None


def _block_end(lines: list[str], start: int) -> int:
    """First line after *start* that is not indented (exclusive end of the key's block)."""
    for j in range(start + 1, len(lines)):
        if lines[j].strip() and not lines[j][0].isspace():
            return j
    return len(lines)


def _open_key_line(lines: list[str], idx: int) -> None:
    """Accept ``key:`` (block) and rewrite ``key: {}``; anything else is unsafe."""
    match = _KEY.match(lines[idx])
    if match is None:
        raise _UnsafeError
    value = _value(match.group(3))
    if value == "":
        return
    if value == "{}":
        lines[idx] = re.sub(r"\s*\{\}", "", lines[idx], count=1)
        return
    raise _UnsafeError


def _after_last_content(lines: list[str], start: int, end: int) -> int:
    """Index just after the last non-blank line in (*start*, *end*), else after *start*."""
    for j in range(end - 1, start, -1):
        if lines[j].strip():
            return j + 1
    return start + 1


def _first_content_indent(lines: list[str], start: int, end: int) -> int | None:
    for j in range(start + 1, end):
        if _is_content(lines[j]):
            return _indent(lines[j])
    return None


def _insert(lines: list[str], pos: int, new: Sequence[str], eol: str) -> None:
    if pos > 0 and not lines[pos - 1].endswith("\n"):
        lines[pos - 1] += eol
    lines[pos:pos] = [line + eol for line in new]


def _append_section(lines: list[str], body: Sequence[str], eol: str) -> None:
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += eol
    if lines and lines[-1].strip():
        lines.append(eol)
    lines.extend(line + eol for line in body)


def _add_entries(lines: list[str], key: str, entries: Sequence[str], eol: str) -> None:
    idx = _find_top(lines, key)
    if idx is None:
        _append_section(lines, [f"{key}:", *(" " * _DEFAULT_INDENT + e for e in entries)], eol)
        return
    _open_key_line(lines, idx)
    end = _block_end(lines, idx)
    indent = _first_content_indent(lines, idx, end) or _DEFAULT_INDENT
    _insert(lines, _after_last_content(lines, idx, end), [" " * indent + e for e in entries], eol)


def _add_child(lines: list[str], idx: int, name: str, entries: Sequence[str], eol: str) -> None:
    """Add *entries* to the ``name:`` block inside the block that starts at line *idx*."""
    end = _block_end(lines, idx)
    ind1 = _first_content_indent(lines, idx, end) or _DEFAULT_INDENT
    children = [
        j
        for j in range(idx + 1, end)
        if (m := _KEY.match(lines[j])) and len(m.group(1)) == ind1 and m.group(2) == name
    ]
    if len(children) > 1:
        raise _UnsafeError
    if not children:
        body = [" " * ind1 + f"{name}:", *(" " * (ind1 + _DEFAULT_INDENT) + e for e in entries)]
        _insert(lines, _after_last_content(lines, idx, end), body, eol)
        return
    j = children[0]
    _open_key_line(lines, j)
    child_end = next(
        (k for k in range(j + 1, end) if lines[k].strip() and _indent(lines[k]) <= ind1), end
    )
    indent = _first_content_indent(lines, j, child_end) or ind1 + _DEFAULT_INDENT
    _insert(
        lines, _after_last_content(lines, j, child_end), [" " * indent + e for e in entries], eol
    )


def _add_categories(
    lines: list[str], expense: Sequence[str], income: Sequence[str], eol: str
) -> None:
    idx = _find_top(lines, "categories")
    blocks = (("expense", expense), ("income", income))
    if idx is None:
        body = ["categories:"]
        for name, entries in blocks:
            if entries:
                body += [f"  {name}:", *("    " + e for e in entries)]
        _append_section(lines, body, eol)
        return
    _open_key_line(lines, idx)
    for name, entries in blocks:
        if entries:
            _add_child(lines, idx, name, entries, eol)


def append_entries(
    text: str, *, accounts: Sequence[str], expense: Sequence[str], income: Sequence[str]
) -> str | None:
    """Return *text* with the entries added, or ``None`` if that cannot be done safely.

    Each entry is a formatted line without indentation (``"Name": "Account"  # note``).
    New entries go at the end of the matching block (``accounts:``, ``categories:`` ->
    ``expense:`` / ``income:``); a missing section or block is created at the end of the
    file. Existing lines are never modified, apart from ``key: {}`` becoming ``key:``.
    The dominant line ending is kept and a final newline is added if missing.
    """
    if not (accounts or expense or income):
        return text
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    try:
        if accounts:
            _add_entries(lines, "accounts", accounts, eol)
        if expense or income:
            _add_categories(lines, expense, income, eol)
    except _UnsafeError:
        return None
    return "".join(lines)


def _contains(old: Any, new: Any) -> bool:
    if old is None:
        return True
    if isinstance(old, dict):
        return isinstance(new, dict) and all(
            k in new and _contains(v, new[k]) for k, v in old.items()
        )
    return bool(old == new)


def _entry_pairs(entries: Sequence[str]) -> dict[str, str]:
    """``{name: account}`` of the formatted entry lines (comment lines contribute nothing)."""
    pairs: dict[str, str] = {}
    for entry in entries:
        data = yaml.safe_load(entry)
        if isinstance(data, dict):
            pairs.update({str(k): str(v) for k, v in data.items()})
    return pairs


def holds_entries(
    text: str, *, accounts: Sequence[str], expense: Sequence[str], income: Sequence[str]
) -> bool:
    """True if *text* maps every given entry, with the proposed value, in the right section."""
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return False
    categories = data.get("categories") or {}
    wanted = (
        (data.get("accounts"), accounts),
        (categories.get("expense"), expense),
        (categories.get("income"), income),
    )
    for found, entries in wanted:
        found = found or {}
        for name, account in _entry_pairs(entries).items():
            if str(found.get(name, found.get(int(name) if name.isdigit() else name))) != account:
                return False
    return True


def preserves_entries(old: str, new: str) -> bool:
    """True if *new* is valid YAML that still holds every entry of *old* with the same value."""
    try:
        old_data, new_data = yaml.safe_load(old), yaml.safe_load(new)
    except yaml.YAMLError:
        return False
    return new_data is not None and _contains(old_data, new_data)
