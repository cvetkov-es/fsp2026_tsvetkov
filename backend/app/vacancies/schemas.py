from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.config.params import PARAMS
from app.matching.schemas import CardOut


class VacancyIn(BaseModel):
    description: str = Field(min_length=10)

    @field_validator("description")
    @classmethod
    def _max(cls, v: str) -> str:
        if len(v) > PARAMS.vacancy_text_max:
            raise ValueError(f"не длиннее {PARAMS.vacancy_text_max} символов")
        return v


class ApplyIn(BaseModel):
    consent_contact_transfer: bool = False
    message: str = Field(default="", max_length=1000)


class AcceptIn(BaseModel):
    hours_per_week: int | None = Field(default=None, gt=0, le=168)  # обязательно для кандидата младше 18 лет


class DeclineIn(BaseModel):
    reason: str = Field(max_length=30)


class VacancyCompanyOut(BaseModel):
    id: str
    name: str
    industry: str | None
    trust_level: str


class MyApplicationOut(BaseModel):
    status: str
    contact_id: str | None


class VacancyOut(BaseModel):
    id: str
    need_id: str
    title: str
    description: str
    specialization: str
    grades: list[str]
    salary_from: int
    salary_to: int
    gross_net: str
    city: str | None
    formats: list[str]
    status: str
    created_at: datetime
    company: VacancyCompanyOut
    my_application: MyApplicationOut | None


class AppliedOut(BaseModel):
    id: str
    status: str


class AcceptedOut(BaseModel):
    contact_id: str


class MyApplicationRowOut(BaseModel):
    id: str
    status: str
    decline_reason: str | None
    contact_id: str | None
    created_at: datetime
    vacancy: VacancyOut


class EmployerApplicationOut(BaseModel):
    id: str
    alias: str
    ref: str
    message: str
    status: str
    decline_reason: str | None
    contact_id: str | None
    created_at: datetime
    card: CardOut | None
    minor_hours_limit: int | None = None  # кандидату нет 18: предел часов в неделю при принятии отклика
