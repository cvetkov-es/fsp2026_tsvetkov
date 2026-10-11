import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.auth.models import User
from app.common.errors import AppError
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.db.session import get_db
from app.employers.service import require_company
from app.integrations.models import Outbox, WebhookDelivery, WebhookEndpoint
from app.integrations.outbox import emit
from app.integrations.webhooks import check_url, new_secret

router = APIRouter(tags=["integrations"])
employer = require_roles("employer")


class WebhookIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)


class EndpointOut(BaseModel):
    id: str
    url: str
    created_at: str


class DeliveryOut(BaseModel):
    id: int
    endpoint_id: str
    event_type: str
    at: str
    status: str
    status_code: int | None
    attempt: int
    error: str | None


class IntegrationsOut(BaseModel):
    endpoints: list[EndpointOut]
    deliveries: list[DeliveryOut]
    mock_available: bool  # встроенный мок ATS включён (демо)


class CreatedOut(BaseModel):
    id: str
    url: str
    secret: str  # показывается один раз
    page: str | None = None  # страница мока ATS


def _own(db: Session, user: User, endpoint_id: uuid.UUID) -> WebhookEndpoint:
    company = require_company(db, user)
    ep = db.get(WebhookEndpoint, endpoint_id)
    if ep is None or ep.company_id != company.id or not ep.active:
        raise AppError(404, "webhook_not_found", "Вебхук не найден")
    return ep


def _create(db: Session, user: User, url: str, endpoint_id: uuid.UUID | None = None) -> WebhookEndpoint:
    company = require_company(db, user)
    active = db.scalar(select(func.count()).select_from(WebhookEndpoint).where(
        WebhookEndpoint.company_id == company.id, WebhookEndpoint.active.is_(True)))
    if active >= PARAMS.webhook_endpoints_max:
        raise AppError(409, "webhook_limit", f"Не больше {PARAMS.webhook_endpoints_max} вебхуков на компанию")
    ep = WebhookEndpoint(id=endpoint_id or uuid.uuid4(), company_id=company.id, url=url, secret=new_secret())
    db.add(ep)
    db.commit()
    return ep


@router.get("/employer/integrations", response_model=IntegrationsOut)
def integrations(user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    company = require_company(db, user)
    eps = db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.company_id == company.id, WebhookEndpoint.active.is_(True))
                     .order_by(WebhookEndpoint.created_at))
    rows = db.execute(select(WebhookDelivery, Outbox).join(Outbox, Outbox.id == WebhookDelivery.outbox_id)
                      .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
                      .where(WebhookEndpoint.company_id == company.id).order_by(WebhookDelivery.id.desc()).limit(20)).all()
    return {"endpoints": [{"id": str(e.id), "url": e.url, "created_at": e.created_at.isoformat()} for e in eps],
            "deliveries": [{"id": d.id, "endpoint_id": str(d.endpoint_id), "event_type": o.event_type, "at": o.created_at.isoformat(),
                            "status": d.status, "status_code": d.status_code, "attempt": d.attempt, "error": d.error} for d, o in rows],
            "mock_available": get_settings().mocks_on}


@router.post("/employer/integrations/webhooks", status_code=201, response_model=CreatedOut)
def create_webhook(data: WebhookIn, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    check_url(data.url)  # https и публичный адрес — иначе сервер стал бы ходить во внутреннюю сеть
    ep = _create(db, user, data.url)
    return {"id": str(ep.id), "url": ep.url, "secret": ep.secret}


@router.post("/employer/integrations/mock-ats", status_code=201, response_model=CreatedOut)
def connect_mock_ats(user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    """Демо: вебхук на встроенный мок ATS с собственным id в адресе; секрет показывается один раз, как у обычного."""
    if not get_settings().mocks_on:
        raise AppError(404, "mock_off", "Встроенный мок ATS выключен")
    base = get_settings().public_base_url.rstrip("/")
    eid = uuid.uuid4()
    ep = _create(db, user, f"{base}/mock/ats/{eid}/webhook", eid)
    return {"id": str(ep.id), "url": ep.url, "secret": ep.secret, "page": f"{base}/mock/ats/{eid}"}


@router.delete("/employer/integrations/webhooks/{endpoint_id}", status_code=204)
def delete_webhook(endpoint_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> Response:
    _own(db, user, endpoint_id).active = False  # журнал доставок остаётся
    db.commit()
    return Response(status_code=204)


@router.post("/employer/integrations/webhooks/{endpoint_id}/test", status_code=202)
def test_webhook(endpoint_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    ep = _own(db, user, endpoint_id)
    emit(db, ep.company_id, "ping", {"message": "Проверка связи с платформой обратного найма"})
    db.commit()
    return {"queued": True}
