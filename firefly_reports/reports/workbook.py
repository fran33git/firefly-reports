"""Workbook assembly: sheets in a fixed order, empty data skipped."""

from collections.abc import Sequence
from pathlib import Path

from openpyxl import Workbook

from firefly_reports.reports.spec import ReportData, SheetWriter


def write_workbook(sheets: Sequence[tuple[SheetWriter, ReportData]], path: Path) -> None:
    """Write *sheets* (writer, data) in the given order to *path*; falsy data is skipped."""
    wb = Workbook()
    wb.remove(wb.active)
    for writer, data in sheets:
        if data:
            writer(wb, data)
    wb.save(path)
