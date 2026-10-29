import hashlib
import re
import ssl
from pathlib import Path

import certifi
import pytest

from firefly_reports.tlstrust.lists import ENTRIES, LIST_DATE, TrustEntry, index
from firefly_reports.tlstrust.spki import spki_sha256

ROOTS = Path(__file__).parent.parent / "fixtures" / "emudhra_roots"
_PEM = re.compile(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.S)


@pytest.fixture(scope="module")
def certifi_spki() -> set[str]:
    text = Path(certifi.where()).read_text(encoding="ascii")
    return {spki_sha256(ssl.PEM_cert_to_DER_cert(pem)) for pem in _PEM.findall(text)}


def test_hashes_are_64_lowercase_hex_and_unique():
    hashes = [e.spki_sha256 for e in ENTRIES]
    assert hashes, "the lists must not be empty"
    assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes)
    assert len(set(hashes)) == len(hashes)


def test_every_entry_has_a_primary_source():
    for entry in ENTRIES:
        assert entry.sources, entry.label
        assert all(s.startswith("https://") for s in entry.sources), entry.label
        assert entry.reason.strip() and entry.label.strip()
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry.added), entry.label


def test_list_date_is_an_iso_date():
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", LIST_DATE)


def test_no_block_hash_in_current_certifi(certifi_spki):
    # A BLOCK key that the bundle still trusts would mean stale or wrong data (or a bundle to update).
    blocked_but_trusted = [
        e.label for e in ENTRIES if e.level == "block" and e.spki_sha256 in certifi_spki
    ]
    assert blocked_but_trusted == []


def test_warn_roots_are_real_roots():
    # Proves the WARN hashes are real. The roots are committed (named by their SHA-256 fingerprint,
    # taken from the certifi bundle of 2026-10-19) because certifi drops roots over time: a root the
    # bundle no longer ships is still a root worth a warning on older systems.
    roots = [e for e in ENTRIES if e.level == "warn" and "Root" in e.label]
    assert roots, "the initial WARN list is the remaining eMudhra roots"
    fixtures = {}
    for path in ROOTS.glob("*.der"):
        der = path.read_bytes()
        assert hashlib.sha256(der).hexdigest() == path.stem, path.name
        fixtures[spki_sha256(der)] = path.name
    assert [e.label for e in roots if e.spki_sha256 not in fixtures] == []


def test_levels_are_block_or_warn():
    assert {e.level for e in ENTRIES} <= {"block", "warn"}
    assert any(e.level == "block" for e in ENTRIES)


def test_index_maps_hash_to_entry():
    table = index()
    assert set(table) == {e.spki_sha256 for e in ENTRIES}
    first = ENTRIES[0]
    assert table[first.spki_sha256] is first


def test_index_rejects_duplicate_hashes():
    a = TrustEntry("a" * 64, "A", "block", "r", ("https://example.org",), "2026-10-29")
    b = TrustEntry("a" * 64, "B", "warn", "r", ("https://example.org",), "2026-10-29")
    with pytest.raises(ValueError):
        index([a, b])
