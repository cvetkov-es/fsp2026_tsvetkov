"""Черновик профиля из текста резюме без LLM: словарь стека, стаж по датам, подсказка грейда (исследование 06, §3)."""
import re
from datetime import date

from app.config.params import PARAMS
from app.matching.stack_dict import find_techs
from app.matching.text_rules import city_in, formats_in, grades_in, specialization_in

_MONTHS = (("январ", 1), ("феврал", 2), ("март", 3), ("апрел", 4), ("ма", 5), ("июн", 6), ("июл", 7), ("август", 8),
           ("сентябр", 9), ("октябр", 10), ("ноябр", 11), ("декабр", 12), ("jan", 1), ("feb", 2), ("mar", 3),
           ("apr", 4), ("may", 5), ("jun", 6), ("jul", 7), ("aug", 8), ("sep", 9), ("oct", 10), ("nov", 11),
           ("dec", 12))
_DATE = r"(?:[А-Яа-яЁёA-Za-z]{3,}\.?\s+(?:19|20)\d{2}|\d{1,2}\.(?:19|20)\d{2}|(?:19|20)\d{2})"
_NOW = r"(?:по\s+)?(?:настоящее время|наст\.\s*время|н\.\s?в\.|сейчас|present|now|текущее время)"
_INTERVAL = re.compile(rf"({_DATE})\s*(?:[—–-]{{1,2}}|по)\s*({_DATE}|{_NOW})", re.I)
_TOTAL = re.compile(r"опыт(?:\s+работы)?\s*[—–:-]?\s*(?:более\s+|от\s+|около\s+)?(\d{1,2})\s*(?:года|год|лет)"
                    r"(?:\s+(\d{1,2})\s*месяц)?", re.I)


def _month(word: str) -> int | None:
    w = word.lower()
    return next((m for prefix, m in _MONTHS if w.startswith(prefix)), None)


def _point(s: str, end: bool, today: date) -> int | None:
    """Дата как номер месяца (год·12 + месяц); у одного года — январь для начала и декабрь для конца."""
    s = s.strip()
    if re.fullmatch(_NOW, s, re.I):
        return today.year * 12 + today.month
    if m := re.fullmatch(r"(\d{1,2})\.(\d{4})", s):
        return int(m.group(2)) * 12 + int(m.group(1))
    if m := re.fullmatch(r"([А-Яа-яЁёA-Za-z]+)\.?\s+(\d{4})", s):
        month = _month(m.group(1))
        year = int(m.group(2))
        return year * 12 + (month or (12 if end else 1))
    if re.fullmatch(r"\d{4}", s):
        return int(s) * 12 + (12 if end else 1)
    return None


def experience_years(text: str, today: date | None = None) -> float | None:
    today = today or date.today()
    if m := _TOTAL.search(text):
        return round(min(60.0, int(m.group(1)) + int(m.group(2) or 0) / 12), 1)
    spans = []
    for a, b in _INTERVAL.findall(text):
        start, end = _point(a, False, today), _point(b, True, today)
        if start and end and start <= end:
            spans.append((start, end))
    if not spans:
        return None
    spans.sort()
    months, cur_s, cur_e = 0, *spans[0]
    for s, e in spans[1:]:
        if s <= cur_e + 1:
            cur_e = max(cur_e, e)
        else:
            months, cur_s, cur_e = months + cur_e - cur_s + 1, s, e
    months += cur_e - cur_s + 1
    return round(min(60.0, months / 12), 1)


def grade_hint(text: str, years: float | None) -> str | None:
    """Подсказка, а не решение: грейд кандидат выбирает сам и подтверждает тестом (процесс 2.3)."""
    words = grades_in(text)
    if words:
        return words[-1]
    if years is None:
        return None
    low, high = PARAMS.grade_hint_years
    return "junior" if years < low else "middle" if years < high else "senior"


def draft_fields(text: str) -> dict:
    techs = find_techs(text)
    years = experience_years(text)
    return {"specialization": specialization_in(text, techs), "recommended_grade": grade_hint(text, years),
            "experience_years": years, "stack": techs, "formats": formats_in(text), "city": city_in(text)}
