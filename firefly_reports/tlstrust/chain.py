"""Read the certificate chain OpenSSL verified for a connected TLS socket.

Two strategies behind one function:

* Python 3.13+: ``SSLSocket.get_verified_chain()``, a public method returning DER ``bytes``.
* Python 3.11/3.12: the same method on the private ``_sslobj``, returning ``_ssl.Certificate``
  objects that are converted to DER. ``tests/test_tls_binding_guard.py`` fails in CI if that
  binding ever disappears, so a silent downgrade to "not checked" cannot go unnoticed.

The verified chain (not the one the server sent) is what the check must use: it is the chain
OpenSSL actually built to a trust anchor, anchor included.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from typing import Any, Literal

ChainPath = Literal["public", "private", "unavailable"]


@dataclass(frozen=True)
class ChainRead:
    certs: tuple[bytes, ...]
    path: ChainPath
    reason: str | None = None

    @property
    def checked(self) -> bool:
        """An empty chain is never "clean": it means nothing was read."""
        return bool(self.certs)


def _der(cert: Any) -> bytes:
    if isinstance(cert, bytes):
        return cert
    return ssl.PEM_cert_to_DER_cert(cert.public_bytes())


def read_verified_chain(sock: object) -> ChainRead:
    """The DER certificates of the verified chain of *sock*; never raises."""
    path: ChainPath
    reader = getattr(sock, "get_verified_chain", None)
    if callable(reader):
        path = "public"
    else:
        reader = getattr(getattr(sock, "_sslobj", None), "get_verified_chain", None)
        if not callable(reader):
            return ChainRead((), "unavailable", "no chain API on this Python or socket")
        path = "private"
    try:
        certs = tuple(_der(cert) for cert in reader())
    except Exception as exc:
        return ChainRead((), "unavailable", f"reading the chain failed ({type(exc).__name__})")
    if not certs:
        return ChainRead((), path, "the verified chain is empty (resumed TLS session?)")
    return ChainRead(certs, path)
