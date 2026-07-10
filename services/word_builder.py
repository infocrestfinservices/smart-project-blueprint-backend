"""
word_builder.py

Turns the structured model JSON into a professional, purpose-specific .docx
(python-docx). Structure (sections, terminology) is driven by purpose_config;
narrative prose comes from the AI. Detailed financial tables intentionally live
in the Excel workbook, not here. Returns the document as bytes.
"""

import io
from datetime import datetime

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from purpose_config import get_config

NAVY = RGBColor(0x10, 0x25, 0x4A)
GOLD = RGBColor(0xB0, 0x8D, 0x3F)
GREY = RGBColor(0x55, 0x5B, 0x66)


def _fmt_date(d):
    try:
        dt = datetime.fromisoformat(str(d).replace("Z", "")) if d else datetime.utcnow()
    except (ValueError, TypeError):
        dt = datetime.utcnow()
    return dt.strftime("%B %d, %Y")


def _set_base_font(doc):
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)


def _heading(doc, text):
    p = doc.add_paragraph()
    p.space_before = Pt(14)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(15)
    run.font.color.rgb = NAVY
    # gold underline rule
    rule = doc.add_paragraph()
    rr = rule.add_run("―" * 24)
    rr.font.color.rgb = GOLD
    rr.font.size = Pt(8)
    rule.paragraph_format.space_after = Pt(4)
    return p


def _render_markdownish(doc, text):
    """Render simple narrative text: bullets for '-'/'*' lines, else paragraphs."""
    for raw in str(text or "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ", "• ")):
            doc.add_paragraph(line[2:].strip(), style="List Bullet")
        else:
            p = doc.add_paragraph(line)
            p.paragraph_format.space_after = Pt(6)


def _cover(doc, config, project):
    for _ in range(3):
        doc.add_paragraph()
    eyebrow = doc.add_paragraph()
    eyebrow.alignment = WD_ALIGN_PARAGRAPH.CENTER
    er = eyebrow.add_run(config["label"].upper())
    er.font.size = Pt(12)
    er.font.color.rgb = GOLD
    er.bold = True

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = title.add_run(project.get("title") or "Project Report")
    tr.bold = True
    tr.font.size = Pt(30)
    tr.font.color.rgb = NAVY

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = sub.add_run("Prepared in accordance with professional Chartered Accountancy standards")
    sr.italic = True
    sr.font.size = Pt(11)
    sr.font.color.rgb = GREY

    for _ in range(2):
        doc.add_paragraph()

    for label, value in [
        ("Industry", project.get("industry")),
        ("Promoter / Company", project.get("promoter_name")),
        ("Location", project.get("location") or project.get("country")),
        ("Date", _fmt_date(project.get("created_date") or project.get("created_at"))),
    ]:
        if not value:
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        lr = p.add_run(f"{label}:  ")
        lr.bold = True
        lr.font.color.rgb = NAVY
        p.add_run(str(value))

    doc.add_page_break()


def build_word(model: dict, purpose_key: str, project: dict) -> bytes:
    config = get_config(purpose_key)
    doc = Document()
    _set_base_font(doc)

    _cover(doc, config, project)

    # KPI snapshot
    kpis = model.get("kpis") or []
    if kpis:
        _heading(doc, "Key Indicators")
        table = doc.add_table(rows=0, cols=2)
        table.style = "Light List Accent 1"
        for kpi in kpis[:16]:
            cells = table.add_row().cells
            cells[0].text = str(kpi.get("label", ""))
            cells[1].text = str(kpi.get("value", ""))
        doc.add_paragraph()

    narrative = model.get("narrative") or {}
    for section in config["word_sections"]:
        title = section["title"]
        _heading(doc, title)
        content = narrative.get(title)
        if content:
            _render_markdownish(doc, content)
        else:
            p = doc.add_paragraph("Refer to the accompanying Excel financial model for detailed figures.")
            p.runs[0].italic = True

    # Pointer to the workbook
    doc.add_paragraph()
    note = doc.add_paragraph()
    nr = note.add_run("Note: Detailed financial statements, projections, ratios and the dashboard are provided in the accompanying Excel workbook.")
    nr.italic = True
    nr.font.size = Pt(9)
    nr.font.color.rgb = GREY

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
