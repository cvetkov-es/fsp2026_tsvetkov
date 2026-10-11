"""Помощники семантических тестов банков навыков — общие из tests/assessment/_bank_helpers.py."""
from app.assessment.bank.base import REGISTRY

from .._bank_helpers import assert_mcq_form, make

__all__ = ["assert_mcq_form", "make", "skill_codes"]


def skill_codes(code: str) -> list[str]:
    return sorted(c for c, f in REGISTRY.items() if f.specialization == f"skill:{code}")
