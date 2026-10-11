import random
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family

from ._helpers import assert_sql_oracle, assert_verdict_form, codes


def test_sql_bank_volume():
    assert len(codes("sql")) == 10


@pytest.mark.parametrize("code", codes("sql"))
def test_sql_verdicts_have_the_verdict_form(code):
    assert_verdict_form(code)


@pytest.mark.parametrize("code", codes("sql"))
def test_sql_verdicts_pass_the_bank_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)


def _n(text: str, pattern: str) -> int:
    return int(re.search(pattern, text).group(1))


def _orders(p: dict, rng: random.Random) -> list[dict]:
    n = p["n"]
    amounts = [None, n - 1, n, n + 1, n * 2]
    return [{"orders": [[i, rng.randint(1, 4), rng.choice(amounts)] for i in range(rng.randint(0, 8))]} for _ in range(15)]


def test_distinct_buyers_matches_the_requirement():
    assert_sql_oracle(
        "ai.sql.distinct_buyers",
        lambda text: {"n": _n(text, r"не меньше (\d+)")},
        lambda p, d: [[len({c for _i, c, a in d["orders"] if a is not None and a >= p["n"]})]],
        _orders)


def test_avg_rating_null():
    def oracle(p, d):
        scores = [s for _i, prod, s in d["reviews"] if prod == p["p"] and s is not None]
        if not scores:
            return [[None]]
        return [[float(Decimal(sum(scores) / len(scores)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))]]

    def datasets(p, rng):
        return [{"reviews": [[i, rng.choice((p["p"], p["p"] + 1)), rng.choice((None, 1, 2, 3, 4, 5))]
                             for i in range(rng.randint(0, 9))]} for _ in range(15)]

    assert_sql_oracle("ai.sql.avg_rating_null", lambda t: {"p": _n(t, r"товара (\d+)")}, oracle, datasets)


def test_dept_headcount():
    def oracle(p, d):
        counts = {name: 0 for _id, name in d["departments"]}
        names = dict(d["departments"])
        for _e, dept in d["employees"]:
            if dept in names:
                counts[names[dept]] += 1
        return [[k, v] for k, v in counts.items()]

    def datasets(p, rng):
        out = []
        for _ in range(15):
            names = rng.sample(["Sales", "HR", "IT", "Legal", "Ops"], rng.randint(1, 4))
            depts = [[i + 1, n] for i, n in enumerate(names)]
            emps = [[j, rng.choice([None, 9, *range(1, len(names) + 1)])] for j in range(rng.randint(0, 7))]
            out.append({"departments": depts, "employees": emps})
        return out

    assert_sql_oracle("ai.sql.dept_headcount", lambda t: {}, oracle, datasets)


def test_orders_in_period():
    def datasets(p, rng):
        d1, d2 = date.fromisoformat(p["d1"]), date.fromisoformat(p["d2"])
        pool = [d1 - timedelta(days=1), d1, d1 + timedelta(days=1), d2, d2 + timedelta(days=1)]
        return [{"orders": [[i, rng.choice(pool).isoformat()] for i in range(rng.randint(0, 8))]} for _ in range(15)]

    assert_sql_oracle(
        "ai.sql.orders_in_period",
        lambda t: dict(zip(("d1", "d2"), re.search(r"с (\d{4}-\d\d-\d\d) по (\d{4}-\d\d-\d\d)", t).groups(), strict=True)),
        lambda p, d: [[sum(p["d1"] <= c <= p["d2"] for _i, c in d["orders"])]], datasets)


def test_big_spenders():
    def oracle(p, d):
        sums: dict = defaultdict(int)
        seen = set()
        for _i, c, a in d["orders"]:
            seen.add(c)
            if a is not None:
                sums[c] += a
        return [[c] for c in seen if c in sums and sums[c] >= p["n"]]

    def datasets(p, rng):
        n = p["n"]
        pool = [None, n // 2, n // 2 + 1, n - 1, n, n + 1]
        return [{"orders": [[i, rng.randint(1, 4), rng.choice(pool)] for i in range(rng.randint(0, 8))]} for _ in range(15)]

    assert_sql_oracle("ai.sql.big_spenders", lambda t: {"n": _n(t, r"не меньше (\d+)")}, oracle, datasets)


def test_customers_without_orders():
    def datasets(p, rng):
        out = []
        for _ in range(15):
            ids = list(range(1, rng.randint(1, 6)))
            out.append({"customers": [[i, f"c{i}"] for i in ids],
                        "orders": [[j, rng.choice([None, *ids, 99])] for j in range(rng.randint(0, 6))]})
        return out

    assert_sql_oracle("ai.sql.customers_without_orders", lambda t: {},
                      lambda p, d: [[i] for i, _n in d["customers"] if i not in {c for _o, c in d["orders"]}],
                      datasets)


def test_product_search():
    def datasets(p, rng):
        w = p["w"]
        names = [f"Big {w.upper()} pack", f"Iced {w}", w, "plain box", f"{w.capitalize()}Max", "other"]
        return [{"products": [[i, rng.choice(names)] for i in range(rng.randint(0, 6))]} for _ in range(15)]

    assert_sql_oracle("ai.sql.product_search", lambda t: {"w": re.search(r"«([a-z]+)»", t).group(1)},
                      lambda p, d: [[i] for i, name in d["products"] if p["w"] in name.lower()], datasets)


def test_orders_by_month():
    def datasets(p, rng):
        pool = ["2023-03-05", "2024-03-07", "2024-03-20", "2025-11-30", "2025-01-01"]
        return [{"orders": [[i, rng.choice(pool)] for i in range(rng.randint(0, 8))]} for _ in range(15)]

    assert_sql_oracle("ai.sql.orders_by_month", lambda t: {},
                      lambda p, d: [[m, c] for m, c in Counter(x[:7] for _i, x in d["orders"]).items()], datasets)


def test_last_login():
    def oracle(p, d):
        last: dict = {}
        for _i, u, at in d["logins"]:
            last[u] = max(last.get(u, at), at)
        return [[u, at] for u, at in last.items()]

    def datasets(p, rng):
        times = ["2025-03-01 10:00", "2025-03-02 09:00", "2025-02-28 23:59", "2025-03-02 18:30"]
        return [{"logins": [[i, rng.randint(1, 3), rng.choice(times)] for i in range(rng.randint(0, 7))]} for _ in range(15)]

    assert_sql_oracle("ai.sql.last_login", lambda t: {}, oracle, datasets)


def test_paid_revenue():
    def oracle(p, d):
        paid = [a for _i, a, s in d["payments"] if s == "paid" and a is not None]
        return [[sum(paid) if paid else None]]

    def datasets(p, rng):
        return [{"payments": [[i, rng.choice((None, 100, 250, 500)), rng.choice(("paid", "pending", "refunded"))]
                              for i in range(rng.randint(0, 8))]} for _ in range(15)]

    assert_sql_oracle("ai.sql.paid_revenue", lambda t: {}, oracle, datasets)
