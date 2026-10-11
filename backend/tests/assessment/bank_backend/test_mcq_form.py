"""Форма вариантов во всех MCQ банка Backend: ключ не угадывается по длине, позиции и первому слову."""
import pytest

from app.assessment.bank.base import REGISTRY

from .._bank_helpers import assert_area_mcq_lengths, assert_mcq_form, kind_codes

CHOICE_CODES = kind_codes("backend", "choice")
AREAS = sorted({REGISTRY[c].area for c in CHOICE_CODES})


def test_every_backend_mcq_family_is_covered():
    assert len(CHOICE_CODES) >= 25
    assert {"be.lang.cpu_bound_parallelism", "be.http.method_idempotency", "be.http.breaking_change",
            "be.debug.which_assert_fails", "be.arch.circuit_breaker_state"} <= set(CHOICE_CODES)


@pytest.mark.parametrize("code", CHOICE_CODES)
def test_mcq_form_does_not_reveal_key(code):
    assert_mcq_form(code)


@pytest.mark.parametrize("area", AREAS)
def test_area_mcq_key_not_systematically_longest_or_shortest(area):
    assert_area_mcq_lengths([c for c in CHOICE_CODES if REGISTRY[c].area == area], area)
