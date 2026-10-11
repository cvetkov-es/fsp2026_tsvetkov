import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.contacts.schemas import ContactMethod, GrossNet, _Fork

GroupState = Literal["open", "ended", "min_reached", "not_reached", "closed"]


class MemberIn(_Fork):
    ref: str = Field(min_length=4, max_length=12)
    salary_from: int = Field(gt=0, le=10_000_000)  # у каждого участника своя вилка
    salary_to: int = Field(gt=0, le=10_000_000)
    hours_per_week: int | None = Field(default=None, gt=0, le=168)  # обязательно для участника младше 18 лет


class GroupIn(BaseModel):
    need_id: uuid.UUID
    team_id: str = Field(min_length=1, max_length=80)
    min_size: int = Field(ge=2)
    deadline: AwareDatetime  # без часового пояса — ошибка проверки, а не сравнение naive с aware
    members: list[MemberIn] = Field(min_length=2, max_length=12)
    gross_net: GrossNet
    description: str = Field(default="", max_length=2000)
    why_you: str = Field(min_length=1, max_length=1000)
    next_step: str = Field(min_length=1, max_length=500)
    contact_method: ContactMethod = "chat"


class LimitsOut(BaseModel):
    ttl_days: int  # самый поздний срок от отправки — GROUP_TTL
    min_team: int  # наименьшая команда — TEAM_MIN_ON_PLATFORM


class GroupMemberOut(BaseModel):
    contact_id: str
    alias: str
    status: str
    salary_from: int
    salary_to: int
    hours_per_week: int | None


class GroupOut(BaseModel):
    id: str
    team_name: str
    need_id: str
    need_title: str
    min_size: int
    size: int
    deadline: datetime
    state: GroupState
    min_reached_now: bool  # набран ли минимум сейчас (работодатель видит всегда)
    members: list[GroupMemberOut]


class GroupListItemOut(BaseModel):
    id: str
    team_name: str
    need_title: str
    size: int
    deadline: datetime
    state: GroupState


class GroupBriefOut(BaseModel):
    """Групповое приглашение глазами участника: без состава и без ответов других."""
    team_name: str
    size: int
    min_size: int
    deadline: datetime
    state: GroupState  # итог «минимум набран / не набран» скрыт («ended»), если минимум равен составу
    min_reached_now: bool | None  # None — минимум равен составу, показывать нечего
