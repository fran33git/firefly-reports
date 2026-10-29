"""Compare a verified chain with the trust lists. Pure: no I/O, never raises."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from firefly_reports.tlstrust.lists import TrustEntry
from firefly_reports.tlstrust.spki import spki_sha256


@dataclass(frozen=True)
class Match:
    entry: TrustEntry
    position: int  # index in the chain as given: 0 is the leaf


@dataclass(frozen=True)
class Verdict:
    hashes: tuple[str, ...]  # SPKI hashes of the certificates that could be read, in order
    blocked: tuple[Match, ...]
    warned: tuple[Match, ...]
    unparsable: int  # certificates whose key could not be extracted (never counted as clean)


def evaluate(certs: Sequence[bytes], table: Mapping[str, TrustEntry]) -> Verdict:
    hashes: list[str] = []
    blocked: list[Match] = []
    warned: list[Match] = []
    unparsable = 0
    for position, der in enumerate(certs):
        try:
            digest = spki_sha256(der)
        except ValueError:
            unparsable += 1
            continue
        hashes.append(digest)
        entry = table.get(digest)
        if entry is None:
            continue
        (blocked if entry.level == "block" else warned).append(Match(entry, position))
    return Verdict(tuple(hashes), tuple(blocked), tuple(warned), unparsable)
