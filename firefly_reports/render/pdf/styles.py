"""Paragraph style sets (classic and corporate) of the PDF reports."""

from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle

from firefly_reports.render.pdf.palette import (
    BLACK,
    DARK,
    LIGHT,
    MID,
)


def classic_styles() -> dict:
    st = {}

    # Report title (first line, large)
    st["title"] = ParagraphStyle(
        "title",
        fontName="Times-Bold",
        fontSize=14,
        textColor=DARK,
        leading=18,
        spaceBefore=0,
        spaceAfter=2,
        alignment=TA_LEFT,
    )

    # Subtitle / entity name
    st["entity"] = ParagraphStyle(
        "entity",
        fontName="Times-Roman",
        fontSize=10,
        textColor=DARK,
        leading=14,
        spaceAfter=1,
        alignment=TA_LEFT,
    )

    # Info row (period, generation date)
    st["meta"] = ParagraphStyle(
        "meta",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=LIGHT,
        leading=12,
        spaceAfter=0,
        alignment=TA_LEFT,
    )

    # Section heading (uppercase, bold)
    st["section"] = ParagraphStyle(
        "section",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=DARK,
        leading=12,
        spaceBefore=14,
        spaceAfter=4,
        alignment=TA_LEFT,
        textTransform="uppercase",
    )  # textTransform not supported in RL; apply manually

    # Normal entry (left cell label)
    st["cell_l"] = ParagraphStyle(
        "cell_l", fontName="Helvetica", fontSize=9, textColor=DARK, leading=12, alignment=TA_LEFT
    )

    st["cell_c"] = ParagraphStyle(
        "cell_c", fontName="Helvetica", fontSize=9, textColor=DARK, leading=12, alignment=TA_CENTER
    )

    # Indented entry
    st["cell_l_ind"] = ParagraphStyle(
        "cell_l_ind",
        fontName="Helvetica",
        fontSize=9,
        textColor=DARK,
        leading=12,
        alignment=TA_LEFT,
        leftIndent=12,
    )

    # Right-aligned number
    st["cell_r"] = ParagraphStyle(
        "cell_r", fontName="Helvetica", fontSize=9, textColor=DARK, leading=12, alignment=TA_RIGHT
    )

    # Subtotal bold
    st["total_l"] = ParagraphStyle(
        "total_l",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=DARK,
        leading=12,
        alignment=TA_LEFT,
    )

    st["total_r"] = ParagraphStyle(
        "total_r",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=DARK,
        leading=12,
        alignment=TA_RIGHT,
    )

    # Grand total (slightly larger)
    st["grand_l"] = ParagraphStyle(
        "grand_l",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=DARK,
        leading=13,
        alignment=TA_LEFT,
    )

    st["grand_r"] = ParagraphStyle(
        "grand_r",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=DARK,
        leading=13,
        alignment=TA_RIGHT,
    )

    st["small"] = ParagraphStyle(
        "small", fontName="Helvetica", fontSize=7.5, textColor=LIGHT, leading=10, alignment=TA_LEFT
    )

    st["col_header"] = ParagraphStyle(
        "col_header",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=DARK,
        leading=11,
        alignment=TA_RIGHT,
    )

    st["col_header_l"] = ParagraphStyle(
        "col_header_l",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=DARK,
        leading=11,
        alignment=TA_LEFT,
    )

    return st


def corporate_styles() -> dict:
    st = {}

    # Modern palette uses more greys
    st["title"] = ParagraphStyle(
        "title",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=BLACK,
        leading=22,
        spaceBefore=0,
        spaceAfter=4,
        alignment=TA_LEFT,
    )

    st["entity"] = ParagraphStyle(
        "entity",
        fontName="Helvetica",
        fontSize=11,
        textColor=MID,
        leading=15,
        spaceAfter=2,
        alignment=TA_LEFT,
    )

    st["meta"] = ParagraphStyle(
        "meta",
        fontName="Helvetica",
        fontSize=8,
        textColor=LIGHT,
        leading=11,
        spaceAfter=0,
        alignment=TA_LEFT,
    )

    st["section"] = ParagraphStyle(
        "section",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=BLACK,
        leading=13,
        spaceBefore=18,
        spaceAfter=6,
        alignment=TA_LEFT,
    )

    # Smaller, cleaner cell styles for corporate look
    st["cell_l"] = ParagraphStyle(
        "cell_l", fontName="Helvetica", fontSize=8.5, textColor=DARK, leading=11, alignment=TA_LEFT
    )

    st["cell_l_grey"] = ParagraphStyle(
        "cell_l_grey",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=MID,
        leading=11,
        alignment=TA_LEFT,
    )

    st["cell_c"] = ParagraphStyle(
        "cell_c",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=DARK,
        leading=11,
        alignment=TA_CENTER,
    )

    st["cell_l_ind"] = ParagraphStyle(
        "cell_l_ind",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=DARK,
        leading=11,
        alignment=TA_LEFT,
        leftIndent=12,
    )

    st["split_indent"] = ParagraphStyle(
        "split_indent",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=DARK,
        leading=11,
        alignment=TA_LEFT,
        leftIndent=24,
    )

    st["cell_r"] = ParagraphStyle(
        "cell_r", fontName="Helvetica", fontSize=8.5, textColor=DARK, leading=11, alignment=TA_RIGHT
    )

    st["cell_r_bold"] = ParagraphStyle(
        "cell_r_bold",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=BLACK,
        leading=11,
        alignment=TA_RIGHT,
    )

    st["total_l"] = ParagraphStyle(
        "total_l",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=BLACK,
        leading=11,
        alignment=TA_LEFT,
    )

    st["total_r"] = ParagraphStyle(
        "total_r",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=BLACK,
        leading=11,
        alignment=TA_RIGHT,
    )

    st["grand_l"] = ParagraphStyle(
        "grand_l",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=BLACK,
        leading=11,
        alignment=TA_LEFT,
    )

    st["grand_r"] = ParagraphStyle(
        "grand_r",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=BLACK,
        leading=11,
        alignment=TA_RIGHT,
    )

    st["small"] = ParagraphStyle(
        "small", fontName="Helvetica", fontSize=7, textColor=LIGHT, leading=11, alignment=TA_LEFT
    )

    st["col_header"] = ParagraphStyle(
        "col_header",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=MID,
        leading=11,
        alignment=TA_RIGHT,
    )

    st["col_header_l"] = ParagraphStyle(
        "col_header_l",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=MID,
        leading=11,
        alignment=TA_LEFT,
    )

    return st
