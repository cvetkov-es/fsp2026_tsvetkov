import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, field_validator

from app.config.params import PARAMS
from app.contacts.schemas import InviteIn


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    specialization: Literal["backend", "frontend", "data"]
    text: str = Field(min_length=10)
    reference_answer: str | None = Field(default=None, max_length=500)
    answer_kind: Literal["number", "text"] | None = None
    deadline: AwareDatetime  # без часового пояса — 422, а не сравнение naive с aware

    @field_validator("text")
    @classmethod
    def _text_max(cls, v: str) -> str:
        if len(v) > PARAMS.task_text_max:
            raise ValueError(f"не длиннее {PARAMS.task_text_max} символов")
        return v


class SubmissionIn(BaseModel):
    answer: str = Field(min_length=1)

    @field_validator("answer")
    @classmethod
    def _answer_max(cls, v: str) -> str:
        if len(v) > PARAMS.task_answer_max:
            raise ValueError(f"не длиннее {PARAMS.task_answer_max} символов")
        return v


class ComplaintIn(BaseModel):
    comment: str = Field(default="", max_length=1000)


class EvaluateIn(BaseModel):
    verdict: Literal["accepted", "rejected"]
    comment: str = Field(default="", max_length=1000)


class TaskInviteIn(InviteIn):
    need_id: uuid.UUID


class CreatedOut(BaseModel):
    id: str


class OkOut(BaseModel):
    ok: bool = True


class ContactCreatedOut(BaseModel):
    contact_id: str


class LimitsOut(BaseModel):
    text_max: int
    ttl_days: int


class CompanyBriefOut(BaseModel):
    name: str
    trust_level: str


class MySubmissionOut(BaseModel):
    status: str  # pending | auto_correct | auto_wrong | accepted | rejected
    comment: str | None


class FeedItemOut(BaseModel):
    id: str
    title: str
    text: str
    specialization: str
    deadline: datetime
    has_reference: bool  # сам эталон кандидату не отдаётся
    answer_max: int  # предел длины ответа — из PARAMS
    company: CompanyBriefOut
    my_submission: MySubmissionOut | None


class CompanyTaskOut(BaseModel):
    id: str
    title: str
    specialization: str
    deadline: datetime
    status: str  # open | closed | removed
    submissions: int
    pending: int


class SubmissionOut(BaseModel):
    id: str
    alias: str
    ref: str
    answer: str
    auto_correct: bool | None
    verdict: str | None
    comment: str | None
    llm_hint: dict | None
    created_at: datetime


class TaskDetailOut(BaseModel):
    id: str
    title: str
    text: str
    reference_answer: str | None  # работодателю эталон виден
    answer_kind: str | None
    deadline: datetime
    status: str


class TaskSubmissionsOut(BaseModel):
    task: TaskDetailOut
    items: list[SubmissionOut]
