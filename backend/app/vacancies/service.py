"""Вакансии и отклики (процесс 4.8): вилка обязательна, отклик — с согласием №4, принятый отклик — контакт."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.consents import ConsentType, record_consent
from app.auth.models import User
from app.candidates.models import CandidateProfile
from app.candidates.service import get_or_create_profile
from app.common.clock import now
from app.common.errors import AppError
from app.contacts.models import CompanyBlock, Contact, ContactEvent
from app.contacts.service import _consent_active, _members, ensure_no_contact
from app.employers.models import Company, Need
from app.employers.service import get_need, require_company
from app.junior.rules import age_of, is_minor_age, minor_hours_limit
from app.matching.scoring import evaluate_candidate
from app.matching.service import alias, card, load_rows, need_facts
from app.notifications.service import notify
from app.vacancies.models import Application, Vacancy
from app.vacancies.schemas import AcceptIn, ApplyIn, DeclineIn, VacancyIn


def _vacancy_out(db: Session, v: Vacancy, mine: Application | None = None) -> dict:
    c = db.get(Company, v.company_id)
    return {"id": str(v.id), "need_id": str(v.need_id), "title": v.title, "description": v.description,
            "specialization": v.specialization, "grades": v.grades, "salary_from": v.salary_from,
            "salary_to": v.salary_to, "gross_net": v.gross_net, "city": v.city, "formats": v.formats,
            "status": v.status, "created_at": v.created_at,
            "company": {"id": str(c.id), "name": c.name, "industry": c.industry, "trust_level": c.trust_level},
            "my_application": None if mine is None else {"status": mine.status,
                                                         "contact_id": str(mine.contact_id) if mine.contact_id else None}}


def publish(db: Session, user: User, need_id: uuid.UUID, data: VacancyIn) -> dict:
    n = get_need(db, user, need_id)
    if n.status != "active":
        raise AppError(409, "need_closed", "Потребность закрыта")
    db.execute(select(Need.id).where(Need.id == n.id).with_for_update())  # двойной клик не даёт IntegrityError
    if db.scalar(select(Vacancy.id).where(Vacancy.need_id == n.id)):
        raise AppError(409, "vacancy_exists", "Вакансия по этой потребности уже опубликована")
    v = Vacancy(company_id=n.company_id, need_id=n.id, title=n.title, description=data.description,
                specialization=n.specialization, grades=list(n.grades), salary_from=n.salary_from,
                salary_to=n.salary_to, gross_net=n.gross_net, city=n.city, formats=list(n.formats))
    db.add(v)
    db.commit()
    return _vacancy_out(db, v)


def company_vacancies(db: Session, user: User) -> list[dict]:
    company = require_company(db, user)
    return [_vacancy_out(db, v) for v in db.scalars(select(Vacancy).where(Vacancy.company_id == company.id)
                                                     .order_by(Vacancy.created_at.desc()))]


def _own_vacancy(db: Session, user: User, vacancy_id: uuid.UUID) -> Vacancy:
    company = require_company(db, user)
    v = db.get(Vacancy, vacancy_id)
    if v is None or v.company_id != company.id:
        raise AppError(404, "vacancy_not_found", "Вакансия не найдена")
    return v


def close(db: Session, user: User, vacancy_id: uuid.UUID) -> dict:
    v = _own_vacancy(db, user, vacancy_id)
    v.status = "closed"
    db.commit()
    return _vacancy_out(db, v)


def _is_minor(user: User) -> bool:
    return is_minor_age(age_of(user.birth_date, user.birth_year, now().date()))


def _check_minor(db: Session, user: User, profile: CandidateProfile, need: Need) -> None:
    """Юниорский трек (2.10): отклик не обход правил — без согласия представителя профиль скрыт, на полную занятость нельзя."""
    if not _is_minor(user):
        return
    if profile.guardian_consent_at is None:
        raise AppError(409, "guardian_consent_required", "Ваш профиль пока черновик: нужно согласие законного представителя")
    if need.employment == "full":
        raise AppError(409, "minor_full_employment", "Несовершеннолетним доступны только стажировка и каникулярная работа")


def open_vacancies(db: Session, user: User, specialization: str | None) -> list[dict]:
    blocked = set(db.scalars(select(CompanyBlock.company_id).where(CompanyBlock.user_id == user.id)))
    mine = {a.vacancy_id: a for a in db.scalars(select(Application).where(Application.user_id == user.id))}
    stmt = select(Vacancy).where(Vacancy.status == "open")
    if specialization:
        stmt = stmt.where(Vacancy.specialization == specialization)
    vacancies = [v for v in db.scalars(stmt.order_by(Vacancy.created_at.desc())) if v.company_id not in blocked]
    if _is_minor(user):  # профиль несовершеннолетнего — черновик до согласия; потом только стажировка и каникулы
        if get_or_create_profile(db, user).guardian_consent_at is None:
            return []
        full = set(db.scalars(select(Need.id).where(Need.employment == "full")))
        vacancies = [v for v in vacancies if v.need_id not in full]
    return [_vacancy_out(db, v, mine.get(v.id)) for v in vacancies]


def apply(db: Session, user: User, vacancy_id: uuid.UUID, data: ApplyIn) -> dict:
    p = get_or_create_profile(db, user)
    v = db.get(Vacancy, vacancy_id, with_for_update=True)  # отклики на вакансию идут по очереди: повтор — 409, не 500
    if v is None or v.status != "open":
        raise AppError(409, "vacancy_closed", "Вакансия закрыта")
    if db.get(CompanyBlock, (user.id, v.company_id)):
        raise AppError(409, "company_blocked", "Эта компания скрыта в ваших настройках")
    _check_minor(db, user, p, db.get(Need, v.need_id))
    if not data.consent_contact_transfer:
        raise AppError(422, "consent_required", "Для отклика нужно согласие на передачу контактов компании")
    if db.scalar(select(Application.id).where(Application.vacancy_id == v.id, Application.user_id == user.id)):
        raise AppError(409, "already_applied", "Вы уже откликнулись на эту вакансию")
    ensure_no_contact(db, v.need_id, user.id, by_candidate=True)
    record_consent(db, user.id, ConsentType.contact_transfer, target_company_id=v.company_id)
    a = Application(vacancy_id=v.id, user_id=user.id, message=data.message)
    db.add(a)
    db.flush()
    for uid in _members(db, v.company_id):
        notify(db, uid, "application", {"alias": alias(p), "title": v.title, "link": "/employer/vacancies"},
               f"application:{a.id}:{uid}")
    db.commit()
    return {"id": str(a.id), "status": a.status}


def my_applications(db: Session, user: User) -> list[dict]:
    out = []
    for a in db.scalars(select(Application).where(Application.user_id == user.id).order_by(Application.created_at.desc())):
        v = db.get(Vacancy, a.vacancy_id)
        out.append({"id": str(a.id), "status": a.status, "decline_reason": a.decline_reason,
                    "contact_id": str(a.contact_id) if a.contact_id else None, "created_at": a.created_at,
                    "vacancy": _vacancy_out(db, v)})
    return out


def applications(db: Session, user: User, vacancy_id: uuid.UUID) -> list[dict]:
    """Список откликов; новые при просмотре становятся «просмотрен». Кандидат — под псевдонимом, с карточкой."""
    v = _own_vacancy(db, user, vacancy_id)
    n = db.get(Need, v.need_id)
    t = now()
    rows = {r.profile.user_id: r for r in load_rows(db, n.specialization, n.company_id)}
    out = []
    for a in db.scalars(select(Application).where(Application.vacancy_id == v.id).order_by(Application.created_at)):
        if a.status == "sent":
            a.status = "viewed"
        p = db.get(CandidateProfile, a.user_id)
        row = rows.get(a.user_id)
        c = None
        if row is not None:
            nf = need_facts(n)
            c = card(row, evaluate_candidate(row.facts, nf, t), nf, None)
        u = db.get(User, a.user_id)
        out.append({"id": str(a.id), "alias": alias(p), "ref": p.public_ref, "message": a.message, "status": a.status,
                    "decline_reason": a.decline_reason, "contact_id": str(a.contact_id) if a.contact_id else None,
                    "created_at": a.created_at, "card": c,
                    "minor_hours_limit": minor_hours_limit(u.birth_date, u.birth_year, n.employment, t.date())})
    db.commit()
    return out


def _own_application(db: Session, user: User, application_id: uuid.UUID) -> tuple[Application, Vacancy]:
    a = db.get(Application, application_id, with_for_update=True)
    if a is None:
        raise AppError(404, "application_not_found", "Отклик не найден")
    return a, _own_vacancy(db, user, a.vacancy_id)


def accept(db: Session, user: User, application_id: uuid.UUID, data: AcceptIn | None = None) -> dict:
    a, v = _own_application(db, user, application_id)
    if a.status in ("accepted", "declined"):
        raise AppError(409, "application_closed", "Отклик уже рассмотрен")
    n = db.get(Need, v.need_id)
    if db.get(CompanyBlock, (a.user_id, v.company_id)):
        raise AppError(409, "candidate_unavailable", "Кандидат недоступен: он скрыл вашу компанию после отклика")
    db.execute(select(Need.id).where(Need.id == n.id).with_for_update())  # как в invite: пара под блокировкой потребности
    ensure_no_contact(db, n.id, a.user_id)
    applicant = db.get(User, a.user_id)
    _check_minor(db, applicant, db.get(CandidateProfile, a.user_id), n)  # согласие могло исчезнуть после отклика
    t = now()
    cap = minor_hours_limit(applicant.birth_date, applicant.birth_year, n.employment, t.date())
    hours = data.hours_per_week if data else None
    if cap is not None and hours is None:
        raise AppError(422, "hours_required", "Для кандидата младше 18 лет укажите часы в неделю",
                       f"Не больше {cap} ч в неделю (ст. 92 ТК РФ)")
    if cap is not None and hours > cap:
        raise AppError(422, "hours_over_limit", "Часов в неделю больше, чем допускает закон для возраста кандидата",
                       f"Не больше {cap} ч в неделю (ст. 92 ТК РФ)")
    c = Contact(channel="application", need_id=v.need_id, vacancy_id=v.id, company_id=v.company_id, user_id=a.user_id,
                status="accepted", salary_from=v.salary_from, salary_to=v.salary_to, gross_net=v.gross_net,
                description=v.description[:2000], contact_method=n.contact_method, expires_at=t,
                contacts_revealed_at=t, hours_per_week=hours if cap is not None else None)
    if not _consent_active(db, c):
        raise AppError(409, "consent_revoked", "Кандидат отозвал согласие на передачу контактов")
    db.add(c)
    db.flush()
    db.add(ContactEvent(contact_id=c.id, type="application_accepted", actor="employer",
                        payload={"application_id": str(a.id)}))
    a.status, a.contact_id = "accepted", c.id
    company = db.get(Company, v.company_id)
    notify(db, a.user_id, "application_accepted", {"company": company.name, "link": f"/contacts/{c.id}"},
           f"application_accepted:{a.id}")
    db.commit()
    return {"contact_id": str(c.id)}


def decline(db: Session, user: User, application_id: uuid.UUID, data: DeclineIn) -> dict:
    a, v = _own_application(db, user, application_id)
    if a.status in ("accepted", "declined"):
        raise AppError(409, "application_closed", "Отклик уже рассмотрен")
    a.status, a.decline_reason = "declined", data.reason
    company = db.get(Company, v.company_id)
    notify(db, a.user_id, "application_declined", {"company": company.name, "link": "/candidate/vacancies"},
           f"application_declined:{a.id}")
    db.commit()
    return {"id": str(a.id), "status": a.status}
