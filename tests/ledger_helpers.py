"""Shared helpers for the ledger tests."""

from firefly_reports.ledger.export import ExportRequest


def export_request(*args, **kwargs) -> ExportRequest:
    """``ExportRequest`` that opts out of the mapping safety block.

    Most tests export without a mapping file on purpose; the block itself is
    covered in ``test_ledger_safety_block.py``.
    """
    kwargs.setdefault("allow_unmapped", True)
    return ExportRequest(*args, **kwargs)
