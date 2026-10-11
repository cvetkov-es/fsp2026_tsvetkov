import math
import random
import re
import statistics
from collections import Counter

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family

from ._helpers import assert_python_oracle, assert_verdict_form, codes


def test_python_bank_volume():
    assert len(codes("python")) == 14


@pytest.mark.parametrize("code", codes("python"))
def test_python_verdicts_have_the_verdict_form(code):
    assert_verdict_form(code)


@pytest.mark.parametrize("code", codes("python"))
def test_python_verdicts_pass_the_bank_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)


def _num(text: str, pattern: str) -> int:
    return int(re.search(pattern, text).group(1))


def _lists(p: dict, rng: random.Random) -> list:
    t = p["t"]
    pool = [None, 0, t - 1, t, t + 1, -t - 3, 2 * t + 5]
    return [[], [None], [t], [t + 1, t + 1], [-(t + 5), t + 1]] + [rng.choices(pool, k=rng.randint(1, 6)) for _ in range(20)]


def test_sum_above_matches_the_requirement():
    assert_python_oracle(
        "ai.py.sum_above",
        lambda text: {"t": _num(text, r"строго больше (\d+)")},
        lambda p, xs: sum(x for x in xs if x is not None and x > p["t"]),
        _lists)


def test_average_capped():
    def oracle(p, xs):
        vals = [x for x in xs if x is not None and x <= p["cap"]]
        return round(statistics.fmean(vals), p["d"]) if vals else 0.0

    def inputs(p, rng):
        c = p["cap"]
        pool = [None, 1, c // 2, c, c + 1, -c, -3, 2 * c]
        return [[], [None], [None, c // 2], [c, 1], [-(c // 2), c // 2 + 3]] + [
            rng.choices(pool, k=rng.randint(1, 6)) for _ in range(20)]

    assert_python_oracle("ai.py.average_capped",
                         lambda t: {"cap": _num(t, r"не больших (\d+)"), "d": _num(t, r"до (\d) знаков")},
                         oracle, inputs)


def test_dedupe_first_k():
    def inputs(p, rng):
        k = p["k"]
        pool = [None, 1, 2, 3, 5, 8, 13]
        return [[], [None, 4, None], [7, 8, 7, 9], list(range(10, 10 + k + 1))] + [
            rng.choices(pool, k=rng.randint(1, k + 4)) for _ in range(20)]

    assert_python_oracle("ai.py.dedupe_first_k", lambda t: {"k": _num(t, r"не больше (\d+) штук")},
                         lambda p, xs: list(dict.fromkeys(xs))[:p["k"]], inputs)


def test_normalize_login():
    def oracle(p, s):
        if s is None:
            return ""
        body = "".join(ch.lower() for ch in s.strip())
        return (p["prefix"] + body)[:p["L"]]

    def inputs(p, rng):
        chars = "aBcЁжЯ  1_"
        return [None, "", "  ЁЖ Иванов ", "a" * p["L"], " X "] + [
            "".join(rng.choices(chars, k=rng.randint(0, p["L"] + 3))) for _ in range(20)]

    assert_python_oracle("ai.py.normalize_login",
                         lambda t: {"prefix": re.search(r"в начало «([^»]+)»", t).group(1),
                                    "L": _num(t, r"до (\d+) символов")},
                         oracle, inputs)


def test_count_words_len():
    def oracle(p, s):
        return sum(1 for w in re.split(r"\s+", s.strip()) if w and len(w) >= p["m"])

    def inputs(p, rng):
        m = p["m"]
        return ["", "a" * m, "b" * (m - 1), f"{'к' * m} {'к' * m}", f"{'a' * m} {'b' * (m - 1)}"] + [
            rng.choice((" ", " ", "\t", "  ")).join("w" * rng.randint(1, m + 2) for _ in range(rng.randint(1, 5)))
            for _ in range(20)]

    assert_python_oracle("ai.py.count_words_len", lambda t: {"m": _num(t, r"не меньше (\d+) символов")},
                         oracle, inputs)


def test_max_or_default():
    def inputs(p, rng):
        pool = [None, -50, -7, -1, 0, 3, 40]
        return [[], [None], [-5, -2], [4, 4]] + [rng.choices(pool, k=rng.randint(1, 5)) for _ in range(20)]

    assert_python_oracle("ai.py.max_or_default", lambda t: {"d": _num(t, r"Если чисел нет — (-?\d+)")},
                         lambda p, xs: max((x for x in xs if x is not None), default=p["d"]), inputs)


def test_parse_ints():
    def inputs(p, rng):
        sep, n = p["sep"], p["n"]
        def line():
            return sep.join(f"{' ' * rng.randint(0, 1)}{rng.randint(-99, 99)}{' ' * rng.randint(0, 1)}"
                            for _ in range(rng.randint(1, n + 3)))
        return ["   ", "", f"1{sep} -2", f"3{sep}3", sep.join(map(str, range(1, n + 1)))] + [line() for _ in range(20)]

    def oracle(p, s):
        return [int(x) for x in re.findall(r"-?\d+", s)][:p["n"]]

    assert_python_oracle("ai.py.parse_ints",
                         lambda t: {"sep": re.search(r"через «(.)»", t).group(1), "n": _num(t, r"не больше (\d+) первых")},
                         oracle, inputs)


def test_pages_count():
    assert_python_oracle("ai.py.pages_count", lambda t: {"k": _num(t, r"по (\d+) на")},
                         lambda p, n: math.ceil(n / p["k"]),
                         lambda p, rng: [0, 1, p["k"], p["k"] + 1, 2 * p["k"]] + [rng.randint(0, 1000) for _ in range(20)])


def test_merge_counts():
    def oracle(p, args):
        c = Counter()
        for d in args:
            c.update(d)
        return {k: v for k, v in c.items() if v >= p["m"]}

    def inputs(p, rng):
        m = p["m"]
        keys = ["x", "y", "X", "z"]
        rand = lambda: {k: rng.randint(-5, m + 5) for k in rng.sample(keys, rng.randint(0, 3))}  # noqa: E731
        return [({}, {}), ({"x": m}, {"x": m}), ({"x": m + 5}, {"x": -3}), ({"x": m}, {})] + [
            (rand(), rand()) for _ in range(20)]

    assert_python_oracle("ai.py.merge_counts", lambda t: {"m": _num(t, r"не меньше (\d+)")}, oracle, inputs)


def test_chunk_k():
    def oracle(p, xs):
        out, rest = [], list(xs)
        while rest:
            out.append(rest[:p["k"]])
            rest = rest[p["k"]:]
        return out

    def inputs(p, rng):
        k = p["k"]
        return [[], [7] * k, [-1, -2], list(range(1, k + 2))] + [
            [rng.randint(-9, 9) for _ in range(rng.randint(0, 3 * k))] for _ in range(20)]

    assert_python_oracle("ai.py.chunk_k", lambda t: {"k": _num(t, r"части по (\d+)")}, oracle, inputs)


def test_unique_tags():
    def oracle(p, tags):
        seen = set()
        for t in tags:
            t = t.strip()
            if len(t) <= p["L"]:
                seen.add(t.lower())
        return len(seen)

    def inputs(p, rng):
        L = p["L"]
        pool = ["go", "Go", " go ", "Ёлка", "ёлка", "x" * L, "y" * (L + 1), "ПиТон"]
        return [[], ["go", "go"], ["Ёлка", "ёлка"], ["x" * L]] + [rng.choices(pool, k=rng.randint(1, 6)) for _ in range(20)]

    assert_python_oracle("ai.py.unique_tags", lambda t: {"L": _num(t, r"длиннее (\d+) символов")}, oracle, inputs)


def test_in_range_count():
    def oracle(p, xs):
        n = 0
        for x in xs:
            if x is not None and p["lo"] <= x <= p["hi"]:
                n += 1
        return n

    def inputs(p, rng):
        lo, hi = p["lo"], p["hi"]
        pool = [None, lo - 1, lo, lo + 1, hi, hi + 1, -lo, 0]
        return [[], [None, lo + 1], [-lo, lo + 1], [lo, hi]] + [rng.choices(pool, k=rng.randint(1, 6)) for _ in range(20)]

    assert_python_oracle("ai.py.in_range_count",
                         lambda t: dict(zip(("lo", "hi"), map(int, re.search(r"от (\d+) до (\d+)", t).groups()), strict=True)),
                         oracle, inputs)


def test_password_ok():
    def oracle(p, s):
        if s is None:
            return False
        return len(s) >= p["L"] and sum(ch in "0123456789" for ch in s) >= p["n"]

    def inputs(p, rng):
        L, n = p["L"], p["n"]
        chars = "abcЖя12345"
        return [None, "", "a" * (L - n) + "1" * n, "Пароль" + "1" * max(n, L - 6)] + [
            "".join(rng.choices(chars, k=rng.randint(0, L + 3))) for _ in range(20)]

    assert_python_oracle("ai.py.password_ok",
                         lambda t: {"L": _num(t, r"не меньше (\d+) символов"), "n": _num(t, r"не меньше (\d+) цифр")},
                         oracle, inputs)


def test_running_balance():
    def oracle(p, ops):
        b = p["B"]
        for op in ops:
            if b + op < 0:
                continue
            b += op
        return b

    def inputs(p, rng):
        B = p["B"]
        return [[], [-B], [-10], [-B, 5]] + [[rng.randint(-B, B) for _ in range(rng.randint(1, 6))] for _ in range(20)]

    assert_python_oracle("ai.py.running_balance", lambda t: {"B": _num(t, r"начальном балансе (\d+)")}, oracle, inputs)
