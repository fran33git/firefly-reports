import pytest

from firefly_reports.tlstrust.lists import TrustEntry, index
from firefly_reports.tlstrust.policy import evaluate
from firefly_reports.tlstrust.spki import spki_sha256
from tests.tls_helpers import cert_der, make_cert


def _entry(der: bytes, label: str, level: str) -> TrustEntry:
    return TrustEntry(
        spki_sha256(der), label, level, "test reason", ("https://example.org",), "2026-10-29"
    )  # type: ignore[arg-type]


@pytest.fixture
def chain(tmp_path):
    """Three distinct real certificates standing in for [leaf, intermediate, root]."""
    return [cert_der(make_cert(tmp_path, name=n)[0]) for n in ("leaf", "inter", "root")]


def test_clean_chain_has_no_matches(chain):
    verdict = evaluate(chain, index([]))
    assert verdict.blocked == () and verdict.warned == () and verdict.unparsable == 0
    assert verdict.hashes == tuple(spki_sha256(c) for c in chain)


def test_blocked_intermediate_under_a_trusted_root_is_found(chain):
    table = index([_entry(chain[1], "Weak Intermediate", "block")])
    verdict = evaluate(chain, table)
    assert [(m.entry.label, m.position) for m in verdict.blocked] == [("Weak Intermediate", 1)]
    assert verdict.warned == ()


def test_warn_only_chain_is_warned_not_blocked(chain):
    verdict = evaluate(chain, index([_entry(chain[2], "Some Root", "warn")]))
    assert [(m.entry.label, m.position) for m in verdict.warned] == [("Some Root", 2)]
    assert verdict.blocked == ()


def test_block_and_warn_in_one_chain_are_both_reported(chain):
    table = index([_entry(chain[0], "A", "block"), _entry(chain[2], "B", "warn")])
    verdict = evaluate(chain, table)
    assert len(verdict.blocked) == 1 and len(verdict.warned) == 1


def test_a_malformed_certificate_is_counted_and_the_rest_still_evaluated(chain):
    table = index([_entry(chain[2], "Weak Root", "block")])
    verdict = evaluate([chain[0], b"\x30\x03garbage", chain[2]], table)
    assert verdict.unparsable == 1
    assert len(verdict.hashes) == 2
    assert [(m.entry.label, m.position) for m in verdict.blocked] == [("Weak Root", 2)]


def test_evaluate_never_raises_on_hostile_input():
    verdict = evaluate([b"", b"\x00", b"\xff" * 5, b"\x30\x84\xff\xff\xff\xff"], index([]))
    assert verdict.unparsable == 4
    assert verdict.hashes == ()
