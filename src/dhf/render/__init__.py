"""Local Word rendering with real revision markup and citation comments."""

import re
from difflib import SequenceMatcher
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from dhf.llm import canonical

AUTHOR = "DHF Assistant (AI draft)"
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def blocks(markdown: str) -> list[dict]:
    """Parse the generated Markdown subset into a JSON document tree."""
    output = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("<!--"):
            continue
        if line.startswith("|"):
            rows = []
            while True:
                cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)[1:-1]]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                if i >= len(lines) or not lines[i].strip().startswith("|"):
                    break
                line = lines[i].strip()
                i += 1
            output.append({"type": "table", "rows": rows})
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            output.append({"type": "heading", "level": level, "text": line[level:].strip()})
        else:
            output.append({"type": "paragraph", "text": line})
    return output


def paragraph_diff(previous: str, current: str) -> list[dict]:
    """Pure paragraph/table-block diff; replacement preserves deleted evidence."""
    before, after = blocks(previous), blocks(current)
    if not previous:
        return [{"change": "equal", "block": b} for b in after]
    diff = []
    matcher = SequenceMatcher(a=[canonical(b) for b in before], b=[canonical(b) for b in after])
    for op, a, b, c, d in matcher.get_opcodes():
        if op in ("delete", "replace"):
            diff.extend({"change": "delete", "block": item} for item in before[a:b])
        if op in ("insert", "replace", "equal"):
            diff.extend(
                {"change": "equal" if op == "equal" else "insert", "block": item}
                for item in after[c:d]
            )
    return diff


