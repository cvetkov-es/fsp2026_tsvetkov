import datetime as dt  # поле с именем date не должно перекрывать тип в аннотациях Pydantic

from pydantic import BaseModel, Field

from app.auth.schemas import RegisterConsents


class FspPendingOut(BaseModel):
    email: str | None
    name: str | None


class FspCompleteIn(BaseModel):
    ticket: str = Field(min_length=10, max_length=64)
    birth_date: dt.date
    consents: RegisterConsents


class FspResultOut(BaseModel):
    competition_title: str
    discipline_title: str
    date: dt.date
    place: int | None
    field_size: int | None
    tier: str
    tier_title: str
    team_name: str | None
    team_size: int | None
    counted: bool
    note: str | None


class FspOnlineOut(BaseModel):
    count: int
    disciplines: int


class FspRankOut(BaseModel):
    rank: str
    title: str
    valid_until: dt.date | None
    valid: bool


class FspOut(BaseModel):
    status: str
    login_via_fsp: bool = False  # аккаунт без пароля: FSP ID — единственный способ входа, отвязка его не удаляет
    summary: str | None
    last_sync_at: dt.datetime | None
    results: list[FspResultOut]
    online: FspOnlineOut
    ranks: list[FspRankOut]


class TeamMemberOut(BaseModel):
    ref: str
    alias: str
    specialization: str
    grade: str | None
    grade_status: str
    minor: bool = False  # 14–17 лет с согласием представителя: в приглашении нужны часы в неделю


class TeamOut(BaseModel):
    team_id: str
    team_name: str | None
    competition_title: str
    discipline_title: str
    date: dt.date
    place: int | None
    field_size: int | None
    tier: str
    team_size: int | None
    on_platform: int
    cohesion: float
    members: list[TeamMemberOut]
