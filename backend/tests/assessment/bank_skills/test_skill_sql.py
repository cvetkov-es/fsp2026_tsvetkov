import re

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family

from ._helpers import assert_mcq_form, make, skill_codes

CODES = skill_codes("sql")
SEEDS = range(40)


def rows(inst, name):
    return next(t for t in inst.prompt.tables if t.name == name).rows


def nums(text: str) -> list[int]:
    return [int(x) for x in re.findall(r"-?\d+", text)]


@pytest.mark.parametrize("code", CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)


def test_volume_and_areas():
    assert len(CODES) == 10
    assert sorted(REGISTRY[c].level for c in CODES) == [1, 1, 2, 2, 2, 2, 3, 3, 3, 4]
    assert {REGISTRY[c].area for c in CODES} == {"query", "model"}


def test_between_is_inclusive():
    for seed in SEEDS:
        inst = make("sk.sql.between_inclusive_count", seed)
        a, b = map(int, re.search(r"BETWEEN (\d+) AND (\d+)", inst.prompt.code).groups())
        prices = [r[2] for r in rows(inst, "products")]
        assert a in prices and b in prices  # значения на обеих границах есть в данных
        assert inst.answer == sum(a <= p <= b for p in prices)


def test_like_pattern_count():
    for seed in SEEDS:
        inst = make("sk.sql.like_pattern_count", seed)
        pattern = re.search(r"LIKE '([^']+)'", inst.prompt.code).group(1)
        rx = re.compile("".join(".*" if ch == "%" else "." if ch == "_" else re.escape(ch) for ch in pattern))
        assert inst.answer == sum(bool(rx.fullmatch(r[1])) for r in rows(inst, "staff"))


def test_sum_by_category():
    for seed in SEEDS:
        inst = make("sk.sql.sum_by_category", seed)
        cat = re.search(r"«([^»]+)»", inst.prompt.text).group(1)
        assert inst.answer == sum(r[2] for r in rows(inst, "sales") if r[1] == cat)


def test_join_on_two_keys_counts_pairs_with_multiplicity():
    for seed in SEEDS:
        inst = make("sk.sql.join_two_keys_rows", seed)
        plans, facts = rows(inst, "plans"), rows(inst, "facts")
        assert inst.answer == sum(1 for p in plans for f in facts if (p[0], p[1]) == (f[0], f[1]))


def test_null_avg():
    for seed in SEEDS:
        inst = make("sk.sql.null_avg", seed)
        amounts = [r[1] for r in rows(inst, "bonus")]
        assert 2 <= amounts.count(None) <= 4
        known = [a for a in amounts if a is not None]
        expected = sum(known) / len(amounts) if "COALESCE" in inst.prompt.code else sum(known) / len(known)
        assert inst.answer == pytest.approx(round(expected, 2))


def test_in_subquery_count():
    for seed in SEEDS:
        inst = make("sk.sql.in_subquery_count", seed)
        x = int(re.search(r"total > (\d+)", inst.prompt.code).group(1))
        ids = {u[0] for u in rows(inst, "users")}
        assert inst.answer == len({o[1] for o in rows(inst, "orders") if o[2] > x} & ids)


def test_fk_on_many_side():
    for seed in SEEDS:
        inst = make("sk.sql.fk_side_choice", seed)
        one, many = re.search(r"Таблицы (\w+) \(\d+ строк\w*\) и (\w+)", inst.prompt.text).groups()
        key = inst.prompt.options[inst.answer]
        assert key.startswith(f"{many}.") and key.endswith(f"→ {one}.id")
    assert_mcq_form("sk.sql.fk_side_choice")


def test_unique_violations_count_repeats():
    for seed in SEEDS:
        inst = make("sk.sql.unique_violations", seed)
        emails = re.findall(r"VALUES \('([^']+)'\)", inst.prompt.code)
        assert inst.answer == len(emails) - len(set(emails))


def test_junction_rows():
    for seed in SEEDS:
        inst = make("sk.sql.junction_rows", seed)
        title = re.search(r"c\.title = '([^']+)'", inst.prompt.code).group(1)
        cid = next(c[0] for c in rows(inst, "courses") if c[1] == title)
        students = {s[0] for s in rows(inst, "students")}
        assert inst.answer == sum(1 for e in rows(inst, "enrollments") if e[1] == cid and e[0] in students)


def test_savepoint_rolls_back_only_the_middle_update():
    for seed in SEEDS:
        inst = make("sk.sql.savepoint_value", seed)
        balance = rows(inst, "account")[0][1]
        lines = inst.prompt.code.splitlines()
        undone = False
        for i, line in enumerate(lines):
            m = re.search(r"SET balance = balance ([+-]) (\d+) WHERE id = 1", line)
            if not m:
                continue
            rolled = any(ln.startswith("SAVEPOINT") for ln in lines[:i]) and any(
                ln.startswith("ROLLBACK TO") for ln in lines[i:]) and not any(
                ln.startswith("ROLLBACK TO") for ln in lines[:i])
            if rolled:
                undone = True
                continue
            balance += int(m.group(2)) * (1 if m.group(1) == "+" else -1)
        assert undone and inst.answer == balance


def _rows_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "строка"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "строки"
    return "строк"


def test_fk_row_counts_are_declined():
    for seed in range(100):
        text = make("sk.sql.fk_side_choice", seed).prompt.text
        for n, word in re.findall(r"\((\d+) (\w+)\)", text):
            assert word == _rows_word(int(n)), text
