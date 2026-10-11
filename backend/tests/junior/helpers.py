"""Общие шаги тестов юниорского трека: несовершеннолетний кандидат и согласие законного представителя."""
from datetime import date

from app.auth.models import User
from app.common import clock
from tests.contacts.helpers import as_user

STACK = ("Python", "PostgreSQL")


def minor(db, make_candidate, years=15, **kw):
    p = make_candidate(stack=STACK, **kw)
    u = db.get(User, p.user_id)
    today = clock.now().date()
    u.birth_date = date(today.year - years, 1, 1)
    db.commit()
    return p


def in_selection(client, need_id, ref) -> bool:
    blocks = client.get(f"/api/v1/employer/needs/{need_id}/selection").json()["blocks"]
    return any(c["ref"] == ref for b in blocks for c in b["items"])


def guardian_token(client, db, p, email="mama@example.ru") -> str:
    as_user(client, db, p.user_id)
    url = client.post("/api/v1/candidate/junior/guardian", json={"email": email}).json()["guardian_url"]
    client.cookies.clear()
    return url.rsplit("/", 1)[1]


def give_consent(client, db, p):
    token = guardian_token(client, db, p)
    assert client.post(f"/api/v1/guardian/{token}", json={"accept": True, "guardian_name": "Иванова Анна"}).status_code == 200
