"""Throwaway certificates for the TLS trust tests, made with the ``openssl`` command line.

No ``cryptography`` dependency: the SPKI reader is checked against what OpenSSL itself computes.
Where ``openssl`` is missing the tests skip locally, but fail under CI so they cannot silently
stop running.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import ssl
import subprocess
from pathlib import Path

import pytest

_ALGOS = {
    "rsa": ["-newkey", "rsa:2048"],
    "ec": ["-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:secp384r1"],
}


def require_openssl() -> str:
    exe = shutil.which("openssl")
    if exe is None:
        if os.environ.get("CI"):
            pytest.fail("openssl is required by the TLS trust tests in CI")
        pytest.skip("openssl command line not available")
    return exe


def make_cert(tmp_path: Path, *, algo: str = "rsa", name: str = "srv") -> tuple[Path, Path]:
    """A self-signed certificate valid for 127.0.0.1 and localhost: (certificate, key) paths."""
    exe = require_openssl()
    cert, key = tmp_path / f"{name}.pem", tmp_path / f"{name}.key"
    subprocess.run(
        [
            exe,
            "req",
            "-x509",
            *_ALGOS[algo],
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "2",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1,DNS:localhost",
        ],
        check=True,
        capture_output=True,
    )
    return cert, key


def cert_der(cert: Path) -> bytes:
    return ssl.PEM_cert_to_DER_cert(cert.read_text())


def openssl_spki_sha256(cert: Path) -> str:
    """The reference value: OpenSSL extracts the public key, we hash its DER SPKI."""
    exe = require_openssl()
    pub = subprocess.run(
        [exe, "x509", "-in", str(cert), "-pubkey", "-noout"], check=True, capture_output=True
    ).stdout
    spki = subprocess.run(
        [exe, "pkey", "-pubin", "-outform", "der"], input=pub, check=True, capture_output=True
    ).stdout
    return hashlib.sha256(spki).hexdigest()


class FakeCertificate:
    """Stands in for ``ssl._ssl.Certificate``, what the private OpenSSL binding returns."""

    def __init__(self, der: bytes) -> None:
        self._der = der

    def public_bytes(self) -> str:
        return ssl.DER_cert_to_PEM_cert(self._der)


class _SslObj:
    """The private ``_sslobj`` of Python 3.11/3.12: the only place the chain can be read."""

    def __init__(self, chain: list[bytes]) -> None:
        self._chain = chain

    def get_verified_chain(self) -> list[FakeCertificate]:
        return [FakeCertificate(der) for der in self._chain]


class FakeTlsSocket:
    """A connected TLS socket as the client sees it: a verified chain, and a record of what is sent.

    ``chain`` is a list of DER certificates, ``None`` for a socket with no chain API at all.
    """

    def __init__(self, chain: list[bytes] | None) -> None:
        self.sent: list[bytes] = []
        self.closed = False
        if chain is not None:
            self._sslobj = _SslObj(chain)

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def close(self) -> None:
        self.closed = True

    def shutdown(self, how: int) -> None:
        pass
