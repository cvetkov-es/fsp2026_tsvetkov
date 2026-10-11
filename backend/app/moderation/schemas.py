from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ResolveIn(BaseModel):
    action: str = Field(max_length=20)  # допустимость проверяет реестр типа
    resolution_text: str = Field(default="", max_length=1000)


class SummaryRow(BaseModel):
    label: str
    value: str


class ActionOut(BaseModel):
    code: str
    title: str


class CaseOut(BaseModel):
    id: str
    type: str
    type_title: str
    status: str
    created_at: datetime
    due_at: datetime | None  # срок ответа, если он есть (ст. 16)
    comment: str
    resolution: str | None
    resolution_text: str | None
    summary: list[SummaryRow]
    actions: list[ActionOut]


class ReportIn(BaseModel):
    reason: Literal["wrong_key", "unclear", "typo", "other"]
    comment: str = Field(default="", max_length=1000)


class ObjectionIn(BaseModel):
    comment: str = Field(min_length=10, max_length=2000)


class ObjectionOut(BaseModel):
    case_id: str
    due_at: datetime  # срок ответа — ART16_DAYS


class MyCaseOut(BaseModel):
    id: str
    type: str
    type_title: str
    status: str
    created_at: datetime
    due_at: datetime | None
    outcome: str | None  # действие модератора
    resolution_text: str | None
