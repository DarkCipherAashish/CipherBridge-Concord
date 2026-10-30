"""One-click PDF decision report (requires the optional `reportlab` package)."""
import re
from io import BytesIO
from typing import Dict, List

_STATUS = {
    "agreed": "Consensus reached (structural checks passed)",
    "partial": "Partial agreement - human review needed",
    "incomplete": "Incomplete - no joint conclusion",
}
_PHASES = {
    "opening": "Opening position", "tradeoffs": "Trade-offs", "convergence": "Convergence",
    "closing": "Closing position", "conclusion": "Joint conclusion", "discussion": "Discussion",
    "stress": "Stress test", "stress_outcome": "Stress-test outcome",
}
_REPLACEMENTS = {"\u2194": "<->", "\u2192": "->", "\u2190": "<-", "\u2713": "ok", "\u2022": "-", "\u00a0": " "}


def pdf_available() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False


def _text(value) -> str:
    """Make text safe for the built-in PDF fonts (Latin-1 range) and for XML markup."""
    out = str(value or "")
    for old, new in _REPLACEMENTS.items():
        out = out.replace(old, new)
    out = out.encode("cp1252", "ignore").decode("cp1252")
    return out.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(value) -> str:
    out = _text(value)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", out)
    return re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', out)


def _markdown_flowables(text: str, styles) -> List:
    from reportlab.platypus import Paragraph, Spacer

    flow = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            flow.append(Spacer(1, 4))
        elif line.startswith("#"):
            flow.append(Paragraph("<b>%s</b>" % _inline(line.lstrip("# ")), styles["body"]))
        elif re.match(r"^[-*\u2022]\s+", line):
            flow.append(Paragraph(_inline(re.sub(r"^[-*\u2022]\s+", "", line)), styles["bullet"], bulletText="-"))
        elif re.match(r"^\d+[.)]\s+", line):
            flow.append(Paragraph(_inline(line), styles["bullet"]))
        else:
            flow.append(Paragraph(_inline(line), styles["body"]))
    return flow


