"""Потребность из текста вакансии (процесс 4.2): текст → LLM → структура → экран подтверждения.

Единственный синхронный вызов LLM в продукте (техдизайн, решение 6). Без LLM — правила; форма остаётся равноправной.
"""
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.config.params import PARAMS
from app.employers.schemas import Format, GradeCode
from app.llm.client import LLM, LLMOut
from app.llm.masking import mask
from app.matching.stack_dict import find_techs, normalize_many
from app.matching.text_rules import (
    city_in,
    formats_in,
    grades_in,
    gross_net_in,
    salary_in,
    specialization_in,
)

Spec = Literal["backend", "frontend", "data"]
_NICE = re.compile(r"(?im)^\s*(?:будет плюсом|плюсом будет|желательно|nice to have|будет преимуществом|"
                   r"преимуществом будет|приветствуется)\b.*$")
_SECTION = re.compile(r"(?im)^\s*(?:требования|обязанности|условия|мы предлагаем|что мы предлагаем|задачи|"
                      r"мы ожидаем|о компании|о нас)\b.*$")
SYSTEM = (
    "Ты разбираешь текст вакансии ИТ-компании в поля формы. specialization: backend, frontend или data "
    "(аналитика, ML). grades — все подходящие уровни из junior, middle, senior; «middle+» — middle и senior. "
    "must — обязательные технологии, nice — желательные («будет плюсом»). formats: office, hybrid, remote. "
    "salary_from и salary_to — числа в рублях за месяц; gross_net — gross, если сумма до вычета НДФЛ, "
    "net — если на руки. Если данных нет — null или пустой список. Ничего не придумывай."
)
REQUIRED = {"title": "название", "specialization": "специализация", "grades": "целевые грейды",
            "salary_from": "вилка от", "salary_to": "вилка до", "gross_net": "до вычета или на руки"}


class NeedLLM(LLMOut):
    title: str | None = Field(default=None, max_length=200)
    specialization: Spec | None = None
    grades: list[GradeCode] = Field(default_factory=list)
    must: list[str] = Field(default_factory=list, max_length=30)
    nice: list[str] = Field(default_factory=list, max_length=30)
    formats: list[Format] = Field(default_factory=list)
    city: str | None = Field(default=None, max_length=80)
    salary_from: int | None = Field(default=None, gt=0, le=10_000_000)
    salary_to: int | None = Field(default=None, gt=0, le=10_000_000)
    gross_net: Literal["gross", "net"] | None = None

    @field_validator("must", "nice")
    @classmethod
    def _short_items(cls, v: list[str]) -> list[str]:
        return [x for x in v if x.strip() and len(x) <= 60]  # длинный элемент — мусор модели, не технология


class NeedDraft(NeedLLM):
    source: Literal["llm", "rules"]
    unknown_terms: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)  # обязательные поля формы, которых нет в тексте


class NeedTextIn(BaseModel):
    text: str = Field(min_length=20, max_length=8000)


def _nice_zone(text: str) -> str:
    """Текст под заголовками «будет плюсом» до следующего раздела."""
    parts = []
    for m in _NICE.finditer(text):
        nxt = _SECTION.search(text, m.end())
        parts.append(text[m.start(): nxt.start() if nxt else len(text)])
    return "\n".join(parts)


def rules_draft(text: str) -> NeedDraft:
    techs = find_techs(text)
    nice = [t for t in find_techs(_nice_zone(text)) if t in techs]
    lo, hi = salary_in(text)
    title = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    title = re.sub(r"^(?:вакансия|позиция)\s*[:—-]\s*", "", title, flags=re.I)[:200] or None
    return NeedDraft(source="rules", title=title, specialization=specialization_in(text, techs),
                     grades=grades_in(text), must=[t for t in techs if t not in nice], nice=nice,
                     formats=formats_in(text), city=city_in(text), salary_from=lo, salary_to=hi,
                     gross_net=gross_net_in(text))


_CONTACT_LINE = re.compile(r"(?i)контакт|рекрут|hr\b|пишите|звоните|связь|обращаться")
_NAME = re.compile(r"\b[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2}\b")


def contact_names(text: str) -> list[str]:
    """Имена в строках с контактами («Контакты: Мария Иванова, hr@…») — маскируются перед LLM."""
    return [m.group(0) for ln in text.splitlines() if _CONTACT_LINE.search(ln) for m in _NAME.finditer(ln)]


def _plain_title(title: str | None) -> str | None:
    """Заголовок от модели — только если он похож на название, а не на свалку полей («…, специализация: …»)."""
    if not title or len(title) > 80 or ":" in title or "\n" in title:
        return None
    return title.strip()


def parse_need_text(text: str, llm: LLM) -> NeedDraft:
    draft = rules_draft(text)
    res = llm.json("runtime", SYSTEM, mask(text, contact_names(text)).text[:PARAMS.llm_max_input_chars], NeedLLM)
    if res is not None:
        out = res[0]
        must, unk1 = normalize_many(out.must)
        nice, unk2 = normalize_many(out.nice)
        draft = NeedDraft(
            source="llm", title=_plain_title(out.title) or draft.title, specialization=out.specialization or draft.specialization,
            grades=out.grades or draft.grades, must=must or draft.must,
            nice=[t for t in (nice or draft.nice) if t not in (must or draft.must)],
            formats=out.formats or draft.formats, city=out.city or draft.city,
            salary_from=out.salary_from or draft.salary_from, salary_to=out.salary_to or draft.salary_to,
            gross_net=out.gross_net or draft.gross_net, unknown_terms=list(dict.fromkeys(unk1 + unk2)))
    draft.missing = [label for field, label in REQUIRED.items() if not getattr(draft, field)]
    return draft
