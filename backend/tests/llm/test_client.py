from datetime import timedelta

import pytest

from app.common import clock
from app.config.params import PARAMS
from app.config.settings import Settings
from app.llm.client import LLMOut
from app.llm.config import route
from app.llm.jsonx import extract_json
from tests.llm_fakes import fake_llm


class Out(LLMOut):
    title: str
    n: int


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('Вот ответ:\n```json\n{"a": {"b": "}"}}\n```') == {"a": {"b": "}"}}
    assert extract_json('текст {"a": "x \\" {"} хвост') == {"a": 'x " {'}
    assert extract_json("[1, 2]") is None and extract_json("нет json") is None and extract_json(None) is None
    assert extract_json('{битый} и потом {"ok": true}') == {"ok": True}


def test_route_by_profile_and_prod_guard():
    dev = route("pd", Settings(_env_file=None))
    assert [m.name for m in dev] == ["deepseek/deepseek-v4.1-flash"] and dev[0].json_mode == "json_schema"
    prod = route("pd", Settings(_env_file=None, llm_profile="prod"))
    assert [m.name for m in prod] == ["sber/gigachat-2-pro", "yandex/yandexgpt-5.1-pro"]
    assert prod[0].json_mode == "json_object"
    with pytest.raises(ValueError, match="РФ"):
        route("runtime", Settings(_env_file=None, llm_profile="prod", llm_model_runtime="deepseek/deepseek-v4.1-flash"))


def test_offline_route_ignores_prod_guard():
    s = Settings(_env_file=None, llm_profile="prod", llm_model_runtime="google/gemini-3.8-flash")
    assert [m.name for m in route("offline", s)] == ["google/gemini-3.8-flash"]


def test_offline_task_gets_long_timeout():
    """Решатель и судья лаборатории не укладываются в интерфейсные 8 с — у офлайн-задачи свой таймаут."""
    llm, t = fake_llm('{}')
    seen = []
    llm.transport = lambda model, messages, fmt, timeout: seen.append(timeout) or t(model, messages, fmt, timeout)
    assert llm.json("offline", "sys", "user", LLMOut) is not None
    assert seen == [PARAMS.llm_timeout_offline_s]


def test_valid_answer_and_schema_mode():
    llm, t = fake_llm('```json\n{"title": "x", "n": 2}\n```')
    out, model = llm.json("runtime", "сист", "польз", Out)
    assert out == Out(title="x", n=2) and model == "deepseek/deepseek-v4.1-flash"
    assert t.calls[0]["response_format"]["type"] == "json_schema"


def test_one_retry_with_error_hint_then_next_model():
    llm, t = fake_llm('{"title": "x"}', '{"title": "x", "n": 3}')
    assert llm.json("runtime", "с", "п", Out)[0].n == 3
    assert "не прошёл проверку" in t.calls[1]["messages"][-1]["content"]
    llm, t = fake_llm("мусор", "мусор", RuntimeError("down"), profile="prod")
    assert llm.json("pd", "с", "п", Out) is None
    assert [c["model"] for c in t.calls] == ["sber/gigachat-2-pro", "sber/gigachat-2-pro", "yandex/yandexgpt-5.1-pro"]
    assert t.calls[0]["response_format"] == {"type": "json_object"}


def test_gigachat_wrapper_unwrapped_and_extra_keys_rejected():
    llm, t = fake_llm('{"properties": {"title": "x", "n": 1}}', profile="prod")
    assert llm.json("runtime", "с", "п", Out)[0] == Out(title="x", n=1)
    prompt = t.calls[0]["messages"][0]["content"]
    assert '{"title": null, "n": null}' in prompt and "$defs" not in prompt and "properties" not in prompt
    llm, t = fake_llm('{"title": "x", "n": 1, "лишнее": 2}', '{"title": "x", "n": 1}')
    assert llm.json("runtime", "с", "п", Out)[0].n == 1 and len(t.calls) == 2


def test_breaker_opens_after_errors_and_recovers(frozen_now):
    start = clock.now()
    frozen_now(start)
    llm, t = fake_llm(*[TimeoutError()] * 3, '{"title": "ok", "n": 1}')
    for _ in range(3):
        assert llm.json("runtime", "с", "п", Out) is None
    assert llm.json("runtime", "с", "п", Out) is None and len(t.calls) == 3  # открыт: провайдера не трогаем
    frozen_now(start + timedelta(minutes=11))
    assert llm.json("runtime", "с", "п", Out)[0].title == "ok"


def test_disabled_without_key():
    from app.llm.client import LLM, openai_transport
    from app.llm.deps import BREAKER

    s = Settings(_env_file=None, llm_api_key="")
    assert openai_transport(s) is None
    assert LLM(None, s, BREAKER).json("runtime", "с", "п", Out) is None
