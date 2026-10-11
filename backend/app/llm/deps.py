from functools import lru_cache

from app.config.params import PARAMS
from app.config.settings import get_settings
from app.llm.breaker import CircuitBreaker
from app.llm.client import LLM, openai_transport
from app.llm.config import route

# Один breaker на процесс: ошибки любых запросов воркера копятся вместе
BREAKER = CircuitBreaker(PARAMS.llm_cb_errors, PARAMS.llm_cb_cooldown_min)


def validate_llm_config() -> None:
    """Вызывается при старте: в prod модель вне РФ для данных кандидата — ошибка конфигурации."""
    s = get_settings()
    route("pd", s)
    route("runtime", s)


@lru_cache
def get_llm() -> LLM:
    s = get_settings()
    return LLM(openai_transport(s), s, BREAKER)


def disabled_llm() -> LLM:
    return LLM(None, get_settings(), BREAKER)
