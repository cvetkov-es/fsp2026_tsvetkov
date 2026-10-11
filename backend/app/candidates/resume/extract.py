"""Текст из PDF в отдельном процессе с таймаутом: защита от PDF-бомб и зависаний (исследование 06, §3).

Исходный файл нигде не сохраняется: байты живут только на время запроса.
"""
import json
import logging
import subprocess
import sys
from pathlib import Path

from app.common.errors import AppError
from app.common.subproc import child_limits, safe_env
from app.config.params import PARAMS

log = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[3]
ERRORS = {
    "encrypted": "PDF защищён паролем. Снимите защиту или заполните профиль вручную",
    "pages": f"В резюме больше {PARAMS.resume_max_pages} страниц",
    "broken": "Файл PDF повреждён",
}


def extract_text(data: bytes) -> tuple[str, int]:
    """Текст всех страниц и их число. Ошибки — problem+json с кодом resume_*."""
    if len(data) > PARAMS.resume_max_mb * 1024 * 1024:
        raise AppError(413, "resume_too_large", f"Файл больше {PARAMS.resume_max_mb} МБ")
    if not data.startswith(b"%PDF"):
        raise AppError(422, "resume_not_pdf", "Нужен файл PDF")
    try:
        r = subprocess.run([sys.executable, "-m", "app.candidates.resume.extract"], input=data, capture_output=True,
                           timeout=PARAMS.pdf_parse_timeout_s, cwd=BACKEND_DIR, env=safe_env(),
                           preexec_fn=child_limits(PARAMS.pdf_parse_mem_mb))
    except subprocess.TimeoutExpired as e:
        raise AppError(422, "resume_timeout", "PDF разбирался слишком долго. Заполните профиль вручную") from e
    if r.returncode != 0:
        # Упал или убит сам разборщик (память, нет pdfium) — это сбой сервера, а не «битый файл»
        log.warning("разбор PDF: код %s: %s", r.returncode, r.stderr[-300:].decode(errors="replace"))
        raise AppError(503, "resume_unavailable", "Не удалось обработать файл. Попробуйте позже или заполните профиль вручную")
    try:
        out = json.loads(r.stdout)
    except ValueError:
        out = {"error": "broken"}
    if err := out.get("error"):
        raise AppError(422, f"resume_{err}", ERRORS[err])
    return out["text"], out["pages"]


def _main() -> None:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(sys.stdin.buffer.read())
    except pdfium.PdfiumError as e:
        print(json.dumps({"error": "encrypted" if "password" in str(e).lower() else "broken"}))
        return
    if len(pdf) > PARAMS.resume_max_pages:
        print(json.dumps({"error": "pages"}))
        return
    pages = [pdf[i].get_textpage().get_text_range().replace("\r\n", "\n") for i in range(len(pdf))]
    print(json.dumps({"text": "\n".join(pages), "pages": len(pages)}, ensure_ascii=False))


if __name__ == "__main__":
    _main()
