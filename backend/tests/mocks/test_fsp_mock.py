import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlparse

import jwt
from jwt.algorithms import RSAAlgorithm

from app.config.settings import get_settings
from app.mocks.fsp.fixtures import ATHLETES

BASE = "/mock/fsp/realms/fsp/protocol/openid-connect"
SCOPE = "openid profile email fsp:achievements.read"


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    return verifier, base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def authorize(client, challenge: str, **kw):
    s = get_settings()
    form = {"client_id": s.fsp_id_client_id, "redirect_uri": s.fsp_redirect_uri, "state": "s-1", "nonce": "n-1",
            "code_challenge": challenge, "scope": SCOPE, "sub": ATHLETES[0]["sub"], **kw}
    return client.post(f"{BASE}/auth", data=form, follow_redirects=False)


def exchange(client, code: str, verifier: str, **kw):
    s = get_settings()
    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": s.fsp_redirect_uri,
            "code_verifier": verifier, "client_id": s.fsp_id_client_id, "client_secret": s.fsp_id_client_secret, **kw}
    return client.post(f"{BASE}/token", data=form)


def code_of(response) -> str:
    return parse_qs(urlparse(response.headers["location"]).query)["code"][0]


def test_discovery_uses_public_issuer(client):
    d = client.get("/mock/fsp/realms/fsp/.well-known/openid-configuration").json()
    assert d["issuer"] == get_settings().fsp_issuer and d["token_endpoint"] == f"{d['issuer']}/protocol/openid-connect/token"
    assert d["code_challenge_methods_supported"] == ["S256"]


def test_auth_page_lists_personas_and_rejects_foreign_redirect(client):
    s = get_settings()
    q = {"client_id": s.fsp_id_client_id, "redirect_uri": s.fsp_redirect_uri, "response_type": "code", "scope": SCOPE,
         "state": "x", "nonce": "y", "code_challenge": "c", "code_challenge_method": "S256"}
    ok = client.get(f"{BASE}/auth", params=q)
    assert ok.status_code == 200 and "Анна Кузнецова" in ok.text and "передаст платформе" in ok.text
    assert client.get(f"{BASE}/auth", params={**q, "redirect_uri": "https://evil.example/cb"}).status_code == 400
    assert client.get(f"{BASE}/auth", params={**q, "code_challenge_method": "plain"}).status_code == 400


def test_code_flow_with_pkce_issues_verifiable_single_use_tokens(client):
    s = get_settings()
    verifier, challenge = pkce()
    r = authorize(client, challenge)
    assert r.status_code == 302 and parse_qs(urlparse(r.headers["location"]).query)["state"] == ["s-1"]
    code = code_of(r)
    tokens = exchange(client, code, verifier).json()
    jwk = client.get(f"{BASE}/certs").json()["keys"][0]
    claims = jwt.decode(tokens["id_token"], RSAAlgorithm.from_jwk(json.dumps(jwk)), algorithms=["RS256"],
                        audience=s.fsp_id_client_id, issuer=s.fsp_issuer)
    assert claims["sub"] == ATHLETES[0]["sub"] and claims["nonce"] == "n-1" and claims["email_verified"] is True
    assert claims["name"] == "Анна Кузнецова" and "results" not in claims  # достижения не в токене
    assert exchange(client, code, verifier).json()["error"] == "invalid_grant"  # код одноразовый
    info = client.get(f"{BASE}/userinfo", headers={"Authorization": f"Bearer {tokens['access_token']}"}).json()
    assert info["email"] == ATHLETES[0]["email"]


def test_wrong_verifier_secret_and_password_rejected(client):
    verifier, challenge = pkce()
    assert exchange(client, code_of(authorize(client, challenge)), "чужой-verifier").json()["error"] == "invalid_grant"
    assert exchange(client, code_of(authorize(client, challenge)), verifier, client_secret="x").status_code == 401
    r = authorize(client, challenge, sub="", email=ATHLETES[0]["email"], password="не тот")
    assert r.status_code == 401


def test_deny_redirects_with_access_denied(client):
    r = authorize(client, pkce()[1], deny="1")
    assert parse_qs(urlparse(r.headers["location"]).query) == {"error": ["access_denied"], "state": ["s-1"]}


def test_achievements_need_token_and_scope(client):
    url = "/mock/fsp/api/v1/athletes/me/achievements"
    assert client.get(url).status_code == 401
    verifier, challenge = pkce()
    token = exchange(client, code_of(authorize(client, challenge)), verifier).json()["access_token"]
    r = client.get(url, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.headers["etag"]
    assert r.json()["athlete"]["sub"] == ATHLETES[0]["sub"] and len(r.json()["results"]) == 3
    narrow = exchange(client, code_of(authorize(client, challenge, scope="openid")), verifier).json()["access_token"]
    assert client.get(url, headers={"Authorization": f"Bearer {narrow}"}).status_code == 403
