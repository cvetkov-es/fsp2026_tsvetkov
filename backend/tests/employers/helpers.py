from app.auth.models import Role, User
from app.auth.service import create_session
from app.common import clock

NEED = {"title": "Бэкенд в платежи", "specialization": "backend", "grades": ["middle"],
        "must": ["python", "postgres"], "nice": ["kafka"], "formats": ["remote"], "city": None,
        "salary_from": 200000, "salary_to": 300000, "gross_net": "gross", "contact_method": "chat"}


def employer(client, db, email="hr@corp.ru"):
    u = User(email=email, role=Role.employer, password_hash="x", email_verified_at=clock.now())
    db.add(u)
    db.commit()
    client.cookies.set("fsp_session", create_session(db, u))
    return u
