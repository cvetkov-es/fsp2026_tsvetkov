"""Worker (техдизайн, решение 10): APScheduler, один экземпляр, раз в минуту. Все задачи идемпотентны.

Логика продукта от worker не зависит: статусы считаются лениво. Worker ускоряет истечение, шлёт напоминания и письма.
"""
import logging
import threading
from datetime import datetime, timedelta

import httpx
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import MSK, now
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.contacts.models import Contact
from app.contacts.service import refresh
from app.employers.models import Company
from app.fsp.sync import purge_fsp_temp
from app.hiring.jobs import remind_stages, vote_digest
from app.integrations.mail import Mailer, get_mailer
from app.integrations.outbox import deliver_webhooks
from app.mocks.fsp.oidc import purge_codes
from app.notifications.models import Notification
from app.notifications.service import notify, title_of

log = logging.getLogger("worker")
EMAIL_BATCH = 100


def expire_due(db: Session, t: datetime) -> int:
    rows = db.scalars(select(Contact).where(or_(
        and_(Contact.status.in_(("sent", "viewed", "offer_v2")), Contact.expires_at <= t),
        and_(Contact.status == "countered", Contact.counter_expires_at <= t))))
    return sum(1 for c in rows if refresh(db, c, t).status == "expired")


def remind_expiring(db: Session, t: datetime) -> int:
    soon = t + timedelta(hours=PARAMS.invite_remind_hours)
    n = 0
    for c in db.scalars(select(Contact).where(Contact.status.in_(("sent", "viewed", "offer_v2")),
                                              Contact.expires_at > t, Contact.expires_at <= soon)):
        company = db.get(Company, c.company_id)
        notify(db, c.user_id, "invitation_reminder",
               {"company": company.name, "expires": f"{c.expires_at.astimezone(MSK):%d.%m %H:%M}",
                "link": "/candidate/invitations"},
               f"invitation_reminder:{c.id}:{c.version}")
        n += 1
    return n


def send_emails(db: Session, mailer: Mailer) -> int:
    """Каждое письмо отмечается и фиксируется сразу: сбой SMTP посреди пачки не повторит уже отправленные."""
    base = get_settings().public_base_url.rstrip("/")
    rows = list(db.scalars(select(Notification).where(Notification.emailed_at.is_(None))
                           .order_by(Notification.id).limit(EMAIL_BATCH)))
    sent = 0
    for n in rows:
        user = db.get(User, n.user_id)
        title = title_of(n.kind, n.payload)
        link = f"\n\n{base}{n.payload['link']}" if n.payload.get("link") else ""
        try:
            mailer.send(user.email, title, f"{title}.{link}\n\nПлатформа обратного найма ФСП")
        except Exception:  # письмо уйдёт в следующую минуту; остальные — сейчас
            log.warning("worker: письмо %s не отправлено", n.id, exc_info=True)
            continue
        n.emailed_at = now()
        db.commit()
        sent += 1
    return sent


def send_webhooks(db: Session, t: datetime, http=None) -> dict:
    """Доставка событий в ATS компаний; сбой доставки продукт не ломает."""
    if http is not None:
        return deliver_webhooks(db, t, http)
    with httpx.Client(timeout=PARAMS.webhook_timeout_s) as client:
        return deliver_webhooks(db, t, client)


def run_once(db: Session, mailer: Mailer | None = None, http=None) -> dict:
    t = now()
    out = {"expired": expire_due(db, t), "reminders": remind_expiring(db, t),
           "fsp_purged": purge_fsp_temp(db, t) + purge_codes(db, t),
           "stage_reminders": remind_stages(db, t), "vote_digests": vote_digest(db, t)}
    db.commit()
    out["emails"] = send_emails(db, mailer or get_mailer())  # письма раньше вебхуков: медленный ATS их не задержит
    db.commit()
    out["webhooks"] = send_webhooks(db, t, http)
    db.commit()
    return out


def _tick() -> None:
    from app.db.session import _session_factory

    with _session_factory()() as db:
        try:
            log.info("worker: %s", run_once(db))
        except Exception:  # одна неудачная минута не останавливает worker; следующая попытка через минуту
            log.exception("worker: сбой итерации")


_lab_lock = threading.Lock()


def _lab_tick() -> None:
    from app.db.session import _session_factory
    from app.lab import service

    # Прогон идёт минуты: следующий тик молча выходит, а не пишет WARNING APScheduler о max_instances
    if not _lab_lock.acquire(blocking=False):
        return
    try:
        with _session_factory()() as db:
            try:
                run = service.run_pending(db)
                if run:
                    log.info("lab: прогон %s — %s", run.id, run.status)
            except Exception:
                log.exception("lab: сбой")
    finally:
        _lab_lock.release()


def _lab_startup() -> None:
    from app.db.session import _session_factory
    from app.lab.service import reset_interrupted

    with _session_factory()() as db:
        if n := reset_interrupted(db):
            log.warning("lab: %s прогон(ов) прерваны перезапуском worker", n)


def main() -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler

    import app.db.all_models  # noqa: F401

    logging.basicConfig(level=logging.INFO)
    _lab_startup()
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(_tick, "interval", minutes=1, next_run_time=now(), max_instances=1, coalesce=True)
    # Прогон лаборатории идёт минуты — отдельная задача, чтобы не задерживать письма и истечения.
    # max_instances=2: тик во время прогона видит _lab_lock и сразу выходит, без WARNING о пропуске
    scheduler.add_job(_lab_tick, "interval", minutes=1, next_run_time=now(), max_instances=2, coalesce=True)
    scheduler.start()


if __name__ == "__main__":
    main()
