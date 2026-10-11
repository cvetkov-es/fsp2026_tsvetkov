"""Повышение уровня доверия компании (процесс 4.1): только вверх и по порядку; каждое повышение — в аудит."""
import re
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.models import User
from app.common.errors import AppError
from app.employers.models import Company
from app.employers.service import require_company
from app.integrations.dadata import find_party
from app.llm.masking import inn_ok
from app.moderation.models import Case
from app.moderation.service import open_case
from app.moderation.types import CaseType, register, row

LEVELS = ("L0", "L1", "L2", "L3")
PUBLIC_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "mail.ru", "bk.ru", "inbox.ru", "list.ru", "internet.ru", "yandex.ru", "ya.ru",
    "yandex.com", "rambler.ru", "outlook.com", "hotmail.com", "live.com", "icloud.com", "me.com", "proton.me",
    "protonmail.com", "yahoo.com", "gmx.com", "vk.com",
})


def raise_level(db: Session, actor_id: uuid.UUID, c: Company, level: str) -> None:
    """Уровень только растёт; повторная проверка нижнего уровня его не понижает."""
    if LEVELS.index(level) > LEVELS.index(c.trust_level):
        audit(db, actor_id, f"trust.{c.trust_level}->{level}", "company", str(c.id))
        c.trust_level = level


def verify_domain(db: Session, user: User) -> Company:
    c = require_company(db, user)
    if user.email_verified_at is None:
        raise AppError(409, "email_unverified", "Сначала подтвердите почту")
    domain = user.email.rsplit("@", 1)[1].lower()
    if domain in PUBLIC_DOMAINS:
        raise AppError(409, "public_domain", "Публичная почта не подтверждает компанию. Нужна почта на корпоративном домене")
    if c.domain and c.domain.lower() != domain:
        raise AppError(409, "domain_mismatch", f"Домен почты не совпадает с доменом компании {c.domain}")
    c.domain = domain
    raise_level(db, user.id, c, "L1")
    db.commit()
    return c


def verify_inn(db: Session, user: User, inn: str, http: httpx.Client) -> Company:
    c = require_company(db, user)
    if LEVELS.index(c.trust_level) < LEVELS.index("L1"):
        raise AppError(409, "l1_required", "Сначала подтвердите корпоративный домен (уровень L1)")
    digits = re.sub(r"\D", "", inn)
    if not inn_ok(digits):
        raise AppError(422, "bad_inn", "Проверьте ИНН: не сходится контрольная сумма")
    party = find_party(http, digits)
    if party is None:
        raise AppError(404, "inn_not_found", "Организация с таким ИНН не найдена")
    if party["data"]["state"]["status"] != "ACTIVE":
        raise AppError(409, "company_inactive", "Организация ликвидирована или ликвидируется")
    c.inn, c.legal_name = digits, party["value"]
    raise_level(db, user.id, c, "L2")
    db.commit()
    return c


def _pending_l3(c: Company):
    return select(Case.id).where(Case.type == "l3_request", Case.status == "open", Case.refs["company_id"].astext == str(c.id))


def l3_pending(db: Session, c: Company) -> bool:
    return db.scalar(_pending_l3(c)) is not None


def request_l3(db: Session, user: User, comment: str) -> Company:
    c = require_company(db, user)
    db.execute(select(Company.id).where(Company.id == c.id).with_for_update())  # двойной клик не открывает два обращения
    if c.trust_level != "L2":
        raise AppError(409, "l2_required", "Заявку на L3 можно подать с уровня L2")
    if l3_pending(db, c):
        raise AppError(409, "l3_pending", "Заявка уже на рассмотрении")
    open_case(db, "l3_request", {"company_id": str(c.id)}, user.id, comment)
    db.commit()
    return c


# --- тип обращения «Заявка на L3»

def _l3_summary(db: Session, case: Case) -> list[dict]:
    c = db.get(Company, uuid.UUID(case.refs["company_id"]))
    if c is None:
        return [row("Компания", "удалена. Обращение можно закрыть")]
    return [row("Компания", c.name), row("Юрлицо", c.legal_name or "—"), row("ИНН", c.inn or "—"),
            row("Домен", c.domain or "—"), row("Текущий уровень", c.trust_level)]


def _l3_apply(db: Session, case: Case, action: str) -> str:
    c = db.get(Company, uuid.UUID(case.refs["company_id"]), with_for_update=True)
    if c is None:
        return "компания уже удалена"
    if action != "approve":
        return "заявка отклонена, уровень не изменился"
    raise_level(db, case.resolved_by, c, "L3")
    return "присвоен уровень L3"


register("l3_request", CaseType(
    title="Заявка на уровень L3", actions={"approve": "Присвоить L3", "reject": "Отклонить"}, summary=_l3_summary,
    apply=_l3_apply, link="/employer/company"))
