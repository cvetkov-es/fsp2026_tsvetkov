"""Circuit breaker: после LLM_CB_ERRORS ошибок подряд — шаблоны и правила на LLM_CB_COOLDOWN_MIN минут."""
import threading
from datetime import datetime, timedelta

from app.common.clock import now


class CircuitBreaker:
    def __init__(self, errors: int, cooldown_min: int):
        self.errors, self.cooldown = errors, timedelta(minutes=cooldown_min)
        self.failures = 0
        self.open_until: datetime | None = None
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            return self.open_until is None or now() >= self.open_until

    def success(self) -> None:
        with self._lock:
            self.failures, self.open_until = 0, None

    def failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.errors:
                self.failures, self.open_until = 0, now() + self.cooldown
