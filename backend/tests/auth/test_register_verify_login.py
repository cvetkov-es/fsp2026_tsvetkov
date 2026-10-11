from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.auth.models import Consent

CAND = {
    "email": "Ivan@Example.ru",
    "password": "correct horse 1",
    "role": "candidate",
    "birth_date": "2000-01-15",
    "consents": {"processing": True, "distribution_preset": "standard"},
}


def _token(verify_url: str) -> str:
    return parse_qs(urlparse(verify_url).query)["token"][0]


def test_full_flow_register_verify_login_me(client, db):
    r = client.post("/api/v1/auth/register", json=CAND)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "ivan@example.ru" and body["verify_url"]
    types = sorted(c.type for c in db.scalars(select(Consent)))
    assert types == ["distribution", "processing"]

    r = client.post("/api/v1/auth/login", json={"email": "ivan@example.ru", "password": "correct horse 1"})
    assert r.status_code == 403 and r.json()["code"] == "email_not_verified"

    assert client.post("/api/v1/auth/verify", json={"token": _token(body["verify_url"])}).status_code == 204

    r = client.post("/api/v1/auth/login", json={"email": "IVAN@example.ru", "password": "correct horse 1"})
    assert r.status_code == 200 and "fsp_session" in r.cookies
    me = client.get("/api/v1/auth/me").json()
    assert me["email"] == "ivan@example.ru" and me["role"] == "candidate"

    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_duplicate_email_case_insensitive(client):
    assert client.post("/api/v1/auth/register", json=CAND).status_code == 201
    r = client.post("/api/v1/auth/register", json={**CAND, "email": "IVAN@EXAMPLE.RU"})
    assert r.status_code == 409 and r.json()["code"] == "email_taken"


def test_verify_token_single_use(client):
    url = client.post("/api/v1/auth/register", json=CAND).json()["verify_url"]
    assert client.post("/api/v1/auth/verify", json={"token": _token(url)}).status_code == 204
    r = client.post("/api/v1/auth/verify", json={"token": _token(url)})
    assert r.status_code == 400 and r.json()["code"] == "token_invalid"


def test_candidate_requires_both_consents(client):
    r = client.post("/api/v1/auth/register", json={**CAND, "consents": {"processing": True}})
    assert r.status_code == 422 and r.json()["code"] == "consent_required"
    r = client.post("/api/v1/auth/register", json={**CAND, "consents": {"processing": False, "distribution_preset": "standard"}})
    assert r.status_code == 422 and r.json()["code"] == "consent_required"


def test_under_14_rejected_and_employer_needs_only_processing(client):
    r = client.post("/api/v1/auth/register", json={**CAND, "birth_date": "2015-01-01"})
    assert r.status_code == 422 and r.json()["code"] == "age_restricted"
    emp = {"email": "hr@corp.ru", "password": "correct horse 1", "role": "employer",
           "consents": {"processing": True}}
    assert client.post("/api/v1/auth/register", json=emp).status_code == 201


def test_wrong_password_401(client):
    url = client.post("/api/v1/auth/register", json=CAND).json()["verify_url"]
    client.post("/api/v1/auth/verify", json={"token": _token(url)})
    r = client.post("/api/v1/auth/login", json={"email": "ivan@example.ru", "password": "nope"})
    assert r.status_code == 401 and r.json()["code"] == "bad_credentials"


def test_consent_texts_endpoint(client):
    r = client.get("/api/v1/consents/texts")
    assert r.status_code == 200
    data = r.json()
    assert {t["type"] for t in data["texts"]} == {"processing", "distribution", "automated_rules", "contact_transfer"}
    assert "standard" in data["presets"]
