"""Встроенный мок ATS (демо): принимает вебхуки, проверяет подпись Standard Webhooks и показывает полученные события."""
import html
import json
import uuid

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.common.errors import AppError
from app.db.session import get_db
from app.integrations.models import WebhookEndpoint
from app.integrations.webhooks import verify
from app.mocks.ats.models import MockAtsEvent

router = APIRouter()
BODY_MAX = 64 * 1024  # событие — короткий JSON; больше мок не принимает и не хранит
EVENTS_KEEP = 200  # на один адрес: мок — демонстрация, а не архив


def _store(db: Session, ep: WebhookEndpoint, h, body: str) -> bool:
    valid = verify(ep.secret, h.get("webhook-id", ""), h.get("webhook-timestamp", ""), body, h.get("webhook-signature", ""))
    if valid:  # тело с неверной подписью не хранится: страница мока не превращается в свалку чужих данных
        try:
            type_ = str(json.loads(body).get("type", "?"))[:60]
        except (ValueError, AttributeError):
            type_ = "?"
        db.add(MockAtsEvent(endpoint_id=ep.id, type=type_, valid=True, body=body))
        db.flush()
        keep = select(MockAtsEvent.id).where(MockAtsEvent.endpoint_id == ep.id).order_by(MockAtsEvent.id.desc()).limit(EVENTS_KEEP)
        db.execute(delete(MockAtsEvent).where(MockAtsEvent.endpoint_id == ep.id, MockAtsEvent.id.not_in(keep)))
    db.commit()
    return valid


@router.post("/{endpoint_id}/webhook")
async def receive(endpoint_id: uuid.UUID, request: Request, db: Session = Depends(get_db)) -> Response:
    ep = db.get(WebhookEndpoint, endpoint_id)
    if ep is None:
        raise AppError(404, "ats_endpoint_not_found", "Такого адреса нет")
    raw = b""
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > BODY_MAX:
            return Response(status_code=413, content='{"error":"too_large"}', media_type="application/json")
    if not await run_in_threadpool(_store, db, ep, request.headers, raw.decode("utf-8", "replace")):
        return Response(status_code=400, content='{"error":"invalid_signature"}', media_type="application/json")
    return Response(status_code=204)


@router.get("/{endpoint_id}", response_class=HTMLResponse)
def page(endpoint_id: uuid.UUID, db: Session = Depends(get_db)) -> str:
    rows = db.scalars(select(MockAtsEvent).where(MockAtsEvent.endpoint_id == endpoint_id)
                      .order_by(MockAtsEvent.id.desc()).limit(100))
    items = "".join(
        f"<tr><td>{html.escape(e.type)}</td><td>{e.received_at:%d.%m.%Y %H:%M:%S} UTC</td>"
        f"<td>{'подпись верна' if e.valid else 'подпись неверна'}</td></tr>" for e in rows)
    body = items or '<tr><td colspan="3">Событий пока нет. Пригласите кандидата, и событие придёт в течение минуты.</td></tr>'
    return ("<!doctype html><html lang=\"ru\"><head><meta charset=\"utf-8\"><title>Мок ATS</title></head><body style=\"font-family:sans-serif;"
            "max-width:48rem;margin:2rem auto\"><h1>Мок ATS: полученные события</h1><table border=\"1\" cellpadding=\"6\">"
            f"<tr><th>Тип</th><th>Время</th><th>Подпись</th></tr>{body}</table></body></html>")
