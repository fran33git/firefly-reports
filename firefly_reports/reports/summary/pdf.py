"""PDF renderers of the summary report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Spacer,
)

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import corporate_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_modern_summary(data: dict[str, Any], output_path: str) -> None:
    """Instance & period summary (Modern only)."""
    st = corporate_styles()
    period = period_str(data["period_start"], data["period_end"])
    owner = data["owner"]
    sym = data["currency"]

    fn = page_decorator(owner, t("titles.summary"), period)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(t("titles.summary"), owner, period, None, st)

    CW = [7.0 * cm, 8.0 * cm]
    inst = data["instance"]
    counts = data["counts"]
    p = data["period"]

    sections = [
        (
            "summary.section_instance",
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
            "summary.section_counts",
            [
                (t("summary.asset_accounts"), str(counts["asset_accounts"])),
                (t("summary.liabilities"), str(counts["liabilities"])),
                (t("summary.budgets"), str(counts["budgets"])),
                (t("summary.bills"), str(counts["bills"])),
                (t("summary.piggy_banks"), str(counts["piggy_banks"])),
            ],
        ),
        (
            "summary.section_period",
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
                (
                    t("summary.avg_daily_income"),
                    fmt_num(p["avg_daily_income"], show_sym=True, sym=sym),
                ),
                (
                    t("summary.avg_daily_expense"),
                    fmt_num(p["avg_daily_expense"], show_sym=True, sym=sym),
                ),
            ],
        ),
    ]

    for section_key, items in sections:
        story.append(Paragraph(t(section_key).upper(), st["section"]))
        rows = [
            [Paragraph(label, st["cell_l"]), Paragraph(value or "—", st["cell_r"])]
            for label, value in items
        ]
        story.append(accounting_table(rows, CW))
        story.append(Spacer(1, 0.5 * cm))

    doc.build(story)


def render_summary_pdf(data: dict, path: str, legacy: bool = False) -> None:
    # Summary is Modern only
    return _render_modern_summary(data, path)
