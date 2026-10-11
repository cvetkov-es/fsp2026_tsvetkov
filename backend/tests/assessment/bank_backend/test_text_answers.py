"""Текстовые ответы банка Backend: формат записи (пробелы в списке, час без нуля) не влияет на зачёт."""
import re

import pytest

from app.assessment.bank.canon import is_correct

from .._bank_helpers import content_change, format_variants, kind_codes, make

TEXT_CODES = kind_codes("backend", "text")


def test_text_families_are_known():
    assert {"be.lang.closure_late_binding_output", "be.lang.mutable_default_output",
            "be.lang.generator_exhaustion_output", "be.arch.ttl_expiry"} <= set(TEXT_CODES)


@pytest.mark.parametrize("code", TEXT_CODES)
def test_text_key_accepts_format_variants_and_rejects_content_change(code):
    for seed in range(100):
        inst = make(code, seed)
        for variant in format_variants(inst.answer):
            assert is_correct(inst, variant), (code, inst.answer, variant)
        assert not is_correct(inst, content_change(inst.answer)), (code, inst.answer)


@pytest.mark.parametrize("code", ["be.lang.closure_late_binding_output", "be.lang.mutable_default_output",
                                  "be.lang.generator_exhaustion_output"])
def test_list_output_hint_shows_list_format(code):
    hints = {make(code, s).prompt.answer_hint for s in range(30)}
    assert len(hints) == 1 and "[1, 2" in hints.pop()


def test_ttl_hint_shows_zero_padded_example():
    hint = make("be.arch.ttl_expiry", 0).prompt.answer_hint
    assert "ЧЧ:ММ:СС" in hint and re.search(r"например 0\d:\d\d:\d\d", hint)
