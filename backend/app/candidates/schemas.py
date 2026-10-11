from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Specialization = Literal["backend", "frontend", "data"]
GradeCode = Literal["junior", "middle", "senior"]


class SurveyIn(BaseModel):
    specialization: Specialization
    claimed_grade: GradeCode


class ProfileOut(BaseModel):
    specialization: str | None
    claimed_grade: str | None
    grade_status: str
    confirmed_grade: str | None
    status_grade: str | None  # грейд попытки, которая задала статус (для «X не подтверждён»)


Format = Literal["office", "hybrid", "remote"]


class DetailsIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    contacts: dict[str, str] = Field(default_factory=dict)
    experience_years: float | None = Field(default=None, ge=0, le=60)
    formats: list[Format] = Field(default_factory=list)
    city: str | None = Field(default=None, max_length=80)
    domains: list[Annotated[str, Field(min_length=1, max_length=40)]] = Field(default_factory=list, max_length=10)
    salary_threshold: int | None = Field(default=None, gt=0, le=10_000_000)
    salary_gross_net: Literal["gross", "net"] = "net"


class DetailsOut(DetailsIn):
    open_until: datetime | None


class StackIn(BaseModel):
    techs: list[str] = Field(max_length=40)


class StackItemOut(BaseModel):
    tech: str
    state: Literal["confirmed", "declared"]


class StackOut(BaseModel):
    items: list[StackItemOut]  # с учётом подтверждений и implies
    declared: list[str]  # ровно то, что заявил кандидат (значение для выбора стека)
    unknown: list[str]


class OpenWindowOut(BaseModel):
    open_until: datetime


class MarketOut(BaseModel):
    median_net: int | None
    n: int
