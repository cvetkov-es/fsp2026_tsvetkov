"""Конвейер резюме (процесс 2.2): PDF → текст → маскирование → LLM → черновик, который кандидат подтверждает.

Без LLM черновик строится правилами — это основной путь на стенде без ключа.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.candidates.resume.extract import extract_text
from app.candidates.resume.rules import draft_fields
from app.config.params import PARAMS
from app.llm.client import LLM, LLMOut
from app.llm.masking import contacts_from, mask
from app.llm.names import scan_names
from app.matching.stack_dict import normalize_many

Spec = Literal["backend", "frontend", "data"]
GradeCode = Literal["junior", "middle", "senior"]
Format = Literal["office", "hybrid", "remote"]
SCAN_WARNING = "Текста почти нет, похоже на скан. Заполните профиль вручную или загрузите PDF с текстовым слоем."
SYSTEM = (
    "Ты извлекаешь поля из резюме ИТ-специалиста для черновика профиля. Персональные данные заменены метками "
    "в квадратных скобках — не восстанавливай их. specialization: backend, frontend или data (аналитика, ML). "
    "recommended_grade: junior, middle или senior — по опыту и зоне ответственности. experience_years — общий "
    "стаж в ИТ. stack — языки, фреймворки, базы, инструменты так, как они названы в тексте. domains — отрасли "
    "(финтех, e-commerce, госсектор…). formats: office, hybrid, remote. Если данных нет — null или пустой список."
)


class ResumeLLM(LLMOut):
    specialization: Spec | None = None
    recommended_grade: GradeCode | None = None
    experience_years: float | None = Field(default=None, ge=0, le=60)
    stack: list[str] = Field(default_factory=list, max_length=60)
    domains: list[str] = Field(default_factory=list, max_length=10)
    formats: list[Format] = Field(default_factory=list)
    city: str | None = Field(default=None, max_length=80)

    @field_validator("stack", "domains")
    @classmethod
    def _short_items(cls, v: list[str], info) -> list[str]:
        # Длинный элемент — мусор модели: отбрасываем его, а не весь ответ (стек ≤ 60, сфера ≤ 40 символов, как в БД)
        limit = 60 if info.field_name == "stack" else 40
        return [x for x in v if x.strip() and len(x) <= limit]


class ResumeDraft(BaseModel):
    source: Literal["llm", "rules"]
    specialization: Spec | None = None
    recommended_grade: GradeCode | None = None
    experience_years: float | None = None
    stack: list[str] = Field(default_factory=list)
    unknown_terms: list[str] = Field(default_factory=list)
    formats: list[Format] = Field(default_factory=list)
    city: str | None = None
    domains: list[str] = Field(default_factory=list)
    full_name: str | None = None
    contacts: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def build_draft(data: bytes, llm: LLM) -> ResumeDraft:
    text, pages = extract_text(data)
    scan = scan_names(text)
    masked = mask(text, scan.names)
    draft = ResumeDraft(source="rules", full_name=scan.full_name,
                        contacts=contacts_from(masked.found), **draft_fields(text))
    if pages and len(text.strip()) / pages < PARAMS.resume_min_chars_per_page:
        draft.warnings.append(SCAN_WARNING)
        return draft
    if not scan.complete:  # NER не отработал: ФИО из тела резюме могли остаться — в LLM не отправляем
        return draft
    res = llm.json("pd", SYSTEM, masked.text[:PARAMS.llm_max_input_chars], ResumeLLM)
    if res is None:
        return draft
    out = res[0]
    known, unknown = normalize_many(out.stack)
    draft.source = "llm"
    draft.specialization = out.specialization or draft.specialization
    draft.recommended_grade = out.recommended_grade or draft.recommended_grade
    draft.experience_years = draft.experience_years if draft.experience_years is not None else out.experience_years
    draft.stack = list(dict.fromkeys([*draft.stack, *known]))
    draft.unknown_terms = unknown
    draft.formats = list(dict.fromkeys([*draft.formats, *out.formats]))
    draft.city = draft.city or out.city
    draft.domains = out.domains
    return draft
