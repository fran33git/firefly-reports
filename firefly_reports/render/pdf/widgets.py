"""Small PDF widgets: chart image and KPI strip."""

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    Paragraph,
    Table,
    TableStyle,
)

from firefly_reports.render.pdf.palette import (
    DARK,
    LIGHT,
    RULE,
    TOTAL_BG,
)


def chart_image(buf, width: float) -> Image:
    """Chart image at a fixed width, aspect ratio preserved."""
    pw, ph = ImageReader(buf).getSize()
    buf.seek(0)
    return Image(buf, width=width, height=width * ph / pw)


def kpi_strip(cards: list) -> Table:
    """Render a strip of boxed KPI cards.

    Each card is a ``(label, value, value_hex_color)`` tuple.
    """
    n = len(cards)
    gap = 0.4 * cm
    card_w = (17.4 * cm - gap * (n - 1)) / n
    lbl_st = ParagraphStyle(
        "kpi_lbl",
        fontName="Helvetica",
        fontSize=7,
        textColor=LIGHT,
        leading=9,
        alignment=TA_CENTER,
    )
    val_st = ParagraphStyle(
        "kpi_val",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=DARK,
        leading=16,
        alignment=TA_CENTER,
    )

    row: list = []
    widths: list = []
    for i, (label, value, vcolor) in enumerate(cards):
        card = Table(
            [
                [Paragraph(label.upper(), lbl_st)],
                [Paragraph(f"<font color='{vcolor}'>{value}</font>", val_st)],
            ],
            colWidths=[card_w],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), TOTAL_BG),
                    ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (0, 0), 5),
                    ("BOTTOMPADDING", (0, 1), (0, 1), 5),
                ]
            ),
        )
        row.append(card)
        widths.append(card_w)
        if i < n - 1:
            row.append("")
            widths.append(gap)
    return Table([row], colWidths=widths)
