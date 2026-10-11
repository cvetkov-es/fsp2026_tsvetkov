import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family

from ._helpers import assert_clarify, assert_verdict_form, codes

RIGHT = {
    "ai.clarify.top_k_duplicates": "Считать ли повторяющиеся значения отдельно (например, 9 и 9 — два места)?",
    "ai.clarify.round_half": "Как округлять ровно половину рубля (например, 2,50 ₽)?",
    "ai.clarify.active_last_month": "Последний месяц — это 30 дней или календарный месяц?",
    "ai.clarify.revenue_month": "Относить заказ к месяцу по дате создания или по дате оплаты?",
    "ai.clarify.same_email": "Считать ли адреса с разным регистром (Anna@x.ru и anna@x.ru) одним адресом?",
    "ai.clarify.age_leap_day": ("Когда исполняется год у родившихся 29 февраля в невисокосный год — 28 февраля "
                                "или 1 марта?"),
}


def test_clarify_bank_volume():
    assert codes("clarify") == sorted(RIGHT)


@pytest.mark.parametrize("code", codes("clarify"))
def test_clarify_verdicts_have_the_verdict_form(code):
    assert_verdict_form(code)


@pytest.mark.parametrize("code", codes("clarify"))
def test_clarify_verdicts_pass_the_bank_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)


@pytest.mark.parametrize("code", sorted(RIGHT))
def test_the_real_question_is_the_declared_one(code):
    assert_clarify(code, RIGHT[code])