def transcript_to_pdf(result: Dict) -> bytes:
    """Render the decision record as a PDF and return its bytes."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("PDF export needs the 'reportlab' package (pip install reportlab).") from exc

    teal, blue, grey = colors.HexColor("#0f766e"), colors.HexColor("#1d4ed8"), colors.HexColor("#475569")
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=19, textColor=teal, alignment=TA_LEFT, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, textColor=teal, spaceBefore=12, spaceAfter=5),
        "label": ParagraphStyle("l", parent=base["Normal"], fontSize=8, textColor=teal, fontName="Helvetica-Bold", spaceAfter=2),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=9.5, leading=13, spaceAfter=3),
        "bullet": ParagraphStyle("bu", parent=base["Normal"], fontSize=9.5, leading=13, leftIndent=14, spaceAfter=2),
        "small": ParagraphStyle("s", parent=base["Normal"], fontSize=8, leading=10, textColor=grey),
        "meta_k": ParagraphStyle("mk", parent=base["Normal"], fontSize=9, fontName="Helvetica-Bold", textColor=grey),
        "meta_v": ParagraphStyle("mv", parent=base["Normal"], fontSize=9.5, leading=12),
    }

    status = result.get("agreement_status", "incomplete")
    meta = result.get("metadata") or {}
    evaluation = result.get("evaluation") or {}
    agreement = evaluation.get("agreement") or {}
    consistency = evaluation.get("persona_consistency") or {}

    story = [
        Paragraph("CipherBridge Concord - Decision Report", styles["title"]),
        Paragraph("Dual-stakeholder cryptography decision dialogue", styles["small"]),
        Spacer(1, 8),
    ]

    rows = [
        ("Decision question", result.get("topic", "")),
        ("Stakeholders", "%s  <->  %s" % (result.get("persona_a", ""), result.get("persona_b", ""))),
        ("Outcome", _STATUS.get(status, status)),
    ]
    if agreement.get("checks"):
        rows.append(("Agreement score", "%s / 100 (%s)" % (agreement.get("score"), agreement.get("label"))))
    if consistency:
        rows.append(("Role consistency", "  |  ".join(
            "%s: %d%% (%s)" % (side, round(100 * v.get("coverage", 0)), v.get("label", "")) for side, v in consistency.items())))
    if result.get("context"):
        rows.append(("Context", result["context"]))
    rows.append(("Generated", "%s | model %s | %s turns" % (
        meta.get("generated_at", "n/a"), meta.get("model", "n/a"), meta.get("turns_generated", len(result.get("turns", []))))))
    table = Table([[Paragraph(_text(k), styles["meta_k"]), Paragraph(_inline(v), styles["meta_v"])] for k, v in rows],
                  colWidths=[38 * mm, 132 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [table]

    if status in ("agreed", "partial"):
        sections = result.get("conclusion") or {}
        story.append(Paragraph("Final conclusion", styles["h2"]))
        box = [Paragraph("JOINT DECISION", styles["label"])] + _markdown_flowables(
            sections.get("decision") or result.get("final_decision", ""), styles)
        box_table = Table([[box]], colWidths=[170 * mm])
        box_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ecfdf5" if status == "agreed" else "#fffbeb")),
            ("BOX", (0, 0), (-1, -1), 0.8, teal if status == "agreed" else colors.HexColor("#b45309")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story += [box_table, Spacer(1, 6)]
        for title, key in (("ACTION PLAN", "action_plan"), ("UNRESOLVED RISKS", "risks")):
            if sections.get(key):
                story += [Paragraph(title, styles["label"])] + _markdown_flowables(sections[key], styles) + [Spacer(1, 4)]
        if status == "partial":
            story.append(Paragraph("<b>Note:</b> full agreement was not confirmed. Treat the decision as a proposed next step.", styles["body"]))

    if agreement.get("checks"):
        story.append(Paragraph("Validation checks", styles["h2"]))
        for check in agreement["checks"]:
            story.append(Paragraph("[%s] %s" % ("pass" if check["passed"] else "review", _text(check["name"])), styles["bullet"]))
        story.append(Paragraph(_text(agreement.get("note", "")), styles["small"]))

    sources = result.get("sources") or []
    if sources:
        story.append(Paragraph("Knowledge-base sources", styles["h2"]))
        for src in sources:
            heading = " - %s" % src["heading"] if src.get("heading") else ""
            story.append(Paragraph("[%s] %s%s (%s)" % (_text(src["id"]), _text(src.get("title", "")), _text(heading), _text(src.get("source", ""))), styles["bullet"]))
        story.append(Paragraph("Retrieved by BM25 keyword ranking. A citation shows the model referred to a note; it does not verify the claim.", styles["small"]))

    story.append(Paragraph("Transcript", styles["h2"]))
    for turn in result.get("turns", []):
        side_colour = teal if turn.get("speaker") == result.get("persona_a") else blue
        head = ParagraphStyle("h", parent=styles["body"], textColor=side_colour, fontName="Helvetica-Bold", spaceBefore=6)
        label = _PHASES.get(turn.get("phase") or turn.get("type"), turn.get("type", ""))
        body = _markdown_flowables(turn.get("content", ""), styles)
        story.append(KeepTogether([Paragraph("Turn %s - %s  (%s)" % (turn.get("turn"), _text(turn.get("speaker")), _text(label)), head)] + body[:2]))
        story += body[2:]

    story += [Spacer(1, 10), Paragraph(
        "Academic prototype. AI-generated content can be inaccurate; the checks above are structural and keyword-based and do not "
        "certify technical correctness. Review all security-critical recommendations before implementation.", styles["small"])]

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(grey)
        canvas.drawString(20 * mm, 10 * mm, "CipherBridge Concord")
        canvas.drawRightString(190 * mm, 10 * mm, "Page %d" % doc.page)
        canvas.restoreState()

    buffer = BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                      title="CipherBridge Concord - Decision Report", author="CipherBridge Concord").build(
        story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
