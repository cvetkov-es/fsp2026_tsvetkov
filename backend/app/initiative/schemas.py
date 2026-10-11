from datetime import datetime

from pydantic import BaseModel


class CompanyItemOut(BaseModel):
    id: str
    name: str
    industry: str | None
    description: str | None
    trust_level: str
    open_needs: int
    signal_id: str | None


class CompaniesOut(BaseModel):
    signals_left: int
    signals_limit: int  # число в тексте «осталось N из M» берётся из PARAMS, а не из фронтенда
    items: list[CompanyItemOut]


class SignalOut(BaseModel):
    signal_id: str
    signals_left: int


class InterestOut(BaseModel):
    ref: str
    alias: str
    specialization: str
    grade: str | None
    grade_status: str
    at: datetime


class DemandTechOut(BaseModel):
    tech: str
    share: float
    state: str
    skill: str | None


class DemandSkillOut(BaseModel):
    code: str
    title: str
    share: float


class DemandOut(BaseModel):
    category: str | None
    enough: bool
    companies: int | None
    min_companies: int
    window_days: int
    top: list[DemandTechOut]
    skills: list[DemandSkillOut]