def render_docx(markdown: str, target: Path, baseline: str = "", timestamp: str = "") -> dict:
    doc = Document()
    doc.core_properties.author = AUTHOR
    doc.core_properties.title = next(
        (b["text"] for b in blocks(markdown) if b["type"] == "heading"), "DHF draft"
    )
    section = doc.sections[0]
    if any(b["type"] == "table" and len(b["rows"][0]) > 5 for b in blocks(markdown)):
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = Inches(11.7), Inches(8.3)
    section.top_margin = section.bottom_margin = Inches(0.65)
    section.left_margin = section.right_margin = Inches(0.7)
    for name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3"):
        style = doc.styles[name]
        style.font.name = "Arial"
        style.font.color.rgb = RGBColor(0, 0, 0)
        for border in list(style.element.iter(qn("w:pBdr"))):
            border.getparent().remove(border)
    doc.styles["Normal"].font.size = Pt(10)
    doc.styles["Normal"].paragraph_format.space_after = Pt(6)
    doc.styles["Title"].font.size = Pt(24)
    doc.settings.element.append(OxmlElement("w:trackRevisions"))
    counts = {"insertions": 0, "deletions": 0, "comments": 0}
    change_id = 0

    def revision(p, change: str) -> None:
        nonlocal change_id
        if change == "equal":
            return
        tag = "w:del" if change == "delete" else "w:ins"
        mark = OxmlElement(tag)
        mark.set(qn("w:id"), str(change_id))
        mark.set(qn("w:author"), AUTHOR)
        mark.set(qn("w:date"), timestamp)
        change_id += 1
        for child in list(p._p):
            if child.tag in (qn("w:r"), qn("w:hyperlink")):
                if change == "delete":
                    for text in child.iter(qn("w:t")):
                        text.tag = qn("w:delText")
                mark.append(child)
        p._p.append(mark)
        counts["deletions" if change == "delete" else "insertions"] += 1

    def content(p, text: str, change: str, small: bool = False) -> None:
        clean = text.replace("**", "").replace("<br>", "\n")
        # Hashes remain intact while allowing line-wrap in narrow evidence cells.
        clean = re.sub(
            r"\b[0-9a-f]{40,64}\b",
            lambda m: "\u200b".join(m[0][i : i + 12] for i in range(0, len(m[0]), 12)),
            clean,
        )
        anchor = p.add_run("" if change == "delete" else "\u200b")
        note = []
        inferred = "[Inferred]" in text
        suggested = "[Suggested" in text
        if inferred:
            note.append("AI-inferred from the cited evidence; review the stated basis.")
        if suggested:
            note.append("REVIEW REQUIRED: AI suggestion; no approval is implied.")

        def add_text(value: str) -> None:
            run = p.add_run(value)
            if small:
                run.font.size = Pt(8)
            if inferred or suggested:
                run.font.highlight_color = (
                    WD_COLOR_INDEX.YELLOW if inferred else WD_COLOR_INDEX.TURQUOISE
                )

        cursor = 0
        for match in LINK.finditer(clean):
            add_text(clean[cursor : match.start()])
            label, url = match.groups()
            note.append(f"Source: {label} — {url}")
            hyperlink = OxmlElement("w:hyperlink")
            hyperlink.set(
                qn("r:id"),
                doc.part.relate_to(
                    url,
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                    is_external=True,
                ),
            )
            hr = OxmlElement("w:r")
            props = OxmlElement("w:rPr")
            color = OxmlElement("w:color")
            color.set(qn("w:val"), "1B4F72")
            props.append(color)
            size = OxmlElement("w:sz")
            size.set(qn("w:val"), "16" if small else "20")
            props.append(size)
            hr.append(props)
            ht = OxmlElement("w:t")
            ht.text = label
            hr.append(ht)
            hyperlink.append(hr)
            p._p.append(hyperlink)
            cursor = match.end()
        add_text(clean[cursor:])
        if note and change != "delete":
            doc.add_comment(anchor, "\n".join(note), author=AUTHOR, initials="AI")
            counts["comments"] += 1
        revision(p, change)

    for item in paragraph_diff(baseline, markdown):
        block, change = item["block"], item["change"]
        if block["type"] == "table":
            table = doc.add_table(rows=0, cols=len(block["rows"][0]))
            table.autofit = False
            weights = [
                {
                    "Rev": 0.5,
                    "Revision": 0.5,
                    "Requirement": 1.0,
                    "Components": 0.85,
                    "Changes": 0.65,
                    "Test cases": 1.0,
                    "Software units": 1.9,
                    "Latest results": 2.0,
                    "Artifact": 1.0,
                    "Title": 3.0,
                }.get(label, 1.5)
                for label in block["rows"][0]
            ]
            available = section.page_width - section.left_margin - section.right_margin
            widths = [int(available * w / sum(weights)) for w in weights]
            for col, width in zip(table.columns, widths, strict=True):
                col.width = width
            for idx, values in enumerate(block["rows"]):
                cells = table.add_row().cells
                if idx == 0:
                    cells[0]._tc.getparent().get_or_add_trPr().append(OxmlElement("w:tblHeader"))
                for col_index, (cell, value) in enumerate(zip(cells, values, strict=True)):
                    cell.width = widths[col_index]
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    props = cell._tc.get_or_add_tcPr()
                    borders = OxmlElement("w:tcBorders")
                    for edge in ("top", "left", "bottom", "right"):
                        e = OxmlElement("w:" + edge)
                        for key, val in {"val": "single", "sz": "4", "color": "D9D9D9"}.items():
                            e.set(qn("w:" + key), val)
                        borders.append(e)
                    props.append(borders)
                    shading = OxmlElement("w:shd")
                    shading.set(
                        qn("w:fill"), "DEE8F0" if idx == 0 else ("F6F8FA" if idx % 2 else "FFFFFF")
                    )
                    props.append(shading)
                    cell.paragraphs[0].paragraph_format.space_after = Pt(3)
                    cell.paragraphs[0].paragraph_format.space_before = Pt(2)
                    content(cell.paragraphs[0], value, change, small=True)
                    if idx == 0:
                        for r in cell.paragraphs[0].runs:
                            r.bold = True
            doc.add_paragraph()
        else:
            if block["type"] == "heading":
                p = doc.add_paragraph(
                    style="Title"
                    if block["level"] == 1
                    else "Heading " + str(min(block["level"] - 1, 3))
                )
            else:
                p = doc.add_paragraph()
            content(p, block["text"], change)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(target)
    return counts
