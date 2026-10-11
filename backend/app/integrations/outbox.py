"""Outbox и доставка вебхуков (процесс 4.7): события пишутся вместе с действием, worker доставляет их на вебхуки компании.

Сбой доставки на продукт не влияет: исключение при отправке превращается в повтор по расписанию, а после
`WEBHOOK_MAX_ATTEMPTS` попыток доставка получает статус «failed».
"""
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.fsp.http import server_url
from app.integrations.models import Outbox, WebhookDelivery, WebhookEndpoint
from app.integrations.webhooks import body_of, check_url, headers

log = logging.getLogger(__name__)


def emit(db: Session, company_id, event_type: str, payload: dict) -> None:
    """Кладёт событие в outbox в транзакции вызывающего; ПДн в payload не допускаются (псевдонимы, ссылка на контакт)."""
    db.add(Outbox(company_id=company_id, event_type=event_type, payload=payload, created_at=now()))


def _fan_out(db: Session, t: datetime) -> int:
    n = 0
    for ev in db.scalars(select(Outbox).where(Outbox.processed_at.is_(None)).order_by(Outbox.id).limit(PARAMS.webhook_batch)):
        for ep_id in db.scalars(select(WebhookEndpoint.id).where(WebhookEndpoint.company_id == ev.company_id,
                                                                  WebhookEndpoint.active.is_(True))):
            db.execute(insert(WebhookDelivery).values(endpoint_id=ep_id, outbox_id=ev.id, next_attempt_at=t, created_at=t)
                       .on_conflict_do_nothing(index_elements=["endpoint_id", "outbox_id"]))
            n += 1
        ev.processed_at = t
    db.commit()
    return n


def _attempt(db: Session, d: WebhookDelivery, t: datetime, http, check) -> bool:
    ep, ev = db.get(WebhookEndpoint, d.endpoint_id), db.get(Outbox, d.outbox_id)
    if not ep.active:
        d.status, d.error = "failed", "endpoint_off"
        return False
    try:
        check(ep.url)  # DNS мог измениться с момента создания вебхука
    except AppError:
        d.status, d.error = "failed", "url_blocked"
        return False
    body = body_of(ev.event_type, ev.payload, ev.created_at.isoformat())
    code: int | None = None
    error: str | None = None
    try:
        r = http.post(server_url(ep.url), content=body, headers=headers(ep.secret, f"msg_{ev.id}", int(t.timestamp()), body),
                      follow_redirects=False)
        code = r.status_code
    except Exception as e:  # сеть, TLS, таймаут: подробности в журнал не пишем — только класс ошибки
        error = type(e).__name__
        log.warning("webhook %s: %s", d.id, error)
    d.status_code = code
    if code is not None and 200 <= code < 300:
        d.status, d.delivered_at, d.error = "delivered", t, None
        return True
    d.attempt += 1
    d.error = error or f"HTTP {code}"
    if d.attempt >= PARAMS.webhook_max_attempts:
        d.status = "failed"
    else:
        d.next_attempt_at = t + timedelta(minutes=PARAMS.webhook_backoff_min[min(d.attempt, len(PARAMS.webhook_backoff_min)) - 1])
    return False


def deliver_webhooks(db: Session, t: datetime, http, check=check_url) -> dict:
    """Один тик worker: разложить новые события по эндпоинтам компаний и отправить то, чьё время пришло."""
    queued = _fan_out(db, t)
    sent, started = 0, time.monotonic()
    for d in db.scalars(select(WebhookDelivery).where(WebhookDelivery.status == "pending", WebhookDelivery.next_attempt_at <= t)
                        .order_by(WebhookDelivery.id).limit(PARAMS.webhook_batch)):
        sent += int(_attempt(db, d, t, http, check))
        db.commit()
        if time.monotonic() - started > PARAMS.webhook_tick_budget_s:
            break  # остальное доставится следующим тиком
    return {"queued": queued, "sent": sent}
