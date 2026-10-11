from typing import Literal

from pydantic import BaseModel, Field, model_validator

GradeCode = Literal["junior", "middle", "senior"]
Format = Literal["office", "hybrid", "remote"]


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    industry: str | None = Field(default=None, max_length=100)
    contacts: dict[str, str] = Field(default_factory=dict)


class CompanyOut(CompanyIn):
    id: str
    trust_level: str
    domain: str | None = None
    legal_name: str | None = None
    l3_pending: bool = False  # заявка на L3 на рассмотрении у модератора


class NeedIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    specialization: Literal["backend", "frontend", "data"]
    grades: list[GradeCode] = Field(min_length=1, max_length=3)
    must: list[str] = Field(default_factory=list, max_length=12)
    nice: list[str] = Field(default_factory=list, max_length=12)
    formats: list[Format] = Field(default_factory=list)
    city: str | None = Field(default=None, max_length=80)
    salary_from: int = Field(gt=0, le=10_000_000)
    salary_to: int = Field(gt=0, le=10_000_000)
    gross_net: Literal["gross", "net"]
    contact_method: Literal["chat", "email", "phone"] = "chat"
    raw_text: str | None = Field(default=None, max_length=8000)
    employment: Literal["full", "internship", "vacation"] = "full"  # стажировка и каникулярная работа — для 14–17 лет (2.10)

    @model_validator(mode="after")
    def _fork(self):
        if self.salary_from > self.salary_to:
            raise ValueError("salary_from больше salary_to")
        return self


class NeedOut(NeedIn):
    id: str
    status: str
