from datetime import timedelta

from sqlalchemy import func, select

from app.common import clock
from app.contacts.models import Contact, effective_status
from app.notifications.models import Notification
from app.notifications.service import latest, notify


def test_effective_status_by_time():
    t = clock.now()
    c = Contact(status="sent", expires_at=t + timedelta(hours=1))
    assert effective_status(c, t) == "sent" and effective_status(c, t + timedelta(hours=2)) == "expired"
    c = Contact(status="countered", expires_at=t - timedelta(days=9), counter_expires_at=t + timedelta(days=1))
    assert effective_status(c, t) == "countered"  # у встречного условия свой срок
    assert effective_status(c, t + timedelta(days=2)) == "expired"
    assert effective_status(Contact(status="accepted", expires_at=t - timedelta(days=1)), t) == "accepted"


def test_notify_is_idempotent_and_titled(db, make_candidate):
    p = make_candidate()
    for _ in range(2):
        notify(db, p.user_id, "invitation", {"company": "Корп", "link": "/candidate/invitations"}, "invitation:x:1")
    db.commit()
    assert db.scalar(select(func.count()).select_from(Notification)) == 1
    items, unread = latest(db, p.user_id)
    assert unread == 1 and items[0]["title"] == "Новое приглашение от компании «Корп»"
