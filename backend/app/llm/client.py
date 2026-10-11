"""Единственная точка вызова LLM (техдизайн, решение 9): маршрут → вызов → JSON → Pydantic → один повтор → следующая модель.

Возвращает None, если LLM выключен, недоступен или не справился: фолбэк (правила, шаблон) делает вызывающий.
Маскирование ПДн — обязанность вызывающего (app.llm.masking) до передачи текста сюда.
"""
import json
import logging
from collections.abc import Callable
from typing import TypeVar, get_origin

from pydantic import BaseModel, ConfigDict, ValidationError

from app.config.params import PARAMS
from app.config.settings import Settings
from app.llm.breaker import CircuitBreaker
from app.llm.config import ModelSpec, Task, route
from app.llm.jsonx import extract_json

log = logging.getLogger(__name__)


class LLMOut(BaseModel):
    """База схем ответа: лишние ключи — ошибка, иначе мусор проходит как «пустой» валидный ответ."""
    model_config = ConfigDict(extra="forbid")


T = TypeVar("T", bound=LLMOut)
# (модель, сообщения, response_format, таймаут в секундах) -> текст ответа
Transport = Callable[[str, list[dict], dict, float], str]


def example_of(schema: type[BaseModel]) -> dict:
    return {name: [] if get_origin(f.annotation) is list else None for name, f in schema.model_fields.items()}


def instructions(spec: ModelSpec, schema: type[BaseModel]) -> str:
    if spec.json_mode == "json_schema":
        return "Ответ — только JSON-объект по схеме:\n" + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    # GigaChat на JSON-схему в промпте отвечает её копией с обёрткой «properties» (проверено 08.10) — даём образец
    return ("Ответ — только JSON-объект с ключами как в образце; null и [] замени найденными значениями:\n"
            + json.dumps(example_of(schema), ensure_ascii=False))


def unwrap(data: dict | None, schema: type[BaseModel]) -> dict | None:
    """{"properties": {...}} и подобные единственные обёртки без ключей схемы — разворачиваем."""
    if isinstance(data, dict) and len(data) == 1 and not set(data) & set(schema.model_fields):
        inner = next(iter(data.values()))
        if isinstance(inner, dict):
            return inner
    return data


def response_format(spec: ModelSpec, schema: type[BaseModel]) -> dict:
    if spec.json_mode == "json_schema":
        return {"type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema(), "strict": False}}
    return {"type": "json_object"}


class LLM:
    def __init__(self, transport: Transport | None, settings: Settings, breaker: CircuitBreaker):
        self.transport, self.settings, self.breaker = transport, settings, breaker

    @property
    def enabled(self) -> bool:
        return self.transport is not None

    def json(self, task: Task, system: str, user: str, schema: type[T]) -> tuple[T, str] | None:
        """Ответ как экземпляр schema и имя модели, которая его дала."""
        if self.transport is None:
            return None
        timeout = {"pd": PARAMS.llm_timeout_pd_s, "offline": PARAMS.llm_timeout_offline_s}.get(task, PARAMS.llm_timeout_s)
        for spec in route(task, self.settings):
            if not self.breaker.allow():
                return None
            messages = [{"role": "system", "content": system + "\n\n" + instructions(spec, schema)},
                        {"role": "user", "content": user}]
            for _ in range(2):  # первый ответ и один повтор с текстом ошибки
                try:
                    content = self.transport(spec.name, messages, response_format(spec, schema), timeout)
                except Exception as e:  # сеть, таймаут, 4xx/5xx провайдера — следующая модель
                    log.warning("llm %s: %s", spec.name, type(e).__name__)
                    break
                try:
                    result = schema.model_validate(unwrap(extract_json(content), schema))
                except ValidationError as e:
                    messages = [*messages, {"role": "assistant", "content": content or ""},
                                {"role": "user", "content": f"Ответ не прошёл проверку: {str(e)[:300]}. "
                                                            "Верни исправленный JSON-объект."}]
                    continue
                self.breaker.success()
                return result, spec.name
            self.breaker.failure()
        return None


def openai_transport(s: Settings) -> Transport | None:
    key = s.llm_api_key.get_secret_value() if s.llm_api_key else ""
    if not key or not s.llm_base_url:
        return None
    from openai import OpenAI

    client = OpenAI(base_url=s.llm_base_url, api_key=key, max_retries=0)

    def call(model: str, messages: list[dict], fmt: dict, timeout: float) -> str:
        r = client.chat.completions.create(model=model, messages=messages, response_format=fmt,
                                           temperature=0.2, timeout=timeout)
        return r.choices[0].message.content or ""

    return call
