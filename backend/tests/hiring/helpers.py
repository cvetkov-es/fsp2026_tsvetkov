"""Принятое приглашение, работодатель, модератор — общие шаги тестов доски найма и голосов."""
from app.auth.models import Role, User
from app.auth.service import create_session
from app.common import clock
from tests.contacts.helpers import Scene, as_user

STACK = ("Python", "PostgreSQL")


def accept(client, db, user_id, cid) -> None:
    as_user(client, db, user_id)
    r = client.post(f"/api/v1/candidate/invitations/{cid}/accept", json={"consent_contact_transfer": True})
    assert r.status_code == 200, r.text


def accepted(client, db, p, trust="L2", email="hr@corp.ru", company="Корп") -> tuple[Scene, str]:
    """Компания уровня trust приглашает кандидата p, он принимает; клиент — снова под работодателем."""
    s = Scene(client, db, trust_level=trust, email=email, company=company)
    cid = s.invite(p.public_ref).json()["id"]
    accept(client, db, p.user_id, cid)
    s.as_employer()
    return s, cid


def stage(client, cid, **body):
    return client.post(f"/api/v1/employer/contacts/{cid}/stage", json=body)


def moderator(client, db, email="mod@x.ru") -> User:
    u = User(email=email, role=Role.moderator, password_hash="x", email_verified_at=clock.now())
    db.add(u)
    db.commit()
    client.cookies.set("fsp_session", create_session(db, u))
    return u
