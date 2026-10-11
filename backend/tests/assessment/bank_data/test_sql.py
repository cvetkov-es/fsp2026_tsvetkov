"""Семантические тесты Data · SQL и модели данных: ключ пересчитывается на Python по таблицам задания."""
import operator
import re
import statistics

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family

from .._bank_helpers import area_codes, make

AREA_CODES = area_codes("sql", "data")


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)
    assert r.space_estimate >= 50_000, (code, r.space_estimate)


OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


def _rows(table) -> list[dict]:
    return [dict(zip(table.columns, r, strict=True)) for r in table.rows]


# ------------------------------------------------------------------ where_count
def test_where_count_key():
    seen = set()
    for seed in range(200):
        inst = make("da.sql.where_count", seed)
        q = inst.prompt.code
        kind = re.search(r"type = '(\w+)'", q).group(1)
        op, t = re.search(r"amount ([<>]=?) (\d+)", q).groups()
        want = sum(r["type"] == kind and OPS[op](r["amount"], int(t)) for r in _rows(inst.prompt.tables[0]))
        assert inst.answer == want and inst.kind == "number"
        seen.add(want)
    assert len(seen) >= 4


# ------------------------------------------------------------------ distinct_count
def test_distinct_count_key():
    for seed in range(200):
        inst = make("da.sql.distinct_count", seed)
        col = re.search(r"COUNT\(DISTINCT (\w+)\)", inst.prompt.code).group(1)
        rows = _rows(inst.prompt.tables[0])
        assert inst.answer == len({r[col] for r in rows}) < len(rows)  # повторы есть


# ------------------------------------------------------------------ group_avg_value
def test_group_avg_value_key():
    for seed in range(200):
        inst = make("da.sql.group_avg_value", seed)
        cat = re.search(r"категории «(\w+)»", inst.prompt.text).group(1)
        amounts = [r["amount"] for r in _rows(inst.prompt.tables[0]) if r["category"] == cat]
        assert len(amounts) >= 2
        assert inst.answer == round(statistics.mean(amounts), 2)


# ------------------------------------------------------------------ left_join_count
def test_left_join_count_key():
    lonely = 0
    for seed in range(200):
        inst = make("da.sql.left_join_count", seed)
        users, sessions = (_rows(t) for t in inst.prompt.tables)
        per_user = [sum(s["user_id"] == u["id"] for s in sessions) for u in users]
        # LEFT JOIN: у пользователя без сессий — одна строка с NULL, иначе по строке на сессию
        assert inst.answer == sum(max(1, k) for k in per_user)
        lonely += 0 in per_user
    assert lonely >= 150


# ------------------------------------------------------------------ case_when_count
def test_case_when_count_key():
    for seed in range(200):
        inst = make("da.sql.case_when_count", seed)
        q = inst.prompt.code
        alias = re.search(r"значение (\w+)", inst.prompt.text).group(1)
        op, t = re.search(rf"WHEN amount ([<>]=?) (\d+) THEN 1 ELSE 0 END\) AS {alias}", q).groups()
        rows = _rows(inst.prompt.tables[0])
        assert inst.answer == sum(OPS[op](r["amount"], int(t)) for r in rows)
        assert any(r["amount"] == int(t) for r in rows)  # граница есть в данных: важно, строгое ли сравнение


# ------------------------------------------------------------------ count_distinct_nulls
def test_count_distinct_nulls_key():
    for seed in range(200):
        inst = make("da.sql.count_distinct_nulls", seed)
        col = re.search(r"COUNT\(DISTINCT (\w+)\)", inst.prompt.code).group(1)
        values = [r[col] for r in _rows(inst.prompt.tables[0])]
        assert values.count(None) >= 2
        assert inst.answer == len({v for v in values if v is not None})  # NULL не считается значением


# ------------------------------------------------------------------ join_fanout_sum
def test_join_fanout_sum_key():
    for seed in range(200):
        inst = make("da.sql.join_fanout_sum", seed)
        orders, items = (_rows(t) for t in inst.prompt.tables)
        per_order = {o["id"]: sum(i["order_id"] == o["id"] for i in items) for o in orders}
        want = sum(o["amount"] * per_order[o["id"]] for o in orders)  # сумма заказа повторяется на каждую позицию
        naive = sum(o["amount"] for o in orders if per_order[o["id"]])
        assert inst.answer == want != naive


# ------------------------------------------------------------------ month_group_count
def test_month_group_count_key():
    boundary = 0
    for seed in range(200):
        inst = make("da.sql.month_group_count", seed)
        month = re.search(r"месяца (\d{4}-\d{2})", inst.prompt.text).group(1)
        dates = [r["created_at"] for r in _rows(inst.prompt.tables[0])]
        assert len({d[:4] for d in dates}) == 1
        assert inst.answer == sum(d[:7] == month for d in dates)
        boundary += any(d.endswith(("-30", "-31", "-01")) for d in dates)
    assert boundary >= 150  # даты у границы месяца встречаются


