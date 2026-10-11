import time
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.models import Consent, ExternalIdentity, Role, User
from app.candidates.models import CandidateProfile
from app.common import clock
from app.common.errors import AppError
from app.config.settings import get_settings
from app.fsp import accounts, oidc
from app.fsp.http import get_fsp_http
from app.fsp.models import FspResult, OidcPending
from app.matching.scoring import fsp_f
from app.mocks.fsp.keys import sign
from tests.candidates.test_profile import login
from tests.fsp.helpers import SUB

CONSENTS = {"processing": True, "distribution_preset": "standard"}


@pytest.fixture
def fsp_http(client):
    """Серверные вызовы бэкенда к встроенному моку — в то же приложение; в бою это HTTP."""
    http = TestClient(client.app)
    client.app.dependency_overrides[get_fsp_http] = lambda: http
    return http


def go_through_fsp(client, sub: str, purpose: str = "login"):
    """Браузер: старт → страница FSP ID (выбор спортсмена) → возврат на callback."""
    r = client.get("/api/v1/auth/fsp/start", params={"purpose": purpose}, follow_redirects=False)
    assert r.status_code == 302, r.text
    auth = urlparse(r.headers["location"])
    q = {k: v[0] for k, v in parse_qs(auth.query).items()}
    form = {k: q[k] for k in ("client_id", "redirect_uri", "state", "nonce", "code_challenge", "scope")}
    r = client.post(auth.path, data={**form, "sub": sub}, follow_redirects=False)
    cb = urlparse(r.headers["location"])
    return f"{cb.path}?{cb.query}"


def callback(client, url: str):
    return client.get(url, follow_redirects=False)


def ticket_of(response) -> str:
    assert response.status_code == 302 and response.headers["location"].startswith("/fsp/finish?ticket=")
    return parse_qs(urlparse(response.headers["location"]).query)["ticket"][0]


def complete(client, ticket: str, **kw):
    return client.post("/api/v1/auth/fsp/complete",
                       json={"ticket": ticket, "birth_date": "2000-05-01", "consents": CONSENTS, **kw})


def test_new_athlete_creates_account_with_consents_and_achievements(client, db, fsp_http):
    ticket = ticket_of(callback(client, go_through_fsp(client, SUB["Кузнецова"])))
    assert client.get(f"/api/v1/auth/fsp/pending/{ticket}").json() == {
        "email": "athlete1@athletes.fsp-mock.example", "name": "Анна Кузнецова"}
    assert complete(client, ticket, consents={"processing": True, "distribution_preset": None}).status_code == 422
    r = complete(client, ticket)
    assert r.status_code == 200 and r.json()["role"] == "candidate"
    assert client.get("/api/v1/auth/me").json()["email"] == "athlete1@athletes.fsp-mock.example"
    user = db.scalar(select(User).where(User.email == "athlete1@athletes.fsp-mock.example"))
    assert user.email_verified_at is not None and user.password_hash is None and user.birth_year == 2000
    assert {c.type for c in db.scalars(select(Consent).where(Consent.user_id == user.id))} == {"processing", "distribution"}
    p = db.get(CandidateProfile, user.id)
    assert p.fsp_status == "LINKED" and p.fsp_f == pytest.approx(fsp_f(4.3)) and p.full_name == "Анна Кузнецова"
    assert complete(client, ticket).json()["code"] == "fsp_ticket_invalid"  # билет одноразовый


def test_returning_athlete_logs_in_directly(client, db, fsp_http):
    complete(client, ticket_of(callback(client, go_through_fsp(client, SUB["Демидов"]))))
    client.cookies.clear()
    r = callback(client, go_through_fsp(client, SUB["Демидов"]))
    assert r.status_code == 302 and r.headers["location"] == "/" and "fsp_session" in r.cookies
    assert client.get("/api/v1/auth/me").json()["role"] == "candidate"


def test_no_auto_link_by_email(client, db, fsp_http):
    db.add(User(email="athlete1@athletes.fsp-mock.example", role=Role.candidate, password_hash="x",
                email_verified_at=clock.now()))
    db.commit()
    r = complete(client, ticket_of(callback(client, go_through_fsp(client, SUB["Кузнецова"]))))
    assert r.status_code == 409 and r.json()["code"] == "email_taken_link"
    assert db.scalar(select(ExternalIdentity)) is None


def test_link_from_profile_and_conflict(client, db, fsp_http):
    first = login(client, db, email="first@x.ru")
    r = callback(client, go_through_fsp(client, SUB["Орлов"], purpose="link"))
    assert r.headers["location"] == "/candidate/profile?fsp=linked"
    assert db.scalar(select(ExternalIdentity.user_id).where(ExternalIdentity.subject == SUB["Орлов"])) == first.id
    assert db.get(CandidateProfile, first.id).fsp_status == "LINKED"
    login(client, db, email="second@x.ru")
    r = callback(client, go_through_fsp(client, SUB["Орлов"], purpose="link"))
    assert r.headers["location"] == "/candidate/profile?fsp_error=fsp_already_linked"


def test_state_is_single_use_and_bound_to_browser(client, db, fsp_http):
    url = go_through_fsp(client, SUB["Демидов"])
    stranger = TestClient(client.app)  # чужой браузер без cookie fsp_oidc: login CSRF
    r = stranger.get(url, follow_redirects=False)
    assert r.headers["location"] == "/login?fsp_error=fsp_state_invalid"
    assert callback(client, url).status_code == 302
    assert callback(client, url).headers["location"] == "/login?fsp_error=fsp_state_invalid"  # повтор


