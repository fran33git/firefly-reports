"""The BLOCK data can be re-derived from the repository, offline.

The fixtures are public CA certificates, named by their SHA-256 fingerprint. The fingerprints below
are the ones published in Mozilla Bugzilla 2083449 (comments 0 and 2) for the eight eMudhra
intermediates and, for the root, in the emSign ECC Root CA - G3 record. A fixture is trusted only
because it hashes back to its published fingerprint; the list hashes are then derived from it.
"""

import hashlib
from pathlib import Path

import pytest

from firefly_reports.tlstrust.lists import ENTRIES
from firefly_reports.tlstrust.spki import spki_sha256

FIXTURES = Path(__file__).parent.parent / "fixtures" / "emudhra"

# (intermediate, issuer, certificate SHA-256 fingerprint), Bugzilla 2083449
INTERMEDIATES = [
    (
        "EM EV TLS CA - G3B",
        "emudhra",
        "e7568fe6e12331f4fd7de61da4c7559d0f8eb192a218d4741a3ba75184333838",
    ),
    (
        "EM EV TLS CA - G3B",
        "sectigo",
        "579480aea166290bd3c643589e795fc0d0e54e86505d180f1dff99efd3199512",
    ),
    (
        "EM OV TLS CA - G3B",
        "emudhra",
        "98b896625c0c230adeec3eb2cf6aad5001ecf9156a68644e82374ce5833bc25b",
    ),
    (
        "EM OV TLS CA - G3B",
        "sectigo",
        "5f1ded4dd590af74631290cf073b122a2aac6a1fa479778a0bd43579bd832699",
    ),
    (
        "EM DV TLS CA - G3B",
        "emudhra",
        "42c4accd12c4f59597925e1a08a7a90102608543809308d50ec427e118ba1493",
    ),
    (
        "EM DV TLS CA - G3B",
        "sectigo",
        "45a883f349aedfd5f3a649b5498ffb121712ba8b448f3f2a91dbc5a766fcddbe",
    ),
    (
        "EM EV TLS CA - G3C",
        "emudhra",
        "432ec25f0d28de9006d97bf752f17bbb2cd41f669933fcb072d9a1148d0261f3",
    ),
    (
        "EM EV TLS CA - G3C",
        "sectigo",
        "fd9d5c2dbbd4995ab69b8d50c439d9527b00529199c2fd01b2174eb58f07021f",
    ),
    (
        "EM OV TLS CA - G3C",
        "emudhra",
        "cb6e15165ac802e9b3f993f16c25d41f4e81c21ebde71ae1b012ac00bf9c7c3f",
    ),
    (
        "EM OV TLS CA - G3C",
        "sectigo",
        "7485b51c0ed192878fa1d2f948fb529ae1842cc5086c4b67f7be5b2039de9489",
    ),
    (
        "EM DV TLS CA - G3C",
        "emudhra",
        "0164d7ceae5bb909c272af151ff44b1177ae9b47d9424b94f1d9558c30934d19",
    ),
    (
        "EM DV TLS CA - G3C",
        "sectigo",
        "62b7f9868263f72f6911fc78ceaf72c1979158b7368bf648683bb2aa39b02e72",
    ),
    (
        "EM OV CS CA - G3B",
        "emudhra",
        "9e39de2881273acc225a149c72ba3e0f51424963669ab633ee1dc7df5db067b4",
    ),
    (
        "EM OV CS CA - G3B",
        "sectigo",
        "a496e23ac0cab8155fc9b117b97eae368efcbb9041aec8804d5a308d2d01c2d8",
    ),
    (
        "EM OV CS CA - G3C",
        "emudhra",
        "4b2460a466f95fd40113bcdcca2ceb29b3b093921de45474da7df48874c630b1",
    ),
    (
        "EM OV CS CA - G3C",
        "sectigo",
        "84112972b8e59d14560ae7e7119654474aad119990cf3722bfc1e3b91615e1fd",
    ),
]
G3_ROOT = "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"


def _der(fingerprint: str) -> bytes:
    return (FIXTURES / f"{fingerprint}.der").read_bytes()