# ------------------------------------------------------------------ running_total
def test_running_total_key():
    for seed in range(200):
        inst = make("da.sql.running_total", seed)
        rows = _rows(inst.prompt.tables[0])
        target = int(re.search(r"строке с id = (\d+)", inst.prompt.text).group(1))
        row = next(r for r in rows if r["id"] == target)
        same_user = [r for r in rows if r["user_id"] == row["user_id"]]
        assert len({r["paid_at"] for r in same_user}) == len(same_user)  # даты внутри пользователя уникальны
        assert inst.answer == sum(r["amount"] for r in same_user if r["paid_at"] <= row["paid_at"])
        assert [r["id"] for r in rows] != [r["id"] for r in sorted(rows, key=lambda r: (r["user_id"], r["paid_at"]))]


# ------------------------------------------------------------------ lag_diff
def test_lag_diff_key():
    for seed in range(200):
        inst = make("da.sql.lag_diff", seed)
        rows = sorted(_rows(inst.prompt.tables[0]), key=lambda r: r["day"])
        day = re.search(r"для дня (\d{4}-\d{2}-\d{2})", inst.prompt.text).group(1)
        i = next(k for k, r in enumerate(rows) if r["day"] == day)
        assert i > 0 and inst.answer == rows[i]["value"] - rows[i - 1]["value"]  # предыдущий по дате, не по id
        assert [r["day"] for r in _rows(inst.prompt.tables[0])] != [r["day"] for r in rows]


# ------------------------------------------------------------------ dedupe_row_number
def test_dedupe_row_number_key():
    for seed in range(200):
        inst = make("da.sql.dedupe_row_number", seed)
        rows = _rows(inst.prompt.tables[0])
        status = re.search(r"status = '(\w+)'", inst.prompt.code).group(1)
        latest = {}
        for r in sorted(rows, key=lambda r: r["updated_at"]):
            latest[r["account_id"]] = r["status"]  # последняя запись аккаунта перезаписывает предыдущие
        want = sum(s == status for s in latest.values())
        assert inst.answer == want
        naive_rows = sum(r["status"] == status for r in rows)
        naive_any = len({r["account_id"] for r in rows if r["status"] == status})
        assert want not in (naive_rows, naive_any)  # ни подсчёт строк, ни «был хоть раз» не дают ответ


# ------------------------------------------------------------------ range_vs_rows
def test_range_vs_rows_key():
    for seed in range(200):
        inst = make("da.sql.range_vs_rows", seed)
        rows = _rows(inst.prompt.tables[0])
        target = int(re.search(r"строке с id = (\d+)", inst.prompt.text).group(1))
        row = next(r for r in rows if r["id"] == target)
        peers = [r for r in rows if r["day"] == row["day"]]
        assert len(peers) >= 2  # у строки есть «соседи» с той же датой
        assert inst.answer == sum(r["amount"] for r in rows if r["day"] <= row["day"])  # RANGE включает всех peers
        rows_by_id = sum(r["amount"] for r in rows if r["day"] < row["day"] or (r["day"] == row["day"] and r["id"] <= target))
        assert rows_by_id != inst.answer


# ------------------------------------------------------------------ cohort_retention
def _next_month(ym: str) -> str:
    y, m = map(int, ym.split("-"))
    return f"{y + m // 12}-{m % 12 + 1:02d}"


def test_cohort_retention_key():
    for seed in range(150):
        inst = make("da.sql.cohort_retention", seed)
        users, activity = (_rows(t) for t in inst.prompt.tables)
        month = re.search(r"когорты (\d{4}-\d{2})", inst.prompt.text).group(1)
        cohort = [u["id"] for u in users if u["signup_date"][:7] == month]
        nxt = _next_month(month)
        retained = {a["user_id"] for a in activity if a["user_id"] in cohort and a["active_date"][:7] == nxt}
        assert inst.answer == round(100 * len(retained) / len(cohort), 1)
        same_month = {a["user_id"] for a in activity if a["user_id"] in cohort and a["active_date"][:7] == month}
        assert same_month - retained or len(retained) < len(cohort)


def test_cohort_activity_not_before_signup():
    for seed in range(150):
        users, activity = (_rows(t) for t in make("da.sql.cohort_retention", seed).prompt.tables)
        signup = {u["id"]: u["signup_date"] for u in users}
        assert all(a["active_date"] >= signup[a["user_id"]] for a in activity)
