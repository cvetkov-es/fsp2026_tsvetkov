from typing import Literal

from pydantic import BaseModel


class StackItemOut(BaseModel):
    tech: str
    state: Literal["confirmed", "declared"]


class ReadinessOut(BaseModel):
    level: str
    tooltip: str


class ExplanationOut(BaseModel):
    lines: list[str]
    missing: list[str]
    counterfactual: str | None


class CardOut(BaseModel):
    ref: str
    alias: str
    grade: str
    grade_status: str
    block: int | None
    fit_level: str | None
    readiness: ReadinessOut | None
    stack: list[StackItemOut]
    skills: list[str]
    experience_years: float | None
    formats: list[str]
    city: str | None
    conflicts: list[str]
    pinned: bool
    express: bool
    filter_mismatch: str | None
    interview_badge: str | None = None  # «Подтверждено на собеседованиях (N)» — только положительный бейдж
    signal: bool = False  # «Хочу к вам» этой компании
    minor: bool = False  # 14–17 лет: стажировка или каникулярная работа
    explanation: ExplanationOut
    contact_status: str | None = None  # статус приглашения по этой потребности (план 05)


class BlockOut(BaseModel):
    block: int
    title: str
    items: list[CardOut]


class RemovedOut(BaseModel):
    ref: str
    alias: str
    reason: str


class DiffOut(BaseModel):
    added: int
    removed: list[RemovedOut]


class SuggestionOut(BaseModel):
    filter: str
    label: str
    gain: int


class ForkFitOut(BaseModel):
    fit: int
    total: int


class SelectionOut(BaseModel):
    blocks: list[BlockOut]
    shortlist: list[CardOut]
    diff: DiffOut | None  # None — первое открытие подборки
    suggestions: list[SuggestionOut]
    fork_fit: ForkFitOut


class MapCellOut(BaseModel):
    specialization: str
    grade: str
    confirmed: int
    unconfirmed: int


class MapOut(BaseModel):
    cells: list[MapCellOut]


class CellOut(BaseModel):
    items: list[CardOut]


class SummaryOut(BaseModel):
    text: str
    source: Literal["llm", "template"]
