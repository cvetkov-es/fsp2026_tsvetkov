"""Вебхуки по Standard Webhooks: подпись, проверка подписи и защита от SSRF."""
import base64
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import socket
from urllib.parse import urlsplit

from app.common import clock
from app.common.errors import AppError
from app.config.settings import get_settings

MOCK_PATH = re.compile(r"^/mock/ats/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/webhook$")
CGNAT = ipaddress.ip_network("100.64.0.0/10")  # общий адрес оператора: is_private его не покрывает
TOLERANCE_S = 5 * 60  # допустимое расхождение отметки времени — защита от повторной отправки старых сообщений


def new_secret() -> str:
    return "whsec_" + base64.b64encode(secrets.token_bytes(24)).decode()


def sign(secret: str, msg_id: str, timestamp: int, body: str) -> str:
    """Standard Webhooks: v1,base64(HMAC-SHA256(base64decode(secret без whsec_), "id.timestamp.body"))."""
    key = base64.b64decode(secret.removeprefix("whsec_"))
    digest = hmac.new(key, f"{msg_id}.{timestamp}.{body}".encode(), hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def headers(secret: str, msg_id: str, timestamp: int, body: str) -> dict:
    return {"webhook-id": msg_id, "webhook-timestamp": str(timestamp),
            "webhook-signature": sign(secret, msg_id, timestamp, body), "content-type": "application/json"}


def body_of(event_type: str, payload: dict, at: str) -> str:
    return json.dumps({"type": event_type, "timestamp": at, "data": payload}, ensure_ascii=False, separators=(",", ":"))


def verify(secret: str, msg_id: str, timestamp: str, body: str, signature: str, now_ts: int | None = None) -> bool:
    """Проверка приёмной стороны: отметка времени в пределах ±5 минут и одна из подписей (через пробел) совпадает."""
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs((now_ts if now_ts is not None else int(clock.now().timestamp())) - ts) > TOLERANCE_S:
        return False
    expected = sign(secret, msg_id, ts, body)
    return any(hmac.compare_digest(expected.encode(), s.encode()) for s in signature.split())


def check_url(url: str) -> None:
    """Защита от SSRF: адрес не должен вести на сам сервис и во внутреннюю сеть.

    Адрес публичного origin платформы сервер переписывает на внутренний (FSP_SERVER_BASE) и вызывает оттуда.
    Обычный вебхук на этот origin не пускаем, иначе он стал бы запросом во внутреннюю сеть. Исключение —
    встроенный мок ATS: его адрес и создаётся под этот origin.
    """
    s = get_settings()
    u, public = urlsplit(url), urlsplit(s.public_base_url)
    if (u.scheme, u.netloc) == (public.scheme, public.netloc):
        if s.mocks_on and MOCK_PATH.match(u.path):
            return
        raise AppError(422, "webhook_url_private", "Адрес вебхука ведёт на сам сервис")
    if u.scheme != "https" or not u.hostname:
        raise AppError(422, "webhook_url_https", "Адрес вебхука должен начинаться с https://")
    try:
        addrs = {ai[4][0] for ai in socket.getaddrinfo(u.hostname, u.port or 443)}
    except ValueError as e:  # порт не число или вне диапазона
        raise AppError(422, "webhook_url_https", "Некорректный адрес вебхука") from e
    except OSError as e:
        raise AppError(422, "webhook_url_unresolved", "Сервер по адресу вебхука не найден") from e
    for a in addrs:
        ip = ipaddress.ip_address(a.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified or ip in CGNAT:
            raise AppError(422, "webhook_url_private", "Адрес вебхука ведёт во внутреннюю сеть")
