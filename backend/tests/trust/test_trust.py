import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.audit.models import AuditLog
from app.auth.models import Role, User
from app.auth.service import create_session
from app.common import clock
from app.employers.models import Company
from app.fsp.http import get_fsp_http
from app.moderation.types import TYPES
from tests.hiring.helpers import moderator

ACTIVE, LIQUIDATED = "7701001005", "5403003003"


@pytest.fixture
def http(client):
    """Серверные вызовы DaData — в мок того же приложения (как FSP ID в тестах 07a1)."""
    inner = TestClient(client.app)
    client.app.dependency_overrides[get_fsp_http] = lambda: inner
    return inner


def boss(client, db, email, verified=True):
    u = User(email=email, role=Role.employer, password_hash="x", email_verified_at=clock.now() if verified else None)
    db.add(u)
    db.commit()
    client.cookies.set("fsp_session", create_session(db, u))
    client.put("/api/v1/employer/company", json={"name": "Корп"})
    return u


def to_l2(client):
    client.post("/api/v1/employer/company/verify-domain")
    return client.post("/api/v1/employer/company/verify-inn", json={"inn": ACTIVE})


def test_domain_levels(client, db):
    boss(client, db, "hr@gmail.com")
    assert client.post("/api/v1/employer/company/verify-domain").json()["code"] == "public_domain"
    assert client.get("/api/v1/employer/company").json()["trust_level"] == "L0"
    boss(client, db, "hr@corp.ru")
    r = client.post("/api/v1/employer/company/verify-domain")
    assert r.status_code == 200 and r.json()["trust_level"] == "L1" and r.json()["domain"] == "corp.ru"


def test_domain_needs_a_verified_email_and_a_matching_domain(client, db):
    boss(client, db, "hr@corp.ru", verified=False)
    assert client.post("/api/v1/employer/company/verify-domain").json()["code"] == "email_unverified"
    u = boss(client, db, "hr2@other.ru")
    company = db.scalar(select(Company).where(Company.domain == "other.ru"))
    company.domain = "corp.ru"  # домен компании записан раньше, почта сотрудника — на другом
    db.commit()
    client.cookies.set("fsp_session", create_session(db, u))
    assert client.post("/api/v1/employer/company/verify-domain").json()["code"] == "domain_mismatch"


def test_inn_levels(client, db, http):
    boss(client, db, "hr@corp.ru")
    assert client.post("/api/v1/employer/company/verify-inn", json={"inn": ACTIVE}).json()["code"] == "l1_required"
    client.post("/api/v1/employer/company/verify-domain")
    assert client.post("/api/v1/employer/company/verify-inn", json={"inn": "7701001006"}).json()["code"] == "bad_inn"
    assert client.post("/api/v1/employer/company/verify-inn", json={"inn": LIQUIDATED}).json()["code"] == "company_inactive"
    out = client.post("/api/v1/employer/company/verify-inn", json={"inn": ACTIVE}).json()
    assert out["trust_level"] == "L2" and out["legal_name"] == "ООО «Компания 1005»"


def test_every_raise_is_audited_and_levels_never_go_down(client, db, http):
    boss(client, db, "hr@corp.ru")
    assert to_l2(client).status_code == 200
    actions = {a.action for a in db.scalars(select(AuditLog))}
    assert {"trust.L0->L1", "trust.L1->L2"} <= actions
    assert client.post("/api/v1/employer/company/verify-domain").json()["trust_level"] == "L2"  # повтор L1 уровень не понижает


def test_dadata_outage_is_503(client, db):
    boss(client, db, "hr@corp.ru")
    client.post("/api/v1/employer/company/verify-domain")

    class Down:
        def post(self, *a, **kw):
            import httpx
            raise httpx.ConnectError("нет сети")

    client.app.dependency_overrides[get_fsp_http] = lambda: Down()
    r = client.post("/api/v1/employer/company/verify-inn", json={"inn": ACTIVE})
    assert r.status_code == 503 and r.json()["code"] == "dadata_unavailable"


def test_unexpected_dadata_answers_are_503(client, db):
    boss(client, db, "hr@corp.ru")
    client.post("/api/v1/employer/company/verify-domain")

    class Reply:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    class Fake:
        def __init__(self, data):
            self.data = data

        def post(self, *a, **kw):
            return Reply(self.data)

    for data in (["не", "словарь"], {"suggestions": [{"value": "ООО", "data": {}}]}, {"suggestions": [{"data": {"state": {"status": "ACTIVE"}}}]}):
        client.app.dependency_overrides[get_fsp_http] = lambda d=data: Fake(d)
        r = client.post("/api/v1/employer/company/verify-inn", json={"inn": ACTIVE})
        assert r.status_code == 503 and r.json()["code"] == "dadata_unavailable", data


def test_l3_by_moderator_only(client, db, http):
    u = boss(client, db, "hr@corp.ru")
    assert client.post("/api/v1/employer/company/l3-request", json={"comment": "рано"}).json()["code"] == "l2_required"
    to_l2(client)
    assert client.post("/api/v1/employer/company/l3-request", json={"comment": "Аккредитованная ИТ-компания"}).status_code == 200
    assert client.get("/api/v1/employer/company").json()["l3_pending"] is True
    assert client.post("/api/v1/employer/company/l3-request", json={"comment": "ещё"}).json()["code"] == "l3_pending"
    moderator(client, db)
    case = client.get("/api/v1/moderation/cases").json()[0]
    assert case["type"] == "l3_request" and {a["code"] for a in case["actions"]} == {"approve", "reject"}
    assert any(s["value"] == "ООО «Компания 1005»" for s in case["summary"])
    client.post(f"/api/v1/moderation/cases/{case['id']}/resolve", json={"action": "approve"})
    client.cookies.set("fsp_session", create_session(db, u))
    assert client.get("/api/v1/employer/company").json()["trust_level"] == "L3"
    assert client.get("/api/v1/employer/company").json()["l3_pending"] is False


def test_l3_rejected_keeps_the_level(client, db, http):
    u = boss(client, db, "hr@corp.ru")
    to_l2(client)
    client.post("/api/v1/employer/company/l3-request", json={"comment": "Просим"})
    moderator(client, db)
    case = client.get("/api/v1/moderation/cases").json()[0]
    client.post(f"/api/v1/moderation/cases/{case['id']}/resolve", json={"action": "reject", "resolution_text": "Мало данных"})
    client.cookies.set("fsp_session", create_session(db, u))
    assert client.get("/api/v1/employer/company").json()["trust_level"] == "L2"


def test_l3_type_is_registered():
    assert "l3_request" in TYPES and set(TYPES["l3_request"].actions) == {"approve", "reject"}
