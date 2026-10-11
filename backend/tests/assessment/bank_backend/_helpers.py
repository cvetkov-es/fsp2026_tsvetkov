"""Помощники семантических тестов банка Backend — общие из tests/assessment/_bank_helpers.py."""
from .._bank_helpers import area_codes as _area_codes
from .._bank_helpers import make, row_for, template_regex

__all__ = ["area_codes", "make", "row_for", "template_regex"]


def area_codes(area: str) -> list[str]:
    return _area_codes(area, "backend")
