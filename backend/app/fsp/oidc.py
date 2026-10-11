"""Клиент FSP ID (OIDC Authorization Code + PKCE S256): discovery, state и nonce, проверка ID token по JWKS.

Переход с мока на настоящий Keycloak ФСП — только env: FSP_ID_ISSUER, FSP_ID_CLIENT_ID, FSP_ID_CLIENT_SECRET.
"""
import base64
import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from sqlalchemy.orm import Session

from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.fsp.http import server_url
from app.fsp.models import OidcState

SCOPE = "openid profile email fsp:achievements.read"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def discovery(http: httpx.Client) -> dict:
    s = get_settings()
    try:
        r = http.get(server_url(f"{s.fsp_issuer}/.well-known/openid-configuration"))
        r.raise_for_status()
        d = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise AppError(502, "fsp_unavailable", "FSP ID сейчас недоступен. Попробуйте позже") from e
    if d.get("issuer") != s.fsp_issuer:
        raise AppError(502, "fsp_unavailable", "FSP ID вернул чужой issuer")
    return d


def start(db: Session, http: httpx.Client, purpose: str, user_id: uuid.UUID | None) -> tuple[str, str]:
    s = get_settings()
    endpoint = discovery(http)["authorization_endpoint"]
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(16), secrets.token_urlsafe(48)
    db.add(OidcState(state=state, nonce=nonce, code_verifier=verifier, purpose=purpose, user_id=user_id))
    db.commit()
    query = {"response_type": "code", "client_id": s.fsp_id_client_id, "redirect_uri": s.fsp_redirect_uri,
             "scope": SCOPE, "state": state, "nonce": nonce,
             "code_challenge": _b64(hashlib.sha256(verifier.encode()).digest()), "code_challenge_method": "S256"}
    return f"{endpoint}?{urlencode(query)}", state


def consume_state(db: Session, state: str, cookie_state: str | None) -> OidcState:
    """state одноразовый, живёт OIDC_TTL_MIN и должен совпасть с cookie этого браузера (защита от login CSRF)."""
    st = db.get(OidcState, state)
    fresh = st is not None and st.created_at >= now() - timedelta(minutes=PARAMS.oidc_ttl_min)
    if not fresh or st.used_at is not None or not cookie_state or not secrets.compare_digest(cookie_state, state):
        raise AppError(400, "fsp_state_invalid", "Вход через FSP ID устарел. Начните заново")
    st.used_at = now()
    db.commit()
    return st


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str | None
    email_verified: bool
    name: str | None
    access_token: str


def verify_id_token(http: httpx.Client, d: dict, token: str, nonce: str) -> dict:
    s = get_settings()
    try:
        r = http.get(server_url(d["jwks_uri"]))
        r.raise_for_status()
        keys = r.json()["keys"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        raise AppError(502, "fsp_unavailable", "FSP ID не отдал ключи подписи") from e
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        jwk = next(k for k in keys if k.get("kid") == kid)
        claims = jwt.decode(token, RSAAlgorithm.from_jwk(json.dumps(jwk)), algorithms=["RS256"],
                            audience=s.fsp_id_client_id, issuer=s.fsp_issuer,
                            options={"require": ["exp", "iat", "sub"]})
    except (jwt.PyJWTError, StopIteration, KeyError, ValueError, httpx.HTTPError) as e:
        raise AppError(401, "fsp_token_invalid", "Ответ FSP ID не прошёл проверку") from e
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise AppError(401, "fsp_token_invalid", "nonce ID token не совпал")
    return claims


def exchange(http: httpx.Client, code: str, st: OidcState) -> Identity:
    s = get_settings()
    d = discovery(http)
    try:
        r = http.post(server_url(d["token_endpoint"]), data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": s.fsp_redirect_uri,
            "code_verifier": st.code_verifier, "client_id": s.fsp_id_client_id,
            "client_secret": s.fsp_id_client_secret})
    except httpx.HTTPError as e:
        raise AppError(502, "fsp_unavailable", "FSP ID сейчас недоступен. Попробуйте позже") from e
    if r.status_code != 200:
        raise AppError(401, "fsp_code_rejected", "FSP ID не принял код входа. Попробуйте ещё раз")
    tokens = r.json()
    claims = verify_id_token(http, d, tokens.get("id_token", ""), st.nonce)
    return Identity(subject=str(claims["sub"]), email=claims.get("email"),
                    email_verified=bool(claims.get("email_verified")), name=claims.get("name"),
                    access_token=str(tokens.get("access_token", "")))
