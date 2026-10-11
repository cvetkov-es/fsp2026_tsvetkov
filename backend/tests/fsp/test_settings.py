import pytest

from app.config.settings import Settings, validate_secrets
from app.fsp.http import server_url


def test_builtin_mock_urls_follow_public_base_url():
    s = Settings(_env_file=None, public_base_url="http://localhost:8080/", demo_mode=True, fsp_id_issuer=None,
                 fsp_api_url=None, mocks_enabled=None)
    assert s.fsp_issuer == "http://localhost:8080/mock/fsp/realms/fsp"
    assert s.fsp_achievements_url == "http://localhost:8080/mock/fsp/api/v1"
    assert s.fsp_redirect_uri == "http://localhost:8080/api/v1/auth/fsp/callback"
    assert s.mocks_on
    assert not Settings(_env_file=None, demo_mode=False, mocks_enabled=None).mocks_on


def test_server_side_rewrite_only_for_builtin_mock():
    s = Settings(_env_file=None, public_base_url="http://localhost:8080", fsp_server_base="http://api:8000")
    assert (server_url("http://localhost:8080/mock/fsp/realms/fsp/protocol/openid-connect/token?a=1", s)
            == "http://api:8000/mock/fsp/realms/fsp/protocol/openid-connect/token?a=1")
    real = Settings(_env_file=None, public_base_url="http://localhost:8080", fsp_server_base="http://api:8000",
                    fsp_id_issuer="https://id.fsp-russia.ru/realms/fsp")
    assert real.fsp_issuer == "https://id.fsp-russia.ru/realms/fsp"
    token = "https://id.fsp-russia.ru/realms/fsp/protocol/openid-connect/token"
    assert server_url(token, real) == token  # настоящий Keycloak — по его адресу, только env
    assert server_url("http://x.example/y", Settings(_env_file=None, fsp_server_base=None)) == "http://x.example/y"


def test_default_secret_is_refused_outside_demo(monkeypatch):
    from app.config import settings as cfg

    # В боевом режиме значение по умолчанию оставлять нельзя: от него зависит выбор заданий
    monkeypatch.setattr(cfg, "get_settings", lambda: Settings(_env_file=None, demo_mode=False))
    with pytest.raises(RuntimeError):
        validate_secrets()
    monkeypatch.setattr(cfg, "get_settings", lambda: Settings(_env_file=None, demo_mode=False, secret_key="s3cr3t-random"))
    validate_secrets()  # со своим секретом старт разрешён
    monkeypatch.setattr(cfg, "get_settings", lambda: Settings(_env_file=None, demo_mode=True))
    validate_secrets()  # в демо значение по умолчанию допустимо
