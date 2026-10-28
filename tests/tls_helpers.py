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
