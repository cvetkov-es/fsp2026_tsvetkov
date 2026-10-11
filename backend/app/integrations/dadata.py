"""DaData findById/party: без DADATA_URL — встроенный мок (как FSP ID), сервер ходит на внутренний origin."""
import httpx

from app.common.errors import AppError
from app.config.settings import get_settings
from app.fsp.http import server_url

MOCK_PATH = "/mock/dadata/suggestions/api/4_1/rs/findById/party"


def find_party(http: httpx.Client, inn: str) -> dict | None:
    s = get_settings()
    url = s.dadata_url or f"{s.public_base_url.rstrip('/')}{MOCK_PATH}"
    headers = {"Authorization": f"Token {s.dadata_token.get_secret_value()}"} if s.dadata_token else {}
    try:
        r = http.post(server_url(url, s), json={"query": inn}, headers=headers)
        r.raise_for_status()
        suggestions = r.json().get("suggestions") or []
        party = suggestions[0] if suggestions else None
        if party is not None:  # форма ответа, на которую опирается проверка: сбой формата — это сбой сервиса, а не 500
            party["value"], party["data"]["state"]["status"]  # noqa: B018
    except (httpx.HTTPError, ValueError, AttributeError, KeyError, TypeError, IndexError) as e:
        raise AppError(503, "dadata_unavailable", "Проверка ИНН сейчас недоступна, попробуйте позже") from e
    return party
