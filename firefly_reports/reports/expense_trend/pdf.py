"""PDF renderers of the expense_trend report."""

from decimal import Decimal
from typing import Any

from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from firefly_reports import i18n
from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.palette import (
    DARK,
    MID,
    RULE,
    TOTAL_BG,
)
from firefly_reports.render.pdf.styles import classic_styles

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_expense_trend(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    owner = data["owner"]
    months = data["months"]

    # Landscape: the category × month matrix is too wide for portrait
    fn = page_decorator(owner, t("titles.expense_trend"), period, landscape_mode=True)
    doc = make_doc(output_path, fn, landscape_mode=True)

    story = []
    story += title_block(
        t("titles.expense_trend"),
        owner,
        period,
        t("pdf.subtitle_expense_trend"),
        st,
    )

    months_abbr = i18n.current().section("months_abbr")

    def _mk_label(mk: str) -> str:
        y, m = mk.split("-")
        return f"{months_abbr.get(m, m)}\n{y[-2:]}"

    n_months = len(months)
    # Landscape: 29.7 cm width. Margins 1.8cm each side (default in make_doc)
    cat_w = 6.0 * cm
    tot_w = 2.8 * cm
    avail = (landscape(A4)[0]) - 1.8 * cm - 1.8 * cm - cat_w - tot_w
    mon_w = min(2.4 * cm, avail / max(n_months, 1))
    CW_t = [cat_w] + [mon_w] * n_months + [tot_w]

    # Header row
    hdr_cells = [Paragraph(t("common.category"), st["col_header_l"])]
    for mk in months:
        hdr_cells.append(
            Paragraph(
                _mk_label(mk),
                ParagraphStyle(
                    "mh",
                    fontName="Helvetica-Bold",
                    fontSize=7.5,
                    textColor=DARK,
                    alignment=TA_CENTER,
                    leading=9,
                ),
            )
        )
    hdr_cells.append(Paragraph(t("common.total"), st["col_header"]))

    rows = [hdr_cells]
    for r in data["rows"]:
        row_cells = [
            Paragraph(
                r["category"][:30],
                ParagraphStyle(
                    "cl", fontName="Helvetica", fontSize=8, textColor=DARK, alignment=TA_LEFT
                ),
            )
        ]
        for val in r["monthly"]:
            row_cells.append(
                Paragraph(
                    fmt_num(val) if val > 0 else "—",
                    ParagraphStyle(
                        "nr", fontName="Helvetica", fontSize=8, textColor=DARK, alignment=TA_RIGHT
                    ),
                )
            )
        row_cells.append(
            Paragraph(
                fmt_num(r["total"]),
                ParagraphStyle(
                    "tr", fontName="Helvetica-Bold", fontSize=8, textColor=DARK, alignment=TA_RIGHT
                ),
            )
        )
        rows.append(row_cells)

    # Monthly expense total row
    tot_cells = [Paragraph(t("common.total_expense"), st["total_l"])]
    for val in data["totals_by_month"]:
        tot_cells.append(
            Paragraph(
                fmt_num(val),
                ParagraphStyle(
                    "tb", fontName="Helvetica-Bold", fontSize=8, textColor=DARK, alignment=TA_RIGHT
                ),
            )
        )
    tot_cells.append(Paragraph(fmt_num(data["grand_total"]), st["total_r"]))
    rows.append(tot_cells)

    # Monthly income row (reference comparison)
    inc_cells = [Paragraph(t("pdf.income_for_comparison"), st["cell_l"])]
    for val in data["income_by_month"]:
        inc_cells.append(
            Paragraph(
                fmt_num(val) if val > 0 else "—",
                ParagraphStyle(
                    "ib", fontName="Helvetica", fontSize=8, textColor=MID, alignment=TA_RIGHT
                ),
            )
        )
    inc_cells.append(
        Paragraph(
            fmt_num(sum(data["income_by_month"], Decimal(0))),
            ParagraphStyle(
                "ib2", fontName="Helvetica", fontSize=8, textColor=MID, alignment=TA_RIGHT
            ),
        )
    )
    rows.append(inc_cells)

    total_idx = len(rows) - 2
    tbl = Table(rows, colWidths=CW_t, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
                ("LINEABOVE", (0, total_idx), (-1, total_idx), 1.0, DARK),
                ("BACKGROUND", (0, total_idx), (-1, total_idx), TOTAL_BG),
                ("FONTNAME", (0, total_idx), (-1, total_idx), "Helvetica-Bold"),
                ("LINEABOVE", (0, total_idx + 1), (-1, total_idx + 1), 0.5, RULE),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
            ]
        )
    )
    story.append(tbl)

    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            t("pdf.expense_trend_note"),
            st["small"],
        )
    )

    doc.build(story)


def render_expense_trend_pdf(data: dict, path: str, legacy: bool = False) -> None:
    if legacy:
        return _render_legacy_expense_trend(data, path)
    return _render_legacy_expense_trend(data, path)  # TODO: Modern
