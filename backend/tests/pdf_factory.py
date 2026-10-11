"""PDF для тестов: создание (Montserrat, страницы, пароль) и извлечение текста."""
import io
from pathlib import Path

import pypdfium2 as pdfium
from reportlab.lib import pdfencrypt
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT = Path(__file__).resolve().parents[1] / "app" / "assets" / "fonts" / "Montserrat-Regular.ttf"


def make_pdf(text: str, pages: int = 1, password: str | None = None) -> bytes:
    if "Montserrat" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Montserrat", str(FONT)))
    buf = io.BytesIO()
    enc = pdfencrypt.StandardEncryption(password) if password else None
    c = canvas.Canvas(buf, pagesize=A4, encrypt=enc)
    for _ in range(pages):
        y = 800
        c.setFont("Montserrat", 9)
        for line in text.splitlines():
            c.drawString(40, y, line)
            y -= 12
        c.showPage()
    c.save()
    return buf.getvalue()


def pdf_text(data: bytes) -> str:
    assert data.startswith(b"%PDF")
    pdf = pdfium.PdfDocument(data)
    return "\n".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))
