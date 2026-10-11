"""HTTP к FSP ID и API достижений. Браузер ходит по публичным URL, сервер — при FSP_SERVER_BASE на внутренний origin."""
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.config.params import PARAMS
from app.config.settings import Settings, get_settings


def server_url(url: str, settings: Settings | None = None) -> str:
    """На внутренний origin переписываются только адреса встроенного мока (origin = PUBLIC_BASE_URL).

    Настоящий FSP ID (FSP_ID_ISSUER) вызывается по его собственным адресам: переход на Keycloak ФСП — только env.
    """
    s = settings or get_settings()
    u, public = urlsplit(url), urlsplit(s.public_base_url)
    if not s.fsp_server_base or (u.scheme, u.netloc) != (public.scheme, public.netloc):
        return url
    base = urlsplit(s.fsp_server_base)
    return urlunsplit((base.scheme, base.netloc, u.path, u.query, u.fragment))


def get_fsp_http() -> Iterator[httpx.Client]:
    """Зависимость FastAPI; тесты подменяют её клиентом поверх того же приложения."""
    with httpx.Client(timeout=PARAMS.fsp_http_timeout_s) as client:
        yield client
