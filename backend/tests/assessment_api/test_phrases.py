import pytest

from app.assessment.phrases import result_phrase, ru_plural


@pytest.mark.parametrize("n,word", [(1, "задание"), (2, "задания"), (5, "заданий"), (11, "заданий"),
                                    (21, "задание"), (22, "задания"), (112, "заданий")])
def test_plural(n, word):
    assert ru_plural(n, "задание", "задания", "заданий") == word


def test_phrases():
    assert result_phrase("middle", "confirmed", 8, 10, 3) == \
        "Middle подтверждён · решено 8 из 10, из них 3 задания уровня выше"
    assert result_phrase("senior", "confirmed", 6, 6, 0) == "Senior подтверждён · решено 6 из 6"
    assert result_phrase("junior", "not_confirmed", 2, 6, 0) == "Junior не подтверждён · решено 2 из 6"
