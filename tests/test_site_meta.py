"""Structural checks for the public docs site: wiki pages and docs/site-meta.json.

No network, no new dependencies: only json, pathlib and re.
"""

import json
import re
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = REPO_ROOT / "docs" / "wiki"
SITE_META = REPO_ROOT / "docs" / "site-meta.json"

FIELDS = ("description", "audience", "kind", "updated", "order")
AUDIENCES = ("user", "developer")
KINDS = ("guide", "reference")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
H1_RE = re.compile(r"^# (.+)$", re.MULTILINE)
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def wiki_pages() -> list[Path]:
    return sorted(p for p in WIKI_DIR.glob("*.md") if p.name != "_Sidebar.md")


def strip_code_blocks(text: str) -> str:
    """Return the text outside fenced code blocks; fail if a fence is left open."""
    kept: list[str] = []
    in_block = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_block = not in_block
            continue
        if not in_block:
            kept.append(line)
    assert not in_block, "unclosed fenced code block"
    return "\n".join(kept)


def load_meta() -> dict:
    return json.loads(SITE_META.read_text(encoding="utf-8"))


def test_every_page_has_an_entry_and_vice_versa() -> None:
    pages = {p.name for p in wiki_pages()}
    meta = load_meta()
    assert set(meta) == {"pages"}
    entries = set(meta["pages"])
    assert entries == pages, (
        f"site-meta.json pages and docs/wiki/ disagree: "
        f"only on disk: {sorted(pages - entries)}, only in meta: {sorted(entries - pages)}"
    )


def test_entry_fields_and_values() -> None:
    meta = load_meta()
    orders: list[int] = []
    for name, entry in meta["pages"].items():
        assert set(entry) == set(FIELDS), f"{name}: fields must be exactly {FIELDS}"
        description = entry["description"]
        assert isinstance(description, str)
        assert 1 <= len(description) <= 155, f"{name}: description length {len(description)}"
        assert entry["audience"] in AUDIENCES, f"{name}: audience {entry['audience']!r}"
        assert entry["kind"] in KINDS, f"{name}: kind {entry['kind']!r}"
        updated = entry["updated"]
        assert isinstance(updated, str) and ISO_DATE_RE.match(updated), (
            f"{name}: updated {updated!r}"
        )
        date.fromisoformat(updated)  # raises on impossible dates like 2026-13-40
        order = entry["order"]
        assert isinstance(order, int) and not isinstance(order, bool), f"{name}: order {order!r}"
        orders.append(order)
    assert len(set(orders)) == len(orders), "order values must be unique"


def test_single_short_h1_per_page() -> None:
    for page in wiki_pages():
        text = strip_code_blocks(page.read_text(encoding="utf-8"))
        titles = H1_RE.findall(text)
        assert len(titles) == 1, f"{page.name}: expected exactly one H1, found {len(titles)}"
        assert len(titles[0]) <= 60, f"{page.name}: H1 too long ({len(titles[0])} chars)"


def test_wikilinks_point_to_existing_pages() -> None:
    names = {p.stem for p in wiki_pages()}
    names.add("Home")
    for page in wiki_pages():
        text = strip_code_blocks(page.read_text(encoding="utf-8"))
        for match in WIKILINK_RE.finditer(text):
            raw = match.group(1)
            target = raw.split("\\|")[0].split("|")[0].strip()
            assert target in names, f"{page.name}: dead wikilink [[{raw}]]"


def test_code_blocks_closed() -> None:
    for page in wiki_pages():
        strip_code_blocks(page.read_text(encoding="utf-8"))  # asserts on unclosed fences


def test_file_formatting() -> None:
    raw = SITE_META.read_text(encoding="utf-8")
    assert raw.endswith("\n") and not raw.endswith("\n\n")
    assert "\t" not in raw
    meta = load_meta()
    assert list(meta["pages"]) == sorted(meta["pages"]), "page keys must be sorted"
