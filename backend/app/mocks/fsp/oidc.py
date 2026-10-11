"""Мок FSP ID: пути Keycloak realm `fsp` (исследование 04, §3). Только для демо и тестов.

Страница входа — выбор демо-спортсмена или «почта + пароль», с экраном согласия на передачу данных.
"""
import base64
import hashlib
import hmac
import secrets
import time
from datetime import timedelta
from html import escape
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.common.clock import now
from app.config.settings import get_settings
from app.db.session import get_db
from app.mocks.fsp.fixtures import ATHLETES, PASSWORD, by_credentials, by_sub, full_name
from app.mocks.fsp.keys import API_AUDIENCE, bearer_claims, jwks, sign
from app.mocks.fsp.models import MockFspCode

router = APIRouter(prefix="/realms/fsp")
CODE_TTL_S = 60
TOKEN_TTL_S = 300
Field = Annotated[str, Form()]


def _base() -> str:
    return f"{get_settings().fsp_issuer}/protocol/openid-connect"


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    html = (f"<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>{escape(title)}</title>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<style>body{font-family:Montserrat,system-ui,sans-serif;max-width:560px;margin:40px auto;padding:0 16px;"
            "color:#1C1D22}h1{color:#310F53}button{display:block;width:100%;margin:6px 0;padding:10px;"
            "border:2px solid #310F53;border-radius:12px;background:#fff;text-align:left;cursor:pointer}"
            "button.primary{background:#FF0053;border-color:#FF0053;color:#fff;text-align:center}"
            "input{width:100%;padding:8px;margin:4px 0;box-sizing:border-box}"
            ".note{font-size:13px;color:#555}.box{background:#FFD6E4;border-radius:12px;padding:12px}</style>"
            f"</head><body><h1>{escape(title)}</h1>{body}</body></html>")
    return HTMLResponse(html, status_code=status)


def _client_problem(client_id: str, redirect_uri: str) -> str | None:
    s = get_settings()
    if client_id != s.fsp_id_client_id:
        return "Неизвестное приложение (client_id)"
    if redirect_uri != s.fsp_redirect_uri:
        return "Адрес возврата не совпадает с зарегистрированным (redirect_uri)"
    return None


