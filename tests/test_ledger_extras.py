"""Extra metadata, IBANs and transaction links in the conversion (offline)."""

from tests.test_ledger_category_mode import convert, deposit, split, withdrawal


def test_bill_and_reference_metadata_on_transaction():
    sp = withdrawal("1", bill_name="Affitto", internal_reference="R-9")
    (tx,) = convert([sp]).transactions
    assert dict(tx.extra) == {"bill": "Affitto", "reference": "R-9"}
    assert all(p.extra == () for p in tx.postings)


def test_empty_values_are_not_exported():
    (tx,) = convert(
        [withdrawal("1", bill_name="", internal_reference=None, external_url=" ")]
    ).transactions
    assert tx.extra == ()


def test_all_fixed_keys_are_mapped():
    sp = withdrawal(
        "1", bill_name="B", internal_reference="R", external_id="E", external_url="U",
        book_date="2025-01-02T00:00:00+01:00", interest_date="2025-01-03T00:00:00+01:00",
    )  # fmt: skip
    (tx,) = convert([sp]).transactions
    assert dict(tx.extra) == {
        "bill": "B",
        "reference": "R",
        "external_id": "E",
        "external_url": "U",
        "book_date": "2025-01-02",
        "interest_date": "2025-01-03",
    }


def test_diverging_bill_goes_on_category_postings():
    g = {"group_id": "G"}
    splits = [
        withdrawal("1", "Food", "A", "10.00", bill_name="Luce", **g),
        withdrawal("2", "Home", "A", "5.00", **g),
    ]
    (tx,) = convert(splits).transactions
    assert tx.extra == ()
    assert [dict(p.extra) for p in tx.postings] == [{}, {"bill": "Luce"}, {}]


def test_agreeing_bill_moves_to_transaction():
    g = {"group_id": "G"}
    splits = [
        withdrawal("1", "Food", "A", "10.00", bill_name="Luce", **g),
        withdrawal("2", "Home", "A", "5.00", bill_name="Luce", **g),
    ]
    (tx,) = convert(splits).transactions
    assert dict(tx.extra) == {"bill": "Luce"}
    assert all(p.extra == () for p in tx.postings)


def test_extra_metadata_also_in_account_mode():
    (tx,) = convert([withdrawal("1", bill_name="Luce")], mode="account").transactions
    assert dict(tx.extra) == {"bill": "Luce"}


def _with_ibans(*pairs):
    splits = []
    for i, (src_iban, dst_iban) in enumerate(pairs, start=1):
        splits.append(withdrawal(str(i), source_iban=src_iban, destination_iban=dst_iban))
    return splits


def test_iban_of_real_account_is_exported():
    ledger = convert(_with_ibans(("IT01", "IT99")))
    assert ledger.ibans == {"Assets:Bank": "IT01"}


def test_counterpart_iban_not_exported_in_either_mode():
    for mode in ("category", "account"):
        assert "Expenses:Sports-Bar" not in convert(_with_ibans(("IT01", "IT99")), mode).ibans


def test_iban_most_frequent_wins_tie_alphabetical():
    assert convert(_with_ibans(("IT02", None), ("IT01", None), ("IT02", None))).ibans == {
        "Assets:Bank": "IT02"
    }
    assert convert(_with_ibans(("IT02", None), ("IT01", None))).ibans == {"Assets:Bank": "IT01"}


def test_missing_iban_gives_no_entry():
    assert convert([withdrawal("1")]).ibans == {}


def link(link_id, inward, outward):
    return {"id": link_id, "inward_id": inward, "outward_id": outward}


def test_link_names_shared_on_both_transactions():
    ledger = convert([withdrawal("10"), deposit("11", "Rimborsi")], links=[link("5", "10", "11")])
    assert [tx.links for tx in ledger.transactions] == [("firefly-link-5",), ("firefly-link-5",)]
    assert ledger.skipped_links == 0


def test_link_to_split_inside_multi_split_group():
    g = {"group_id": "G"}
    splits = [withdrawal("1", "Food", "A", **g), withdrawal("2", "Home", "A", **g), deposit("3")]
    ledger = convert(splits, links=[link("7", "2", "3")])
    assert {tx.firefly_id: tx.links for tx in ledger.transactions} == {
        "1": ("firefly-link-7",),
        "3": ("firefly-link-7",),
    }


def test_link_with_missing_endpoint_is_skipped_and_counted():
    ledger = convert([withdrawal("10")], links=[link("5", "10", "99"), link("6", "98", "99")])
    assert ledger.transactions[0].links == ()
    assert ledger.skipped_links == 2


def test_transaction_with_two_links_gets_both_sorted():
    splits = [withdrawal("10"), deposit("11", "R"), deposit("12", "S")]
    ledger = convert(splits, links=[link("9", "10", "12"), link("3", "10", "11")])
    by_id = {tx.firefly_id: tx.links for tx in ledger.transactions}
    assert by_id["10"] == ("firefly-link-3", "firefly-link-9")
    assert by_id["11"] == ("firefly-link-3",) and by_id["12"] == ("firefly-link-9",)


def test_link_between_splits_of_the_same_transaction_is_ignored():
    g = {"group_id": "G"}
    ledger = convert(
        [withdrawal("1", "A", "X", **g), withdrawal("2", "B", "X", **g)],
        links=[link("4", "1", "2")],
    )
    assert ledger.transactions[0].links == () and ledger.skipped_links == 0


def test_transfer_split_unaffected_by_extras():
    sp = split("1", "transfer", "A", "Asset account", "B", "Asset account", bill_name="X")
    (tx,) = convert([sp]).transactions
    assert dict(tx.extra) == {"bill": "X"}
