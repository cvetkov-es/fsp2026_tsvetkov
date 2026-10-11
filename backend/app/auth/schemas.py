import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterConsents(BaseModel):
    processing: bool = False
    distribution_preset: Literal["standard", "minimal"] | None = None


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    role: Literal["candidate", "employer"]
    # Полная дата нужна только для точной проверки возраста; в БД хранится лишь год
    birth_date: date | None = None
    consents: RegisterConsents


class RegisterOut(BaseModel):
    user_id: uuid.UUID
    email: str
    verify_url: str | None


class TokenIn(BaseModel):
    token: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_demo: bool
    impersonated_by: uuid.UUID | None = None
