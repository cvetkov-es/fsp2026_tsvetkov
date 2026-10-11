"""Единые часы приложения. В тестах время подменяется через set_now()."""
from datetime import UTC, datetime, timedelta, timezone

# Даты для людей — по Москве (без перехода на летнее время с 2014 года, tzdata не нужна)
MSK = timezone(timedelta(hours=3), "MSK")

_override: datetime | None = None


def now() -> datetime:
    return _override if _override is not None else datetime.now(UTC)


def set_now(value: datetime | None) -> None:
    global _override
    _override = value
