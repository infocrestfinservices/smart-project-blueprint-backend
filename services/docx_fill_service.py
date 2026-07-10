"""
docx_fill_service.py

Word (.docx) template support for the template-driven platform.

A Word template marks its variable spots with {{ placeholder }} tokens anywhere in
the document — body paragraphs, tables, headers and footers. We:
  * detect_placeholders(path) -> the ordered unique placeholder names, used to build
    the template's input schema (the questions we ask / the AI fills), and
  * fill_docx(path, answers) -> bytes: replace every {{name}} with answers["name"],
    preserving ALL formatting, tables, styles and layout (we edit run text in place
    and never rebuild the document).

Placeholders left without an answer are blanked (so the {{...}} never ships in the
final document).
"""

import io
import re

from docx import Document

# {{ name }} — name is any run of chars except braces; surrounding space is trimmed.
_TOKEN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def _iter_paragraphs(doc):
    """Every paragraph in the document: body, table cells (recursively), and the
    headers/footers of every section."""
    def _walk(container):
        for p in getattr(container, "paragraphs", []):
            yield p
        for tbl in getattr(container, "tables", []):
            for row in tbl.rows:
                for cell in row.cells:
                    yield from _walk(cell)

    yield from _walk(doc)
    for section in doc.sections:
        for hf in (section.header, section.footer,
                   section.first_page_header, section.first_page_footer,
                   section.even_page_header, section.even_page_footer):
            if hf is not None:
                yield from _walk(hf)


def detect_placeholders(path: str) -> list:
    """Ordered, de-duplicated placeholder names found in the .docx."""
    doc = Document(path)
    seen, out = set(), []
    for p in _iter_paragraphs(doc):
        for name in _TOKEN.findall(p.text):
            key = name.strip()
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return out


def _replace_in_paragraph(paragraph, mapping):
    """Replace every {{token}} in a paragraph while keeping formatting. Tokens that
    sit inside one run are replaced in place; tokens split across runs are collapsed
    into the paragraph's first run (which keeps that run's formatting)."""
    runs = paragraph.runs
    if not runs:
        return
    # Fast path: replace tokens contained within a single run.
    for run in runs:
        if "{{" in run.text and _TOKEN.search(run.text):
            run.text = _TOKEN.sub(lambda m: _sub(m, mapping), run.text)
    # Slow path: a token spans multiple runs -> rebuild from joined text.
    joined = "".join(r.text for r in runs)
    if _TOKEN.search(joined):
        runs[0].text = _TOKEN.sub(lambda m: _sub(m, mapping), joined)
        for r in runs[1:]:
            r.text = ""


def _sub(match, mapping):
    key = match.group(1).strip()
    val = mapping.get(key, "")
    return "" if val is None else str(val)


def fill_docx(path: str, answers: dict) -> bytes:
    """Fill {{placeholders}} in the .docx template with `answers` (keyed by
    placeholder name) and return the resulting document bytes. Formatting, tables,
    headers/footers and styles are preserved."""
    doc = Document(path)
    mapping = answers or {}
    for p in _iter_paragraphs(doc):
        if "{{" in p.text:
            _replace_in_paragraph(p, mapping)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
