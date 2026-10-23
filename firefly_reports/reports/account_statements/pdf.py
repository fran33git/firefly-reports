"""PDF renderers of the account_statements report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from firefly_reports.i18n import t
from firefly_reports.render.fmt import flatten_rows, fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.palette import (
    DARK,
    RULE,
    TOTAL_BG,
)
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_account_statements(statements: list[dict[str, Any]], output_path: str) -> None:
    if not statements:
        return

    st = classic_styles()
    # Use the first statement for the period (all share the same period)
    period = period_str(statements[0]["period_start"], statements[0]["period_end"])
    owner = statements[0]["owner"]

    # Landscape: 6 columns with comfortable spacing (29.7 × 21.0 cm)
    fn = page_decorator(owner, t("titles.account_statement"), period, landscape_mode=True)
    doc = make_doc(output_path, fn, landscape_mode=True)
    story = []

    for idx, stmt in enumerate(statements):
        if idx > 0:
            story.append(PageBreak())

        sym = stmt["currency"]

        story += title_block(
            t("titles.account_statement"),
            owner,
            period,
            f"{stmt['account_role']} — {stmt['account_name']}",
            st,
        )

        # Account metadata
        meta_rows = [
            [
                Paragraph(t("pdf.iban_reference"), st["col_header_l"]),
                Paragraph(stmt["account_iban"], st["cell_l"]),
            ],
            [
                Paragraph(t("common.currency_col"), st["col_header_l"]),
                Paragraph(stmt["currency_code"], st["cell_l"]),
            ],
            [
                Paragraph(t("pdf.opening_balance_period"), st["col_header_l"]),
                Paragraph(
                    fmt_num(stmt["opening_balance"], show_sym=True, sym=sym, parens_neg=True),
                    st["cell_r"],
                ),
            ],
        ]
        meta_tbl = Table(meta_rows, colWidths=[5 * cm, 16 * cm])
        meta_tbl.setStyle(
            TableStyle(
                [
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, -1), (-1, -1), 0.5, RULE),
                ]
            )
        )
        story.append(meta_tbl)
        story.append(Spacer(1, 0.4 * cm))

        # Landscape columns: 26.7 cm available (29.7 − 2×1.5)
        # date | description | type | counterpart | amount | balance
        CW_m = [2.4 * cm, 10.0 * cm, 2.2 * cm, 5.5 * cm, 3.5 * cm, 3.1 * cm]
        hdr = [
            [
                Paragraph(t("common.date"), st["col_header_l"]),
                Paragraph(t("common.description"), st["col_header_l"]),
                Paragraph(t("common.type"), st["col_header"]),
                Paragraph(t("common.counterpart"), st["col_header_l"]),
                Paragraph(t("common.amount"), st["col_header"]),
                Paragraph(t("common.balance"), st["col_header"]),
            ]
        ]
        rows = list(hdr)

        # Flatten grouped data for legacy rendering
        flat_stmt_rows = flatten_rows(stmt["rows"])

        for r in flat_stmt_rows:
            amt = r["amount"]
            desc = r["description"]
            if len(desc) > 80:
                desc = desc[:77] + "…"
            cpart = r["counterpart"] or "—"
            if len(cpart) > 40:
                cpart = cpart[:37] + "…"
            rows.append(
                [
                    Paragraph(r["date"], st["cell_l"]),
                    Paragraph(desc, st["cell_l"]),
                    Paragraph(r["type"][:3].upper(), st["cell_r"]),
                    Paragraph(cpart, st["cell_l"]),
                    Paragraph(fmt_num(amt, parens_neg=True), st["cell_r"]),
                    Paragraph(fmt_num(r["running_balance"], parens_neg=True), st["cell_r"]),
                ]
            )

        rows.append(
            [
                Paragraph("", st["cell_l"]),
                Paragraph(t("pdf.closing_balance_period"), st["total_l"]),
                Paragraph("", st["cell_r"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_r"]),
                Paragraph(
                    fmt_num(stmt["closing_balance"], show_sym=True, sym=sym, parens_neg=True),
                    st["total_r"],
                ),
            ]
        )
        grand_idx = len(rows) - 1

        tbl = Table(rows, colWidths=CW_m, repeatRows=1)
        tbl.setStyle(
            TableStyle(
                [
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
                    ("FONTSIZE", (0, 1), (-1, -2), 8),
                    ("LINEABOVE", (0, grand_idx), (-1, grand_idx), 1.0, DARK),
                    ("LINEBELOW", (0, grand_idx), (-1, grand_idx), 0.5, DARK),
                    ("BACKGROUND", (0, grand_idx), (-1, grand_idx), TOTAL_BG),
                    ("FONTNAME", (0, grand_idx), (-1, grand_idx), "Helvetica-Bold"),
                ]
            )
        )
        story.append(tbl)

        # Summary table
        story.append(Spacer(1, 0.5 * cm))
        CW_s = [15 * cm, 3.5 * cm, 3.5 * cm, 4.2 * cm]
        recap = [
            [
                Paragraph(t("common.opening_balance"), st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(
                    fmt_num(stmt["opening_balance"], show_sym=True, sym=sym, parens_neg=True),
                    st["cell_r"],
                ),
            ],
            [
                Paragraph(t("pdf.stmt_income_period"), st["cell_l_ind"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(fmt_num(stmt["total_in"], show_sym=True, sym=sym), st["cell_r"]),
            ],
            [
                Paragraph(t("pdf.stmt_expense_period"), st["cell_l_ind"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(
                    f"({fmt_num(abs(stmt['total_out']), show_sym=True, sym=sym)})", st["cell_r"]
                ),
            ],
            [
                Paragraph(t("common.closing_balance_stmt"), st["grand_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(
                    fmt_num(stmt["closing_balance"], show_sym=True, sym=sym, parens_neg=True),
                    st["grand_r"],
                ),
            ],
        ]
        recap_tbl = accounting_table(recap, CW_s, total_rows=[2], grand_rows=[3])
        story.append(recap_tbl)

    doc.build(story)


def render_account_statements_pdf(data: list, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_account_statements(data, path)
    return _render_legacy_account_statements(data, path)  # TODO: Modern
