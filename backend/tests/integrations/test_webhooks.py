import base64
import hashlib
import hmac

import pytest

from app.common.errors import AppError
from app.integrations.webhooks import check_url, headers, new_secret, sign, verify


def test_signature_matches_standard_webhooks():
    secret = "whsec_" + base64.b64encode(b"0123456789abcdef0123456789").decode()
    body = '{"type":"ping"}'
    expected = base64.b64encode(hmac.new(b"0123456789abcdef0123456789", f"msg_1.1700000000.{body}".encode(),
                                         hashlib.sha256).digest()).decode()
    assert sign(secret, "msg_1", 1700000000, body) == f"v1,{expected}"
    h = headers(secret, "msg_1", 1700000000, body)
    assert h["webhook-id"] == "msg_1" and h["webhook-timestamp"] == "1700000000"
    assert new_secret().startswith("whsec_")


def test_new_secrets_are_unique_and_long_enough():
    secrets_ = {new_secret() for _ in range(20)}
    assert len(secrets_) == 20 and all(len(base64.b64decode(s.removeprefix("whsec_"))) >= 24 for s in secrets_)


def test_verify_accepts_a_genuine_signature_and_rejects_tampering_and_old_timestamps():
    secret = new_secret()
    body = '{"type":"contact.sent"}'
    ts = 1700000000
    sig = sign(secret, "msg_9", ts, body)
    assert verify(secret, "msg_9", str(ts), body, sig, now_ts=ts + 10)
    assert verify(secret, "msg_9", str(ts), body, f"v1,AAAA {sig}", now_ts=ts + 10)  # несколько подписей через пробел
    assert not verify(secret, "msg_9", str(ts), body + " ", sig, now_ts=ts + 10)  # тело изменено
    assert not verify(new_secret(), "msg_9", str(ts), body, sig, now_ts=ts + 10)  # чужой секрет
    assert not verify(secret, "msg_9", str(ts), body, sig, now_ts=ts + 6 * 60)  # старше пяти минут — защита от повторов
    assert not verify(secret, "msg_9", "не число", body, sig, now_ts=ts)
    assert not verify(secret, "msg_9", str(ts), body, "", now_ts=ts)


@pytest.mark.parametrize("url", ["http://example.com/hook", "https://127.0.0.1/hook", "https://10.0.0.5/hook",
                                 "https://localhost/hook", "https://[::1]/hook", "https://169.254.169.254/latest/meta-data",
                                 "https://192.168.1.10/hook", "ftp://example.com/x", "https:///nohost"])
def test_ssrf_guard(url):
    with pytest.raises(AppError):
        check_url(url)


@pytest.mark.parametrize("url", ["https://example.com:abc/hook", "https://100.64.0.1/hook", "https://100.127.255.254/hook",
                                 "http://localhost:5173/mock/ats/../../api/v1/x", "http://localhost:5173/mock/ats/x/webhook"])
def test_ssrf_guard_hygiene(url):
    with pytest.raises(AppError):
        check_url(url)


def test_mock_url_must_be_exactly_the_mock_webhook():
    check_url("http://localhost:5173/mock/ats/1772d790-fb81-4ef8-b849-2595423b7cd0/webhook")


def test_url_on_own_origin_is_refused():
    # Публичный origin платформы сервер переписывает на внутренний — обычный вебхук туда не пускаем
    with pytest.raises(AppError):
        check_url("http://localhost:5173/api/v1/health")


def test_verify_survives_non_ascii_signatures():
    assert verify(new_secret(), "m", "1", "{}", "v1,\u00e9\u00e9", now_ts=1) is False
