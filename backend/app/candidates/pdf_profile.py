"""Стандартизированный PDF-профиль (процесс 2.2): версия для кандидата и псевдонимная версия для работодателя."""
import io
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy.orm import Session

from app.auth.models import User
from app.candidates.service import get_or_create_profile, passed_skills, stack_states
from app.common.clock import MSK, now
from app.matching.explain import NO_FSP
from app.matching.stack_dict import SKILL_TITLES

FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
PLUM, PINK, INK = HexColor("#310F53"), HexColor("#FF0053"), HexColor("#1C1D22")
FORMAT_TITLES = {"office": "офис", "hybrid": "гибрид", "remote": "удалёнка"}
SPEC_TITLES = {"backend": "Backend", "frontend": "Frontend", "data": "Data / Analytics"}


@dataclass(frozen=True)
class ProfileView:
    title: str
    subtitle: str
    sections: list[tuple[str, list[str]]]
    footer: str


def _register_fonts() -> None:
    registered = pdfmetrics.getRegisteredFontNames()
    for name, file in (("Montserrat", "Montserrat-Regular.ttf"), ("Montserrat-Bold", "Montserrat-Bold.ttf")):
        if name not in registered:  # каждое начертание отдельно: обычное мог уже зарегистрировать другой код
            pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))


def _clean(s: str) -> str:
    # В Montserrat нет глифа ✓: в PDF подтверждение пишется словом
    return escape(s.replace(" ✓", " (подтверждено)").replace("✓", "подтверждено"))


def render(view: ProfileView) -> bytes:
    _register_fonts()
    h1 = ParagraphStyle("h1", fontName="Montserrat-Bold", fontSize=18, leading=22, textColor=PLUM)
    sub = ParagraphStyle("sub", fontName="Montserrat", fontSize=10.5, leading=14, textColor=PINK, spaceAfter=8)
    h2 = ParagraphStyle("h2", fontName="Montserrat-Bold", fontSize=11.5, leading=15, textColor=PLUM, spaceBefore=8)
    body = ParagraphStyle("body", fontName="Montserrat", fontSize=9.5, leading=13, textColor=INK, leftIndent=6)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title=view.title, author="Платформа обратного найма ФСП")
    story = [Paragraph(_clean(view.title), h1), Paragraph(_clean(view.subtitle), sub), Spacer(1, 2 * mm)]
    for head, lines in view.sections:
        if lines:
            story.append(Paragraph(_clean(head), h2))
            story += [Paragraph("• " + _clean(line), body) for line in lines]

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Montserrat", 7.5)
        canvas.setFillColor(INK)
        canvas.drawString(18 * mm, 10 * mm, view.footer)
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def _stack_lines(stack: list[dict]) -> list[str]:
    conf = [s["tech"] for s in stack if s["state"] == "confirmed"]
    decl = [s["tech"] for s in stack if s["state"] == "declared"]
    return [line for line in (("Подтверждено: " + ", ".join(conf)) if conf else "",
                              ("Заявлено: " + ", ".join(decl)) if decl else "") if line]


def employer_view(card: dict, need_title: str, generated: str) -> ProfileView:
    """Только поля карточки работодателя: она уже без ПДн и с учётом пресета видимости."""
    status = "подтверждён тестом" if card["grade_status"] == "confirmed" else "заявлен, тестом не подтверждён"
    conditions = [x for x in (
        ("Формат: " + ", ".join(FORMAT_TITLES[f] for f in card["formats"])) if card["formats"] else "",
        f"Город: {card['city']}" if card.get("city") else "",
        f"Опыт: {card['experience_years']} г." if card.get("experience_years") is not None else "") if x]
    return ProfileView(
        title=card["alias"], subtitle=f"{card['grade'].capitalize()} · {status}",
        sections=[(f"Почему в подборке «{need_title}»", list(card["explanation"]["lines"])),
                  ("Чего не хватает", list(card["explanation"]["missing"])),
                  ("Стек", _stack_lines(card["stack"])),
                  ("Подтверждённые навыки", [SKILL_TITLES.get(s, s) for s in card.get("skills") or []]),
                  ("Условия", conditions)],
        footer=f"Псевдонимный профиль · ФИО и контакты передаются только с согласия кандидата · {generated}")


def candidate_view(db: Session, user: User) -> ProfileView:
    """Личная версия: с ФИО, контактами и порогом зарплаты (порог виден только самому кандидату)."""
    p = get_or_create_profile(db, user)
    grade = p.confirmed_grade or p.claimed_grade
    status = {"confirmed": "подтверждён тестом", "not_confirmed": "заявлен, тестом не подтверждён"}.get(
        p.grade_status, "тест ещё не пройден")
    threshold = ""
    if p.salary_threshold:
        kind = "на руки" if p.salary_gross_net == "net" else "до вычета НДФЛ"
        threshold = f"Минимальная зарплата: {p.salary_threshold:,} ₽ {kind}. Работодатели её не видят".replace(",", " ")
    conditions = [x for x in (
        ("Формат: " + ", ".join(FORMAT_TITLES[f] for f in p.formats)) if p.formats else "",
        f"Город: {p.city}" if p.city else "",
        f"Опыт: {p.experience_years} г." if p.experience_years is not None else "",
        threshold,
        f"Открыт к предложениям до {p.open_until.astimezone(MSK):%d.%m.%Y}" if p.open_until and p.open_until > now() else "")
        if x]
    stack = [{"tech": t, "state": st} for t, st in sorted(stack_states(db, p).items())]
    return ProfileView(
        title=p.full_name or "Профиль кандидата",
        subtitle=f"{SPEC_TITLES.get(p.specialization or '', 'Специализация не выбрана')} · "
                 f"{grade.capitalize() if grade else '—'} · {status}",
        sections=[("Контакты", [f"{k}: {v}" for k, v in (p.contacts or {}).items() if v]),
                  ("Стек", _stack_lines(stack)),
                  ("Подтверждённые навыки", [SKILL_TITLES.get(s, s) for s in sorted(passed_skills(db, p.user_id))]),
                  ("Достижения ФСП", [p.fsp_summary or NO_FSP]),
                  ("Условия", conditions)],
        footer=f"Личная версия профиля · сформирована {now().astimezone(MSK):%d.%m.%Y}")
