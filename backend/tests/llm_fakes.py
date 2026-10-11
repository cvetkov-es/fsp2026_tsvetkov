"""Подставной транспорт LLM: сценарий ответов и журнал вызовов. Сеть в тестах не используется."""
from app.config.params import PARAMS
from app.config.settings import Settings
from app.llm.breaker import CircuitBreaker
from app.llm.client import LLM


class FakeTransport:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, model, messages, response_format, timeout):
        self.calls.append({"model": model, "messages": messages, "response_format": response_format})
        reply = self.replies.pop(0) if self.replies else "{}"
        if isinstance(reply, Exception):
            raise reply
        return reply

    def sent_text(self) -> str:
        return "\n".join(m["content"] for c in self.calls for m in c["messages"] if m["role"] == "user")


def fake_llm(*replies, profile: str = "dev") -> tuple[LLM, FakeTransport]:
    t = FakeTransport(*replies)
    s = Settings(_env_file=None, llm_profile=profile)
    return LLM(t, s, CircuitBreaker(PARAMS.llm_cb_errors, PARAMS.llm_cb_cooldown_min)), t
