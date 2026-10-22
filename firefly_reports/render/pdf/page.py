"""Page decorator, document factory and title block of the PDF reports."""

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Spacer,
)

from firefly_reports import clock
from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_date
from firefly_reports.render.pdf.palette import (
    DARK,
    LIGHT,
    RULE,
)


def page_decorator(owner: str, report_title: str, period: str, landscape_mode=False):
    pagesize = landscape(A4) if landscape_mode else A4
    generated = fmt_date(clock.now())

    def draw(canvas, doc):
        canvas.saveState()
        w, h = pagesize

        # ── HEADER: text only + thin rule
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(DARK)
        canvas.drawString(1.8 * cm, h - 1.3 * cm, report_title.upper())

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(LIGHT)
        canvas.drawRightString(w - 1.8 * cm, h - 1.3 * cm, owner)

        # thin horizontal rule below header
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(1.8 * cm, h - 1.6 * cm, w - 1.8 * cm, h - 1.6 * cm)

        # ── FOOTER: rule + text
        canvas.setStrokeColor(RULE)
        canvas.line(1.8 * cm, 1.4 * cm, w - 1.8 * cm, 1.4 * cm)

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(LIGHT)
        canvas.drawString(
            1.8 * cm, 0.9 * cm, t("pdf.footer_period").format(period=period, generated=generated)
        )
        canvas.drawRightString(w - 1.8 * cm, 0.9 * cm, t("pdf.footer_page").format(page=doc.page))

        canvas.restoreState()

    return draw


def make_doc(output_path: str, page_fn, landscape_mode=False) -> BaseDocTemplate:
    pagesize = landscape(A4) if landscape_mode else A4
    doc = BaseDocTemplate(
        output_path,
        pagesize=pagesize,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=2.4 * cm,
        bottomMargin=2.2 * cm,
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="main",
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=page_fn)])
    return doc


def title_block(report_title: str, owner: str, period: str, subtitle: str | None, st: dict) -> list:
    """Return a list of flowables for the title block."""
    items = []
    items.append(Spacer(1, 0.3 * cm))
    items.append(Paragraph(report_title, st["title"]))
    items.append(Paragraph(owner, st["entity"]))
    items.append(Paragraph(t("pdf.period_ref").format(period=period), st["meta"]))
    items.append(Spacer(1, 0.15 * cm))
    items.append(HRFlowable(width="100%", thickness=1, color=DARK, spaceAfter=6, spaceBefore=2))
    if subtitle:
        items.append(Paragraph(subtitle.upper(), st["section"]))
    return items
