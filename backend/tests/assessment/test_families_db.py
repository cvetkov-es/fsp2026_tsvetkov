from statistics import mean

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import load_all

load_all()


def test_left_join_answer_matches_independent_count():
    f = REGISTRY["be.db.left_join_no_orders"]
    for seed in range(30):
        inst = f.make(seed)
        customers, orders = inst.prompt.tables
        with_orders = {row[1] for row in orders.rows}
        assert inst.answer == len(customers.rows) - len(with_orders)
        assert "LEFT JOIN" in inst.prompt.code and "answer" not in inst.public()


def test_avg_ignores_nulls_independent():
    f = REGISTRY["be.db.avg_ignores_null"]
    for seed in range(30):
        inst = f.make(seed)
        (t,) = inst.prompt.tables
        dept = inst.prompt.code.split("'")[1]
        vals = [r[3] for r in t.rows if r[2] == dept and r[3] is not None]
        assert inst.answer == round(mean(vals), 2)
        assert any(r[2] == dept and r[3] is None for r in t.rows)


def test_db_families_pass_pipeline():
    for code in ("be.db.left_join_no_orders", "be.db.avg_ignores_null"):
        r = check_family(REGISTRY[code], subprocess_probe=False)
        assert r.ok, (code, r.errors)
