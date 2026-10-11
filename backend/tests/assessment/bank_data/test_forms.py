"""Форма ответов во всём банке Data/Analytics: MCQ не выдаёт ключ формой, текстовый ответ терпим к записи."""
import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.canon import is_correct

from .._bank_helpers import (
    assert_area_mcq_lengths,
    assert_mcq_form,
    content_change,
    format_variants,
    kind_codes,
    make,
)

SPEC = "data"
CHOICE_CODES = kind_codes(SPEC, "choice")
TEXT_CODES = kind_codes(SPEC, "text")


@pytest.mark.parametrize("code", CHOICE_CODES)
def test_mcq_form_does_not_reveal_key(code):
    assert_mcq_form(code)


@pytest.mark.parametrize("area", sorted({REGISTRY[c].area for c in CHOICE_CODES}))
def test_area_mcq_key_not_systematically_longest_or_shortest(area):
    assert_area_mcq_lengths([c for c in CHOICE_CODES if REGISTRY[c].area == area], area)


@pytest.mark.parametrize("code", TEXT_CODES)
def test_text_key_accepts_format_variants_and_rejects_content_change(code):
    for seed in range(100):
        inst = make(code, seed)
        for variant in format_variants(inst.answer):
            assert is_correct(inst, variant), (code, inst.answer, variant)
        assert not is_correct(inst, content_change(inst.answer)), (code, inst.answer)



NUMBER_CODES = kind_codes(SPEC, "number")
# числа в тексте этих семейств — константы формулы, а не входы задания (урок 15, явное исключение)
LEAK_EXEMPT = {"da.quality.iqr_outliers": "«(n − 1)·q» и «1.5·IQR» в описании метода квартилей",
               "da.sql.month_group_count": "«substr(created_at, 1, 7)» в пояснении к запросу"}


@pytest.mark.parametrize("code", [c for c in NUMBER_CODES if c not in LEAK_EXEMPT])
def test_number_key_not_named_in_text(code):
    """Урок 15: ключ-число не встречается в тексте задания (совпадения с входами — редкость, не правило)."""
    import re
    hits = 0
    for seed in range(100):
        inst = make(code, seed)
        nums = {float(x.replace(",", ".")) for x in re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?", inst.prompt.text)}
        hits += inst.answer in nums
    assert hits <= 10, (code, hits)
