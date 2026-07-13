import io

from docx import Document
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def build_docx(text: str) -> bytes:
    doc = Document()
    for line in text.splitlines() or [""]:
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def build_xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 72
    for line in text.splitlines() or [""]:
        pdf.drawString(72, y, line)
        y -= 14
        if y < 72:
            pdf.showPage()
            y = height - 72
    pdf.save()
    return buffer.getvalue()
