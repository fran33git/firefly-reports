"""Excel sheet of the summary report."""

from typing import Any

from openpyxl import Workbook

from firefly_reports.i18n import t
from firefly_reports.render.fmt import period_str
from firefly_reports.render.xlsx.layout import (
    data_row,
    header_row,
    title_block,
    to_number,
)

# ─────────────────────────────────────────────────
# Monochrome palette
# ─────────────────────────────────────────────────


# ─────────────────────────────────────────────────
# Sheet 1 — Cash Flow Statement
# ─────────────────────────────────────────────────


def write_sheet(wb: Workbook, data: dict[str, Any]) -> None:
    ws = wb.create_sheet(t("excel.sheet_summary"))
    period = period_str(data["period_start"], data["period_end"])
    row = title_block(ws, t("titles.summary"), data["owner"], period)

    row = header_row(
        ws,
        row,
        [t("excel.col_summary_item"), t("excel.col_summary_value")],
        col_widths=[34, 24],
    )

    inst = data["instance"]
    counts = data["counts"]
    p = data["period"]

    sections = [
        (
            t("summary.section_instance"),
            [
                (t("summary.firefly_version"), inst["firefly_version"]),
                (t("summary.api_version"), inst["api_version"]),
                (t("summary.server_os"), inst["os"]),
                (t("summary.php_version"), inst["php_version"]),
                (t("summary.user_email"), inst["user_email"]),
                (t("summary.user_role"), inst["user_role"]),
            ],
        ),
        (
            t("summary.section_counts"),
            [
                (t("summary.asset_accounts"), str(counts["asset_accounts"])),
                (t("summary.liabilities"), str(counts["liabilities"])),
                (t("summary.budgets"), str(counts["budgets"])),
                (t("summary.bills"), str(counts["bills"])),
                (t("summary.piggy_banks"), str(counts["piggy_banks"])),
            ],
        ),
        (
            t("summary.section_period"),
            [
                (t("summary.tx_total"), str(p["tx_total"])),
                (t("summary.tx_deposits"), str(p["tx_deposits"])),
                (t("summary.tx_withdrawals"), str(p["tx_withdrawals"])),
                (t("summary.tx_transfers"), str(p["tx_transfers"])),
                (t("summary.first_tx_date"), p["first_tx_date"]),
                (t("summary.last_tx_date"), p["last_tx_date"]),
                (t("summary.accounts_used"), str(p["accounts_used"])),
                (t("summary.categories_used"), str(p["categories_used"])),
                (t("summary.payees_used"), str(p["payees_used"])),
                (t("summary.tags_used"), str(p["tags_used"])),
                (t("summary.avg_daily_income"), to_number(p["avg_daily_income"])),
                (t("summary.avg_daily_expense"), to_number(p["avg_daily_expense"])),
            ],
        ),
    ]

    for section_title, items in sections:
        row = data_row(ws, row, [section_title.upper(), ""], is_total=True)
        for label, value in items:
            row = data_row(ws, row, [label, value if value != "" else "—"], indent_col=1)
