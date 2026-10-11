import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import Role, User
from app.common.errors import AppError
from app.config.params import PARAMS
from app.employers.models import Company, CompanyMember, Need
from app.employers.schemas import CompanyIn, NeedIn
from app.matching.stack_dict import normalize_many


def employer_company(db: Session, user: User) -> Company | None:
    if user.role != Role.employer:
        raise AppError(403, "forbidden", "Доступно только работодателям")
    return db.scalar(select(Company).join(CompanyMember, CompanyMember.company_id == Company.id)
                     .where(CompanyMember.user_id == user.id))


def require_company(db: Session, user: User) -> Company:
    c = employer_company(db, user)
    if c is None:
        raise AppError(409, "company_required", "Сначала заполните профиль компании")
    return c


def upsert_company(db: Session, user: User, data: CompanyIn) -> Company:
    c = employer_company(db, user)
    if c is None:
        c = Company(name=data.name, domain=user.email.split("@")[-1])
        db.add(c)
        db.flush()
        db.add(CompanyMember(company_id=c.id, user_id=user.id))
    c.name, c.description, c.industry, c.contacts = data.name, data.description, data.industry, data.contacts
    db.commit()
    return c


def needs_limit(c: Company) -> int:
    return {"L0": PARAMS.needs_l0, "L1": PARAMS.needs_l1}.get(c.trust_level, PARAMS.needs_l2)


def _normalized(data: NeedIn) -> tuple[list[str], list[str]]:
    must, unk1 = normalize_many(data.must)
    nice, unk2 = normalize_many(data.nice)
    unknown = unk1 + [t for t in unk2 if t not in unk1]
    if unknown:
        raise AppError(422, "unknown_terms", "Неизвестные технологии", ", ".join(unknown))
    return must, [t for t in nice if t not in must]


def _apply(n: Need, data: NeedIn, must, nice) -> None:
    n.title, n.specialization, n.grades = data.title, data.specialization, list(data.grades)
    n.must, n.nice, n.formats, n.city = must, nice, list(data.formats), data.city
    n.salary_from, n.salary_to, n.gross_net = data.salary_from, data.salary_to, data.gross_net
    n.contact_method, n.raw_text = data.contact_method, data.raw_text
    n.employment = data.employment


def create_need(db: Session, user: User, data: NeedIn) -> Need:
    c = require_company(db, user)
    active = db.scalar(select(func.count()).select_from(Need).where(Need.company_id == c.id, Need.status == "active"))
    if active >= needs_limit(c):
        raise AppError(409, "needs_limit", "Лимит активных потребностей для вашего уровня доверия исчерпан. Закройте одну из текущих")
    must, nice = _normalized(data)
    n = Need(company_id=c.id)
    _apply(n, data, must, nice)
    db.add(n)
    db.commit()
    return n


def get_need(db: Session, user: User, need_id: uuid.UUID) -> Need:
    c = require_company(db, user)
    n = db.get(Need, need_id)
    if n is None or n.company_id != c.id:
        raise AppError(404, "need_not_found", "Потребность не найдена")
    return n


def update_need(db: Session, user: User, need_id: uuid.UUID, data: NeedIn) -> Need:
    n = get_need(db, user, need_id)
    must, nice = _normalized(data)
    _apply(n, data, must, nice)
    db.commit()
    return n


def close_need(db: Session, user: User, need_id: uuid.UUID) -> Need:
    n = get_need(db, user, need_id)
    n.status = "closed"
    db.commit()
    return n


def list_needs(db: Session, user: User) -> list[Need]:
    c = require_company(db, user)
    return list(db.scalars(select(Need).where(Need.company_id == c.id).order_by(Need.created_at.desc())))