def test_every_fixture_hashes_back_to_its_published_fingerprint():
    for _, _, fingerprint in INTERMEDIATES:
        assert hashlib.sha256(_der(fingerprint)).hexdigest() == fingerprint
    assert hashlib.sha256(_der(G3_ROOT)).hexdigest() == G3_ROOT


def test_the_eight_block_entries_are_exactly_the_keys_of_those_certificates():
    block = {
        e.label: e.spki_sha256 for e in ENTRIES if e.level == "block" and e.label.startswith("EM ")
    }
    derived: dict[str, set[str]] = {}
    for name, _, fingerprint in INTERMEDIATES:
        derived.setdefault(name, set()).add(spki_sha256(_der(fingerprint)))
    assert len(block) == 8 and set(block) == set(derived)
    for name, hashes in derived.items():
        assert hashes == {block[name]}, name


def test_the_emudhra_and_the_sectigo_certificate_of_each_intermediate_share_one_key():
    for name in {n for n, _, _ in INTERMEDIATES}:
        keys = {spki_sha256(_der(fp)) for n, _, fp in INTERMEDIATES if n == name}
        assert len(keys) == 1, name


def test_the_g3_root_entry_matches_the_root_certificate():
    entry = next(e for e in ENTRIES if e.label == "emSign ECC Root CA - G3")
    assert entry.level == "block" and entry.spki_sha256 == spki_sha256(_der(G3_ROOT))


# --- the compromise itself, re-derived: P-384 keys whose private scalar is below 256 ---------------
_P = 2**384 - 2**128 - 2**96 + 2**32 - 1
_A = _P - 3
_G = (
    0xAA87CA22BE8B05378EB1C71EF320AD746E1D3B628BA79B9859F741E082542A385502F25DBF55296C3A545E3872760AB7,
    0x3617DE4A96262C6F5D9E98BF9292DC29F8F41DBD289A147CE9DA3113B5F0B8C00A60B1CE1D7E819D7A431D7C90EA0E5F,
)


def _add(p, q):
    if p is None or q is None:
        return p or q
    if p[0] == q[0] and (p[1] + q[1]) % _P == 0:
        return None
    if p == q:
        slope = (3 * p[0] * p[0] + _A) * pow(2 * p[1], -1, _P) % _P
    else:
        slope = (q[1] - p[1]) * pow(q[0] - p[0], -1, _P) % _P
    x = (slope * slope - p[0] - q[0]) % _P
    return x, (slope * (p[0] - x) - p[1]) % _P


def _small_multiples() -> dict[tuple[int, int], int]:
    table, point = {}, None
    for d in range(1, 256):
        point = _add(point, _G)
        table[point] = d
    return table


def _public_point(der: bytes) -> tuple[int, int]:
    marker = b"\x03\x62\x00\x04"  # BIT STRING, 98 bytes, 0 unused bits, uncompressed point
    start = der.index(marker) + len(marker)
    raw = der[start : start + 96]
    return int.from_bytes(raw[:48], "big"), int.from_bytes(raw[48:], "big")


def test_every_blocked_intermediate_key_is_a_p384_key_with_a_tiny_private_scalar():
    small = _small_multiples()
    scalars: dict[str, set[int]] = {}
    for name, _, fingerprint in INTERMEDIATES:
        point = _public_point(_der(fingerprint))
        assert point in small, f"{name}: public key is not d*G for d < 256"
        scalars.setdefault(name, set()).add(small[point])
    assert all(len(values) == 1 for values in scalars.values())  # both certificates, same key


@pytest.mark.parametrize("fingerprint", [fp for _, _, fp in INTERMEDIATES][:1])
def test_the_weakness_check_does_not_pass_for_an_ordinary_key(fingerprint, tmp_path):
    """Guard against a vacuous check: a normal P-384 key is not in the small-multiples table."""
    from tests.tls_helpers import cert_der, make_cert

    cert, _ = make_cert(tmp_path, algo="ec")
    assert _public_point(cert_der(cert)) not in _small_multiples()
