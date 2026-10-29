"""The CA key lists: BLOCK refuses the connection, WARN only warns.

Entries are keys (SPKI SHA-256), not certificates: a reissued or cross-signed certificate keeps the
key, and a key is what a CA incident compromises. The lists ship inside the release as code (a static
import is bundled by PyInstaller without extra data files) and are never user-editable.

Rules for changing them (see AGENTS.md): every entry cites a primary source, a hash is added only
after it was computed from the certificate itself (never copied from an article), and ``LIST_DATE``
moves with the change.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

Level = Literal["block", "warn"]


@dataclass(frozen=True)
class TrustEntry:
    spki_sha256: str
    label: str
    level: Level
    reason: str
    sources: tuple[str, ...]
    added: str


LIST_DATE: Final = "2026-10-29"

_INCIDENT = "https://bugzilla.mozilla.org/show_bug.cgi?id=2083449"
_GOOGLE = (
    "https://blog.google/security/"
    "protecting-chrome-and-android-users-from-compromised-emudhra-intermediate-ca-certificates/"
)
_EMUDHRA = "https://emudhra.com/en/post/certificate-security-incident"

_WEAK_KEY = (
    "eMudhra intermediate CA whose private key is recoverable (P-384 key generated on 2025-04-30 "
    "with a value below 256); revoked with reason caCompromise on 2026-10-18. The same key also "
    "signs a Sectigo cross-signed certificate under AAA Certificate Services, so the key is "
    "blocked, not the individual certificate"
)
_REVIEW = (
    "eMudhra root under review after the October 2026 key compromise: Chrome and Mozilla are "
    "assessing the remaining eMudhra roots and eMudhra is winding down public TLS issuance"
)


def _weak_intermediate(spki_sha256: str, label: str) -> TrustEntry:
    return TrustEntry(spki_sha256, label, "block", _WEAK_KEY, (_INCIDENT, _GOOGLE), LIST_DATE)


ENTRIES: Final[tuple[TrustEntry, ...]] = (
    # The eight intermediates (six TLS, two code signing). The key is shared by the certificate
    # issued by eMudhra and by its Sectigo cross-sign, so both chains are caught.
    _weak_intermediate(
        "e0254c7fcdc265e2f0f8a428dabb75ab4ae039b4872d62f5ee57f0877d5a8a41", "EM EV TLS CA - G3B"
    ),
    _weak_intermediate(
        "43bffa19d6ef651451f6841e019931e96f6f2eaeff28ab4b6f1ce4576de2717b", "EM OV TLS CA - G3B"
    ),
    _weak_intermediate(
        "ebed6475c2c2d80fcb199f3fe8dd6e6b3ce60b77eb15d4e42c3dec0c6f5b5105", "EM DV TLS CA - G3B"
    ),
    _weak_intermediate(
        "5c0660a2b164910d8ff589c18e14552e9e0ec237dcefe2cb736d41a4811f81a0", "EM EV TLS CA - G3C"
    ),
    _weak_intermediate(
        "63ecefee431d49523bc1136c4e72d0206a477086caf606cd5cf025686c109cf8", "EM OV TLS CA - G3C"
    ),
    _weak_intermediate(
        "49dd353dc2b919a3770645117d0e60c16115e7d1bc259eefe734b00ea434fe5f", "EM DV TLS CA - G3C"
    ),
    _weak_intermediate(
        "ec4ffa1ad0ac88081314b7aaffef6a91f97cd57291bb5ba686c5415f5eb4f6b6", "EM OV CS CA - G3B"
    ),
    _weak_intermediate(
        "92c063d67e8f14db71d288e11266ffdaf69cbf115f7bab14f3bc2f68d25e0e30", "EM OV CS CA - G3C"
    ),
    TrustEntry(
        "8d417db2dd8bf5e3084d1e3f196d583849d81bdd4c00c70b9d39369e96b8c782",
        "emSign ECC Root CA - G3",
        "block",
        "Root removed from the Mozilla and Chrome root stores after eight of the intermediates "
        "it signed were found to have recoverable private keys",
        (_INCIDENT, _GOOGLE),
        LIST_DATE,
    ),
    TrustEntry(
        "376a1a7082a593dccc20d561d119e9ab8d30f11cc321d0a37fa41f0df284e01c",
        "emSign Root CA - G1",
        "warn",
        _REVIEW,
        (_INCIDENT, _EMUDHRA),
        LIST_DATE,
    ),
    TrustEntry(
        "b7408b4d2be0238ba37004dd34e276c6019bd2f24c9db7d4980f5f6c359a4bcc",
        "emSign Root CA - C1",
        "warn",
        _REVIEW,
        (_INCIDENT, _EMUDHRA),
        LIST_DATE,
    ),
    TrustEntry(
        "eabc185c4e82d942b1a5978ba3c0181487d6b3b9974e5c49f72f6d0bd9637150",
        "emSign ECC Root CA - C3",
        "warn",
        _REVIEW,
        (_INCIDENT, _EMUDHRA),
        LIST_DATE,
    ),
)


def index(entries: Iterable[TrustEntry] = ENTRIES) -> dict[str, TrustEntry]:
    """Hash -> entry; a hash named twice is a data error, not something to resolve silently."""
    table: dict[str, TrustEntry] = {}
    for entry in entries:
        if entry.spki_sha256 in table:
            raise ValueError(f"duplicate SPKI hash in the trust lists: {entry.spki_sha256}")
        table[entry.spki_sha256] = entry
    return table
