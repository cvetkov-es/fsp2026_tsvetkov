"""Маршрут моделей по задаче и профилю (техдизайн v2, §1 и §9)."""
from dataclasses import dataclass
from typing import Literal

from app.config.settings import Settings

Task = Literal["pd", "runtime", "offline"]  # pd — резюме; runtime — вакансия и объяснения; offline — лаборатория
JsonMode = Literal["json_schema", "json_object"]

# Режим JSON проверен пробными запросами 07.10 и 08.10: DeepSeek держит схему, GigaChat — только json_object
JSON_MODES: dict[str, JsonMode] = {
    "deepseek/deepseek-v4.1-flash": "json_schema",
    "google/gemini-3.8-flash": "json_schema",
    "sber/gigachat-2-pro": "json_object",
    "yandex/yandexgpt-5.1-pro": "json_object",
}
ROUTES: dict[str, dict[str, tuple[str, ...]]] = {
    "dev": {"pd": ("deepseek/deepseek-v4.1-flash",), "runtime": ("deepseek/deepseek-v4.1-flash",)},
    "prod": {"pd": ("sber/gigachat-2-pro", "yandex/yandexgpt-5.1-pro"),
             "runtime": ("sber/gigachat-2-pro", "yandex/yandexgpt-5.1-pro")},
}
# На стенде данные кандидата (резюме, объяснения) уходят только в модели с хранением в РФ
RU_RESIDENT = frozenset({"sber/gigachat-2-pro", "yandex/yandexgpt-5.1-pro"})


@dataclass(frozen=True)
class ModelSpec:
    name: str
    json_mode: JsonMode


def route(task: Task, s: Settings) -> list[ModelSpec]:
    if task == "offline":  # только синтетика без ПДн: одна заданная модель, ограничение профиля prod не нужно
        name = s.llm_model_runtime or ROUTES["dev"]["runtime"][0]
        return [ModelSpec(name, JSON_MODES.get(name, "json_object"))]
    names = list(ROUTES[s.llm_profile][task])
    override = s.llm_model_pd if task == "pd" else s.llm_model_runtime
    if override:
        names[0] = override
    if task == "pd" and s.llm_model_pd_fallback:
        names[1:] = [s.llm_model_pd_fallback]
    names = list(dict.fromkeys(names))
    if s.llm_profile == "prod" and (bad := [n for n in names if n not in RU_RESIDENT]):
        raise ValueError(f"LLM_PROFILE=prod: данные кандидата допустимы только в моделях с хранением в РФ, а не {bad}")
    return [ModelSpec(n, JSON_MODES.get(n, "json_object")) for n in names]
