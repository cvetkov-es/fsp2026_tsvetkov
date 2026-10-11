"""Все переходы машины состояний контакта, включая недопустимые (спецификация 5.3)."""
import uuid
from datetime import timedelta

from app.common import clock
from app.contacts.models import Contact
from tests.contacts.helpers import Scene, as_user

STATUSES = ("sent", "viewed", "accepted", "declined", "countered", "offer_v2", "company_declined", "expired",
            "withdrawn", "revoked")
# действие → (сторона, путь, тело, статусы, из которых действие допустимо)
ACTIONS = {
    "accept": ("candidate", "candidate/invitations/{id}/accept", {"consent_contact_transfer": True}, {"sent", "viewed", "offer_v2"}),
    "decline": ("candidate", "candidate/invitations/{id}/decline", {"reason": "other"}, {"sent", "viewed", "offer_v2"}),
    "counter": ("candidate", "candidate/invitations/{id}/counter", {"amount": 400000, "gross_net": "gross"}, {"sent", "viewed"}),
    "revoke": ("candidate", "candidate/invitations/{id}/revoke", None, {"accepted"}),
    "respond": ("employer", "employer/invitations/{id}/counter-response", {"action": "decline"}, {"countered"}),
    "withdraw": ("employer", "employer/invitations/{id}/withdraw", None, {"sent", "viewed", "offer_v2", "countered"}),
}


def test_transition_matrix(client, db, make_candidate):
    p = make_candidate(stack=("Python", "PostgreSQL"))
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    c = db.get(Contact, uuid.UUID(cid))
    for status in STATUSES:
        for name, (side, path, body, allowed) in ACTIONS.items():
            c.status, c.version, c.revoked_at = status, 2 if status == "offer_v2" else 1, None
            c.expires_at = clock.now() + timedelta(days=1)
            c.counter_expires_at = clock.now() + timedelta(days=1) if status == "countered" else None
            db.commit()
            as_user(client, db, p.user_id if side == "candidate" else s.employer.id)
            r = client.post("/api/v1/" + path.format(id=cid), json=body)
            expected = 200 if status in allowed else 409
            assert r.status_code == expected, f"{name} из «{status}»: {r.status_code} {r.text[:120]}"
