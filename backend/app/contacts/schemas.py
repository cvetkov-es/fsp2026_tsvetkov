from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

GrossNet = Literal["gross", "net"]
ContactMethod = Literal["chat", "email", "phone"]
DeclineReason = Literal["salary", "format", "stack", "not_looking", "company", "spam", "other"]
DECLINE_TITLES = {"salary": "не подходит вилка", "format": "не подходит формат работы", "stack": "не мой стек",
                  "not_looking": "сейчас не ищу работу", "company": "не интересна компания",
                  "spam": "спам или не соответствует описанию", "other": "другая причина"}


class _Fork(BaseModel):
    @model_validator(mode="after")
    def _fork(self):
        lo, hi = getattr(self, "salary_from", None), getattr(self, "salary_to", None)
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("salary_from больше salary_to")
        return self


class InviteIn(_Fork):
    ref: str = Field(min_length=4, max_length=12)
    salary_from: int = Field(gt=0, le=10_000_000)
    salary_to: int = Field(gt=0, le=10_000_000)
    gross_net: GrossNet
    description: str = Field(default="", max_length=2000)
    why_you: str = Field(min_length=1, max_length=1000)
    next_step: str = Field(min_length=1, max_length=500)
    contact_method: ContactMethod = "chat"
    hours_per_week: int | None = Field(default=None, gt=0, le=168)  # обязательно для несовершеннолетнего (ст. 92 ТК РФ)


class InviteDraftOut(BaseModel):
    ref: str
    alias: str
    salary_from: int
    salary_to: int
    gross_net: GrossNet
    description: str
    why_you: str
    next_step: str
    contact_method: ContactMethod
    quota_used: int
    quota_limit: int
    minor_hours_limit: int | None = None  # у кандидата 14–17 лет — предельное число часов в неделю


class AcceptIn(BaseModel):
    consent_contact_transfer: bool


class DeclineIn(BaseModel):
    reason: DeclineReason
    comment: str | None = Field(default=None, max_length=500)


class CounterIn(BaseModel):
    amount: int = Field(gt=0, le=10_000_000)
    gross_net: GrossNet
    comment: str | None = Field(default=None, max_length=500)


class CounterResponseIn(_Fork):
    action: Literal["offer_v2", "decline"]
    salary_from: int | None = Field(default=None, gt=0, le=10_000_000)
    salary_to: int | None = Field(default=None, gt=0, le=10_000_000)

    @model_validator(mode="after")
    def _v2_needs_fork(self):
        if self.action == "offer_v2" and (self.salary_from is None or self.salary_to is None):
            raise ValueError("для оффера v2 нужна вилка")
        return self


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("пустое сообщение")
        return v


class CompanyBrief(BaseModel):
    id: str
    name: str
    industry: str | None
    description: str | None
    trust_level: str


class GroupBrief(BaseModel):
    team_name: str
    size: int
    min_size: int
    deadline: datetime
    state: str
    min_reached_now: bool | None


class InvitationOut(BaseModel):
    """Приглашение глазами кандидата."""
    id: str
    status: str
    version: int
    company: CompanyBrief
    need_title: str
    salary_from: int
    salary_to: int
    gross_net: GrossNet
    salary_to_net: int
    description: str
    why_you: str
    next_step: str
    contact_method: ContactMethod
    expires_at: datetime
    counter_amount: int | None
    counter_expires_at: datetime | None
    created_at: datetime
    chat_open: bool
    hours_per_week: int | None = None
    group: GroupBrief | None = None  # командное приглашение: только своё место, без состава и чужих ответов


class EmployerInvitationOut(BaseModel):
    id: str
    status: str
    version: int
    ref: str
    alias: str
    salary_from: int
    salary_to: int
    gross_net: GrossNet
    expires_at: datetime
    counter_amount: int | None
    counter_comment: str | None
    counter_expires_at: datetime | None
    decline_reason: str | None
    created_at: datetime
    chat_open: bool
    viewed: bool  # кандидат открыл текущую версию оффера
    hours_per_week: int | None = None  # у кандидата младше 18 лет


class QuotaOut(BaseModel):
    used: int
    limit: int


class CandidateContacts(BaseModel):
    full_name: str | None
    email: str
    contacts: dict[str, str]


class MessageOut(BaseModel):
    id: int
    mine: bool
    author: Literal["candidate", "company"]
    text: str
    at: datetime


class ContactOut(BaseModel):
    """Страница контакта для обеих сторон; ФИО и контакты кандидата — только компании и только после согласия №4."""
    id: str
    status: str
    role: Literal["candidate", "employer"]
    company: CompanyBrief
    need_title: str
    alias: str
    candidate: CandidateContacts | None
    chat_open: bool
    messages: list[MessageOut]
