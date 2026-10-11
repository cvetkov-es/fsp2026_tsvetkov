from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Stage = Literal["first", "technical", "offer", "hired", "rejected"]
Level = Literal["below", "meets", "above", "unknown"]


class StageIn(BaseModel):
    stage: Stage
    level: Level | None = None  # на этапе «техническое» и в финале — обязательно (можно «пока не могу сказать»)
    reason: str | None = Field(default=None, max_length=30)  # причина отказа
    weak_areas: list[str] = Field(default_factory=list, max_length=5)


class VoteOut(BaseModel):
    value: str
    state: str
    effective_at: datetime


class BoardCardOut(BaseModel):
    contact_id: str
    alias: str
    grade: str | None
    revoked: bool  # кандидат скрыл контакты — карточка только для чтения
    stage: str | None
    stage_at: datetime | None
    level: str | None
    reason: str | None
    weak_areas: list[str]
    vote: VoteOut | None
    vote_note: str | None
    chat_open: bool
    area_options: list[dict]


class HelperQuestionOut(BaseModel):
    text: str
    topic: str
    reason: str


class HelperOut(BaseModel):
    questions: list[HelperQuestionOut]
    used: int  # наборов у компании за окно лимита
    limit: int
    window_days: int  # окно лимита — HELPER_WINDOW


class BoardOut(BaseModel):
    need_id: str
    title: str
    trust_level: str
    vote_weight: float | None
    votes_used: int
    votes_limit: int
    dispute_days: int
    cards: list[BoardCardOut]


class DisputeIn(BaseModel):
    reason: Literal["no_interview", "wrong_stage", "wrong_company"]
    comment: str = Field(default="", max_length=500)
    answered_at: datetime | None = None  # какую версию оценки оспаривают: изменилась — 409


class ReviewOut(BaseModel):
    id: str
    company: str
    value: str
    grade: str
    specialization: str
    at: datetime
    state: str
    effective_at: datetime
    can_dispute: bool