@router.get("/.well-known/openid-configuration")
def discovery() -> dict:
    iss = get_settings().fsp_issuer
    base = _base()
    return {"issuer": iss, "authorization_endpoint": f"{base}/auth", "token_endpoint": f"{base}/token",
            "userinfo_endpoint": f"{base}/userinfo", "jwks_uri": f"{base}/certs",
            "end_session_endpoint": f"{base}/logout", "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"], "code_challenge_methods_supported": ["S256"],
            "id_token_signing_alg_values_supported": ["RS256"], "subject_types_supported": ["public"],
            "scopes_supported": ["openid", "profile", "email", "fsp:achievements.read"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"]}


@router.get("/protocol/openid-connect/auth", response_class=HTMLResponse)
def auth_page(client_id: str = "", redirect_uri: str = "", response_type: str = "", scope: str = "",
              state: str = "", nonce: str = "", code_challenge: str = "", code_challenge_method: str = ""):
    problem = (_client_problem(client_id, redirect_uri)
               or (None if response_type == "code" else "Поддерживается только response_type=code")
               or (None if "openid" in scope.split() else "Нужен scope openid")
               or (None if code_challenge and code_challenge_method == "S256" else "Нужен PKCE S256"))
    if problem:
        return _page("Ошибка запроса", f"<p>{escape(problem)}</p>", 400)
    hidden = "".join(f"<input type='hidden' name='{k}' value='{escape(v, quote=True)}'>" for k, v in (
        ("client_id", client_id), ("redirect_uri", redirect_uri), ("state", state), ("nonce", nonce),
        ("code_challenge", code_challenge), ("scope", scope)))
    personas = "".join(
        f"<button name='sub' value='{a['sub']}'><b>{escape(full_name(a))}</b><br>"
        f"<span class='note'>{escape(a['note'])}</span></button>" for a in ATHLETES)
    body = (
        "<div class='box'><b>Платформа обратного найма ИТ-специалистов</b> просит доступ. FSP ID передаст платформе: "
        "ФИО, адрес почты, результаты соревнований ФСП и разряды. Паспортные данные, полную дату рождения и контакты "
        "сокомандников ФСП не передаёт.</div>"
        f"<form method='post'>{hidden}<p class='note'>Демо: выберите спортсмена, чтобы войти и дать согласие.</p>"
        f"{personas}<button name='deny' value='1'>Отказаться</button></form>"
        f"<form method='post'>{hidden}<p class='note'>Или войдите по почте (пароль демо-спортсменов: «{PASSWORD}»).</p>"
        "<input name='email' type='email' placeholder='Почта'><input name='password' type='password' "
        "placeholder='Пароль'><button class='primary'>Войти и разрешить</button></form>")
    return _page("Вход через FSP ID", body)


@router.post("/protocol/openid-connect/auth")
def auth_submit(client_id: Field = "", redirect_uri: Field = "", state: Field = "", nonce: Field = "",
                code_challenge: Field = "", scope: Field = "", sub: Field = "", email: Field = "",
                password: Field = "", deny: Field = "", db: Session = Depends(get_db)):
    problem = _client_problem(client_id, redirect_uri) or (None if code_challenge else "Нужен PKCE S256")
    if problem:
        return _page("Ошибка запроса", f"<p>{escape(problem)}</p>", 400)
    if deny:
        return RedirectResponse(f"{redirect_uri}?{urlencode({'error': 'access_denied', 'state': state})}", 302)
    athlete = by_sub(sub) if sub else by_credentials(email, password)
    if athlete is None:
        return _page("Вход через FSP ID", "<p>Неверная почта или пароль.</p>", 401)
    code = secrets.token_urlsafe(32)
    db.add(MockFspCode(code=code, subject=athlete["sub"], client_id=client_id, redirect_uri=redirect_uri,
                       nonce=nonce, code_challenge=code_challenge, scope=scope,
                       expires_at=now() + timedelta(seconds=CODE_TTL_S)))
    db.commit()
    return RedirectResponse(f"{redirect_uri}?{urlencode({'code': code, 'state': state})}", 302)


def _error(code: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status)


@router.post("/protocol/openid-connect/token")
def token(request: Request, grant_type: Field = "", code: Field = "", redirect_uri: Field = "",
          code_verifier: Field = "", client_id: Field = "", client_secret: Field = "",
          db: Session = Depends(get_db)) -> JSONResponse:
    s = get_settings()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        client_id, _, client_secret = base64.b64decode(auth[6:]).decode().partition(":")
    if client_id != s.fsp_id_client_id or not hmac.compare_digest(client_secret, s.fsp_id_client_secret):
        return _error("invalid_client", 401)
    if grant_type != "authorization_code":
        return _error("unsupported_grant_type")
    row = db.get(MockFspCode, code)
    if (row is None or row.used_at is not None or row.expires_at <= now() or row.client_id != client_id
            or row.redirect_uri != redirect_uri):
        return _error("invalid_grant")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
    if not hmac.compare_digest(challenge, row.code_challenge):
        return _error("invalid_grant")
    row.used_at = now()
    db.commit()
    a = by_sub(row.subject)
    t = int(time.time())  # реальные часы: PyJWT проверяет exp по ним
    iss = s.fsp_issuer
    id_token = sign(db, {"iss": iss, "sub": a["sub"], "aud": client_id, "iat": t, "exp": t + TOKEN_TTL_S,
                         "nonce": row.nonce, "email": a["email"], "email_verified": True, "name": full_name(a),
                         "given_name": a["given_name"], "family_name": a["family_name"],
                         "preferred_username": a["email"]})
    access = sign(db, {"iss": iss, "sub": a["sub"], "aud": API_AUDIENCE, "azp": client_id, "iat": t,
                       "exp": t + TOKEN_TTL_S, "scope": row.scope})
    return JSONResponse({"access_token": access, "id_token": id_token, "token_type": "Bearer",
                         "expires_in": TOKEN_TTL_S, "scope": row.scope}, headers={"Cache-Control": "no-store"})


@router.get("/protocol/openid-connect/certs")
def certs(db: Session = Depends(get_db)) -> dict:
    return jwks(db)


@router.get("/protocol/openid-connect/userinfo")
def userinfo(authorization: Annotated[str, Header()] = "", db: Session = Depends(get_db)) -> dict:
    a = by_sub(bearer_claims(db, authorization)["sub"])
    return {"sub": a["sub"], "email": a["email"], "email_verified": True, "name": full_name(a),
            "given_name": a["given_name"], "family_name": a["family_name"]}


def purge_codes(db: Session, t) -> int:
    """Worker: коды авторизации живут CODE_TTL_S; истёкшие не нужны ни для обмена, ни для разбора."""
    return db.execute(delete(MockFspCode).where(MockFspCode.expires_at < t)).rowcount
