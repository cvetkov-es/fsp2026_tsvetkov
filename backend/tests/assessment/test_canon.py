import timeit

import pytest

from app.assessment.bank.canon import CanonError, canonical


@pytest.mark.parametrize("raw,expected", [
    (" 1,5 ", 1.5), ("1 000", 1000.0), (2, 2.0), ("1234.50", 1234.5), (" 1 500,25", 1500.25),
    ("92,3%", 92.3), ("92.3 %", 92.3),  # знак процента после числа — формат, а не содержание
])
def test_number(raw, expected):
    assert canonical("number", raw) == expected


@pytest.mark.parametrize("raw", ["около пяти", "%", "92,3%%", "%92,3"])
def test_number_garbage_raises(raw):
    with pytest.raises(CanonError):
        canonical("number", raw)


def test_text_trims_and_collapses_spaces_case_sensitive():
    assert canonical("text", "  4  5   7 \r\n") == "4 5 7"
    assert canonical("text", "True") != canonical("text", "true")


def test_order_parses_any_separators():
    assert canonical("order", "3, 1 2-6 4 5") == (3, 1, 2, 6, 4, 5)
    assert canonical("order", [3, 1, 2]) == (3, 1, 2)


def test_rows_multiset_tolerant():
    a = canonical("rows", [["Анна ", "1.0"], ["Борис", None]])
    b = canonical("rows", [["Борис", "NULL"], ["Анна", 1]])
    assert a == b


def test_line_and_choice_ints():
    assert canonical("line", " 6 ") == 6 and canonical("choice", "2") == 2
    with pytest.raises(CanonError):
        canonical("line", "6.5")


@pytest.mark.parametrize("raw,key", [
    ("[25,25,25,25,25,25]", "[25, 25, 25, 25, 25, 25]"),   # список без пробелов
    ("[ 25 , 25 ]", "[25, 25]"),                            # пробелы у скобок и перед запятой
    ("[[1,2],[ 3 ,4]]", "[[1, 2], [3, 4]]"),               # вложенные скобки
    ("(1,2)", "(1, 2)"), ("( 7 , )", "(7,)"),              # кортежи, в том числе из одного элемента
    ("[ ]", "[]"), ("18 0 [ ]", "18 0 []"), ("{1,2}", "{1, 2}"),
    ("7:59:15", "07:59:15"), (" 0:00:05 ", "00:00:05"),    # час без ведущего нуля
])
def test_text_tolerates_list_and_time_format(raw, key):
    assert canonical("text", raw) == canonical("text", key)


@pytest.mark.parametrize("raw,key", [
    ("[25, 25]", "[25, 26]"), ("[25,25]", "[25, 25, 25]"), ("(1, 2)", "[1, 2]"),
    ("07:59:15", "07:59:16"), ("7:59:15", "17:59:15"), ("18 0 []", "18 0 [0]"),
])
def test_text_still_strict_about_content(raw, key):
    assert canonical("text", raw) != canonical("text", key)


def test_text_canon_is_idempotent():
    for raw in ("[25,25]", "( 7 , )", "7:05:09", "a , b", "18 0 [ ]", "x\n[ 1,2 ]"):
        once = canonical("text", raw)
        assert canonical("text", once) == once


WHITESPACE = {"space": " ", "tab": "\t", "nbsp": "\xa0", "emsp": "\u2003", "cr": "\r", "vt": "\v",
              "ff": "\f"}
SHAPES = {"run": lambda w: "a" + w * 9990 + "b", "close": lambda w: "[" + w * 9990 + "]",
          "comma": lambda w: "a" + w * 9990 + ",b", "commas": lambda w: "(" + (w * 3 + ",") * 2400 + ")"}
WORST_TEXT = {f"{wn}-{sn}": shape(ws) for wn, ws in WHITESPACE.items() for sn, shape in SHAPES.items()}
WORST_TEXT |= {"space-comma-list": "[" + " ," * 4999 + "]", "mixed-list": "[" + "\u2003,\xa0" * 3300 + "]"}


@pytest.mark.parametrize("raw", list(WORST_TEXT.values()), ids=list(WORST_TEXT))
def test_text_canon_is_fast_on_long_whitespace_runs(raw):
    """Ответ кандидата до 10 000 знаков канонизируется за линейное время (раньше — секунды)."""
    assert len(raw) <= 10_000
    # минимум из трёх замеров: случайная пауза CI-раннера (GC, соседи) не валит тест, а квадратичный
    # откат (секунды на любом замере) по-прежнему ловится
    best = min(timeit.repeat(lambda: canonical("text", raw), number=1, repeat=3))
    assert best < 0.1


def test_text_treats_any_whitespace_as_space():
    assert canonical("text", "[25,\xa025]") == canonical("text", "[25, 25]")
    assert canonical("text", "4\u20035\r7") == "4 5 7"
