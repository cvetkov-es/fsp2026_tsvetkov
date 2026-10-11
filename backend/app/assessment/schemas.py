import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

GradeCode = Literal["junior", "middle", "senior"]


class StartIn(BaseModel):
    target_grade: GradeCode
    express: bool = False
    extra_time: bool = False
    accept_rules: bool = False
    pledge: bool = False


MAX_EVENTS = 200
MAX_RESPONSE_CHARS = 10_000


class AnswerIn(BaseModel):
    seq: int
    response: Any = None
    # Сигналы честности — не повод терять ответ: лишние события отбрасываются, а не дают 422
    events: list[dict] = Field(default_factory=list)

    @field_validator("events", mode="before")
    @classmethod
    def _cap_events(cls, v: Any) -> Any:
        return v[:MAX_EVENTS] if isinstance(v, list) else v

    @field_validator("response")
    @classmethod
    def _cap_response(cls, v: Any) -> Any:
        if len(json.dumps(v, ensure_ascii=False, default=str)) > MAX_RESPONSE_CHARS:
            raise ValueError("Ответ слишком длинный")
        return v


class ItemOut(BaseModel):
    seq: int
    phase: int
    kind: str
    prompt: dict
    time_limit_s: int
    remaining_s: int  # по часам сервера: клиент показывает его, а не считает от своих часов
    presented_at: datetime


class AiMetricsOut(BaseModel):
    passed: bool | None
    n: int
    answered: int
    correct: int
    accuracy: float
    miss_weighted: float
    false_reject: float
    minutes: int
    in_time: bool


class ResultOut(BaseModel):
    decision: str
    phrase: str
    reliability: float | None
    border: bool
    confident: bool
    express: bool
    ai: AiMetricsOut | None = None  # только «Работа с ИИ»


class AiProgressOut(BaseModel):
    total: int
    time_left_s: int | None  # общий таймер; None — вердикт ещё не показан или попытка закрыта
    minutes: int
    sql_max_rows: int
    pass_accuracy: float
    pass_miss: float
    cooldown_days: int  # пересдача после неудачи


class AttemptOut(BaseModel):
    id: str
    target_grade: str
    express: bool
    status: str
    stage: str
    n_answered: int
    phase2_total: int
    phase2_answered: int
    bank_exhausted: bool
    item: ItemOut | None
    result: ResultOut | None
    skill_code: str | None = None  # навык попытки; None — тест на грейд
    ai: AiProgressOut | None = None  # только «Работа с ИИ»


class SkillStartIn(BaseModel):
    accept_rules: bool = False
    pledge: bool = False
    extra_time: bool = False


class SkillOut(BaseModel):
    code: str
    title: str
    summary: str
    techs: list[str]
    status: Literal["passed", "failed", "not_taken"]
    available: bool
    available_at: datetime | None
    active_attempt_id: str | None
    recommended: bool
    bank_ready: bool
    format: Literal["test", "ai"]
    items: int
    minutes: int | None


class AvailabilityOut(BaseModel):
    allowed: bool
    available_at: datetime | None
    reasons: list[str]


class AttemptSummary(BaseModel):
    id: str
    target_grade: str
    express: bool
    status: str
    decision: str | None
    phrase: str | None
    started_at: datetime
    finished_at: datetime | None
