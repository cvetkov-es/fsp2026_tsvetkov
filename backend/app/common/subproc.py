"""Подпроцессы разбора (PDF, NER, SQL): пределы ресурсов и чистое окружение.

Разбор идёт в отдельном процессе: PDF-бомба или сбой нативной библиотеки не должны съесть память воркера и не
должны передать дочернему процессу доступ к базе, LLM и внешним системам. Поэтому вместе с ограничением памяти
дочерний процесс получает пределы по процессорному времени, размеру файлов и числу процессов, а из окружения
убираются переменные с секретами.
"""
import os
import resource
from collections.abc import Callable

# Секреты и адреса внешних систем: дочернему процессу разбора они не нужны
SECRET_ENV = frozenset({
    "DATABASE_URL", "SECRET_KEY", "POSTGRES_PASSWORD",
    "LLM_API_KEY", "OPENROUTER_API_KEY", "LLM_BASE_URL",
    "DADATA_TOKEN", "FSP_ID_CLIENT_SECRET",
})


def safe_env() -> dict[str, str]:
    """Окружение для подпроцесса без секретов; PATH, HOME, LANG и прочее остаются."""
    return {k: v for k, v in os.environ.items() if k not in SECRET_ENV}


def child_limits(mem_mb: int, cpu_s: int = 120, fsize_mb: int = 1024) -> Callable[[], None]:
    """Пределы дочернего процесса: адресное пространство, процессорное время, размер файла, число процессов."""

    def apply() -> None:  # выполняется в дочернем процессе до exec
        limit = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_mb * 1024 * 1024, fsize_mb * 1024 * 1024))
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))
        except (ValueError, OSError):
            pass  # не во всех средах лимит применим

    return apply