def test_deny_and_missing_params(client, db, fsp_http):
    assert callback(client, "/api/v1/auth/fsp/callback?error=access_denied&state=x").headers["location"] == \
        "/login?fsp_error=access_denied"
    assert callback(client, "/api/v1/auth/fsp/callback").headers["location"] == "/login?fsp_error=invalid_request"
    r = client.get("/api/v1/auth/fsp/start", params={"purpose": "link"}, follow_redirects=False)
    assert r.headers["location"] == "/login?fsp_error=login_required"


def test_forged_id_token_rejected(client, db, fsp_http):
    s = get_settings()
    d = oidc.discovery(fsp_http)
    t = int(time.time())
    claims = {"iss": s.fsp_issuer, "sub": "x", "aud": s.fsp_id_client_id, "iat": t, "exp": t + 60, "nonce": "n"}
    forged = jwt.encode(claims, rsa.generate_private_key(public_exponent=65537, key_size=2048), algorithm="RS256",
                        headers={"kid": "fsp-mock-1"})
    with pytest.raises(AppError) as e:
        oidc.verify_id_token(fsp_http, d, forged, "n")
    assert e.value.code == "fsp_token_invalid"


def test_ticket_token_is_cleared_after_use(client, db, fsp_http):
    ticket = ticket_of(callback(client, go_through_fsp(client, SUB["Демидов"])))
    assert complete(client, ticket).status_code == 200
    assert db.get(OidcPending, ticket).access_token is None  # короткоживущий токен не лежит в БД после входа


def test_unlink_keeps_fsp_login_for_passwordless_account(client, db, fsp_http):
    complete(client, ticket_of(callback(client, go_through_fsp(client, SUB["Демидов"]))))
    assert client.delete("/api/v1/candidate/fsp").status_code == 204
    v = client.get("/api/v1/candidate/fsp").json()
    assert v["status"] == "CONSENT_REVOKED" and v["results"] == [] and v["login_via_fsp"] is True
    client.cookies.clear()
    r = callback(client, go_through_fsp(client, SUB["Демидов"]))
    assert r.headers["location"] == "/"  # FSP ID — единственный способ входа, он остаётся
    user = db.scalar(select(User).where(User.email == "athlete8@athletes.fsp-mock.example"))
    p = db.get(CandidateProfile, user.id)
    assert (p.fsp_status, p.fsp_f) == ("CONSENT_REVOKED", 0.0)  # вход не возвращает удалённые данные
    assert db.scalar(select(FspResult).where(FspResult.user_id == user.id)) is None
    r = callback(client, go_through_fsp(client, SUB["Демидов"], purpose="link"))
    assert r.headers["location"] == "/candidate/profile?fsp=linked"
    db.refresh(p)
    assert p.fsp_status == "LINKED"


def test_unexpected_error_in_callback_redirects(client, db, fsp_http, monkeypatch):
    complete(client, ticket_of(callback(client, go_through_fsp(client, SUB["Демидов"]))))
    client.cookies.clear()

    def boom(*a, **kw):
        raise RuntimeError("сбой")

    monkeypatch.setattr("app.fsp.router.sync", boom)
    assert callback(client, go_through_fsp(client, SUB["Демидов"])).headers["location"] == "/login?fsp_error=internal"


def test_link_callback_requires_same_session_user(client, db, fsp_http):
    login(client, db, email="first@x.ru")
    url = go_through_fsp(client, SUB["Орлов"], purpose="link")
    login(client, db, email="second@x.ru")  # за 10 минут в браузере сменился пользователь
    assert callback(client, url).headers["location"] == "/login?fsp_error=login_required"
    assert db.scalar(select(ExternalIdentity)) is None


def test_pending_rejects_unverified_email_up_front(client, db):
    ticket = accounts.create_pending(db, oidc.Identity("sub-x", "x@y.ru", False, "Икс", "tok"))
    r = client.get(f"/api/v1/auth/fsp/pending/{ticket}")
    assert r.status_code == 422 and r.json()["code"] == "fsp_email_unverified"


def test_wrong_aud_or_nonce_rejected_even_with_valid_signature(client, db, fsp_http):
    s = get_settings()
    d = oidc.discovery(fsp_http)
    t = int(time.time())
    base = {"iss": s.fsp_issuer, "sub": "x", "aud": s.fsp_id_client_id, "iat": t, "exp": t + 60, "nonce": "n"}
    for claims, nonce in (({**base, "aud": "other-client"}, "n"), (base, "other-nonce")):
        with pytest.raises(AppError) as e:
            oidc.verify_id_token(fsp_http, d, sign(db, claims), nonce)
        assert e.value.code == "fsp_token_invalid"


class _Down:
    def get(self, url, headers=None):
        return httpx.Response(503, text="<html>down</html>", request=httpx.Request("GET", url))


def test_jwks_failure_is_unavailable_not_invalid_token():
    token = jwt.encode({"sub": "x"}, rsa.generate_private_key(public_exponent=65537, key_size=2048),
                       algorithm="RS256", headers={"kid": "k"})
    with pytest.raises(AppError) as e:
        oidc.verify_id_token(_Down(), {"jwks_uri": "http://fsp.example/certs"}, token, "n")
    assert e.value.code == "fsp_unavailable"
