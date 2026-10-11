"""Правила юниорского трека (процесс 2.10): возраст, несовершеннолетие, часы по ст. 92 ТК РФ. Чистые функции без БД."""
from datetime import date

from app.config.params import PARAMS


def age_of(birth_date: date | None, birth_year: int | None, today: date) -> int | None:
    """Точный возраст по дате рождения; без неё — по году (консервативно: младший из возможных возрастов)."""
    if birth_date:
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return today.year - birth_year - 1 if birth_year else None


def is_minor_age(age_years: int | None) -> bool:
    return age_years is not None and age_years < PARAMS.adult_age


def hours_limit(age_years: int, employment: str) -> int:
    """Ст. 92 ТК РФ: в каникулы — 24 ч (14–15 лет) или 35 ч (16–17); в учебный год (стажировка) — половина."""
    base = PARAMS.minor_hours_week[0] if age_years < 16 else PARAMS.minor_hours_week[1]
    return int(base * (1 if employment == "vacation" else PARAMS.minor_school_factor))


def minor_hours_limit(birth_date: date | None, birth_year: int | None, employment: str, today: date) -> int | None:
    """Лимит часов в неделю для несовершеннолетнего; для взрослого и при неизвестном возрасте — None."""
    a = age_of(birth_date, birth_year, today)
    return hours_limit(a, employment) if a is not None and is_minor_age(a) else None
