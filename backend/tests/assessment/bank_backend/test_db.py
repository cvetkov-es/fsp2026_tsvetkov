import ast
import re
from collections import Counter

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.canon import is_correct
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import backend_db as db_module
from app.assessment.bank.sqlite_sandbox import run_query, setup_sql

from ._helpers import area_codes
from ._helpers import make as _make

AREA_CODES = area_codes("db")
SEEDS = range(40)


def _tables(inst):
    return {t.name: t for t in inst.prompt.tables}


def _col(table, name):
    return table.columns.index(name)


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


def test_no_digit_leak_in_text_for_number_families():
    # Ключ не должен стоять в тексте задания отдельным числом
    for code in AREA_CODES:
        for seed in SEEDS:
            inst = _make(code, seed)
            if inst.kind != "number":
                continue
            nums = set(re.findall(r"(?<![\w.])\d+(?![\w.])", inst.prompt.text))
            assert str(int(inst.answer)) not in nums, (code, seed)


# ---------------------------------------------------------------- batch A
def test_where_and_or_count_key():
    for seed in SEEDS:
        inst = _make("be.db.where_and_or_count", seed)
        t = _tables(inst)["products"]
        m = re.search(r"category = '([^']+)' AND \(price > (\d+) OR in_stock = 1\)", inst.prompt.code)
        cat, price = m.group(1), int(m.group(2))
        ic, ip, ist = _col(t, "category"), _col(t, "price"), _col(t, "in_stock")
        expected = sum(1 for r in t.rows if r[ic] == cat and (r[ip] > price or r[ist] == 1))
        assert inst.answer == expected
        assert 8 <= len(t.rows) <= 12
        # товар и категория согласованы: пара взята из каталога
        for r in t.rows:
            assert r[_col(t, "name")] in db_module.CATALOG[r[ic]]
        assert sum(1 for r in t.rows if r[ic] == cat) >= 3
        assert len({r[_col(t, "name")] for r in t.rows}) == len(t.rows)
    assert len({_make("be.db.where_and_or_count", s).answer for s in range(60)}) >= 4


def test_pools_have_no_duplicates():
    pools = [c[2] for c in db_module.COUNT_CONTEXTS] + [c[3] for c in db_module.COUNT_CONTEXTS]
    pools += [c[2] for c in db_module.NOT_IN_CONTEXTS] + [c[4] for c in db_module.ORDER_CONTEXTS]
    pools += [c[8] for c in db_module.ORM_CONTEXTS] + [p for v in db_module.CATALOG.values() for p in [v]]
    for pool in pools:
        assert len(set(pool)) == len(pool), pool
    flat = [x for v in db_module.CATALOG.values() for x in v]
    assert len(set(flat)) == len(flat)


def test_order_limit_value_key():
    for seed in SEEDS:
        inst = _make("be.db.order_limit_value", seed)
        m = re.fullmatch(r"SELECT (\w+)\nFROM (\w+)\nORDER BY (\w+) DESC\nLIMIT 1;", inst.prompt.code)
        name_col, tname, val_col = m.groups()
        t = _tables(inst)[tname]
        vals = [r[_col(t, val_col)] for r in t.rows]
        assert len(set(vals)) == len(vals)
        top = max(t.rows, key=lambda r: r[_col(t, val_col)])
        assert inst.answer == top[_col(t, name_col)]
        assert len({r[_col(t, name_col)] for r in t.rows}) == len(t.rows)
        # текстовый ответ сравнивается с учётом регистра — подсказка формата говорит об этом прямо
        assert inst.prompt.answer_hint == f"Значение колонки {name_col} — в точности как в таблице, с учётом регистра"
        assert not is_correct(inst, inst.answer.lower()) and is_correct(inst, f" {inst.answer} ")
    assert len({_make("be.db.order_limit_value", s).answer for s in range(60)}) >= 5


def test_group_having_count_key():
    for seed in SEEDS:
        inst = _make("be.db.group_having_count", seed)
        m = re.search(r"GROUP BY (\w+)\nHAVING COUNT\(\*\) > (\d+);", inst.prompt.code)
        col, k = m.group(1), int(m.group(2))
        t = _tables(inst)["orders"]
        cnt = Counter(r[_col(t, col)] for r in t.rows)
        assert inst.answer == sum(1 for v in cnt.values() if v > k)
        assert 10 <= len(t.rows) <= 16


def test_inner_join_rows_key():
    for seed in SEEDS:
        inst = _make("be.db.inner_join_rows", seed)
        tabs = _tables(inst)
        c, o = tabs["customers"], tabs["orders"]
        expected = 0
        for cr in c.rows:
            for orow in o.rows:
                if orow[_col(o, "customer_id")] == cr[_col(c, "id")]:
                    expected += 1
        assert inst.answer == expected
        per = Counter(r[_col(o, "customer_id")] for r in o.rows)
        ids = {r[0] for r in c.rows}
        assert any(per[i] == 0 for i in ids)  # у части клиентов нет заказов
        assert any(per[i] >= 2 for i in ids)  # у части несколько
        assert any(r[_col(o, "customer_id")] not in ids for r in o.rows)  # заказ без клиента


def test_count_variants_nulls_key():
    for seed in SEEDS:
        inst = _make("be.db.count_variants_nulls", seed)
        m = re.fullmatch(r"SELECT COUNT\(DISTINCT (\w+)\)\nFROM (\w+);", inst.prompt.code)
        col, tname = m.groups()
        t = _tables(inst)[tname]
        vals = [r[_col(t, col)] for r in t.rows]
        distinct = len({v for v in vals if v is not None})
        assert inst.answer == distinct
        assert len(vals) != sum(v is not None for v in vals) != distinct
        assert len(vals) != distinct
    assert len({_make("be.db.count_variants_nulls", s).answer for s in range(200)}) >= 5


def test_not_in_null_trap():
    code = "be.db.not_in_null_trap"
    positions = set()
    consecutive = 0
    for seed in range(60):
        inst = _make(code, seed)
        q = inst.prompt.code
        assert "NOT IN (SELECT" in q
        rows = run_query(setup_sql(*inst.prompt.tables), q)
        assert rows == []  # NULL в подзапросе: ни одной строки
        opts = inst.prompt.options
        assert opts[inst.answer] == "0"
        assert len(set(opts)) == 4
        # у подзапроса есть NULL и обычные значения
        sub_t = [t for t in inst.prompt.tables if t.name in q.split("NOT IN")[1]][0]
        vals = [r[0] for r in sub_t.rows]
        assert None in vals and 2 <= len({v for v in vals if v is not None}) <= 3
        # дистракторы считаем в Python независимо от SQL генератора
        main = inst.prompt.tables[0]
        ids = {r[0] for r in main.rows}
        present = {v for v in vals if v is not None}
        total = len(main.rows)
        not_exists = len(ids - present)
        in_reading = len(ids & present)
        expected = {"0", str(not_exists), str(in_reading), str(total)}
        assert set(opts) == expected and len(expected) == 4 and not_exists >= 1
        distractors = sorted(int(o) for o in opts if o != "0")
        consecutive += distractors[2] - distractors[0] == 2
        positions.add(inst.answer)
    assert len(positions) >= 3
    assert consecutive <= 0.2 * 60  # ключ «0» не выделяется тремя подряд идущими числами


def test_window_rank_key():
    code = "be.db.window_rank"
    answers = set()
    tied_asked = 0
    for seed in range(200):
        inst = _make(code, seed)
        t = _tables(inst)["results"]
        name = re.search(r"name = '([^']+)'", inst.prompt.text).group(1)
        scores = [r[_col(t, "score")] for r in t.rows]
        mine = next(r[_col(t, "score")] for r in t.rows if r[_col(t, "name")] == name)
        rank = 1 + sum(s > mine for s in scores)
        dense = 1 + len({s for s in scores if s > mine})
        assert inst.answer == rank
        tied = scores.count(mine) > 1
        assert rank != dense or tied  # внутри группы равных или сразу после неё
        assert mine != min(scores)  # самую низкую строку не спрашиваем
        tied_asked += tied
        assert len(set(scores)) < len(scores)  # есть равные баллы
        assert "RANK() OVER (ORDER BY score DESC)" in inst.prompt.code
        answers.add(rank)
    assert len(answers) >= 3
    assert tied_asked > 0


# ---------------------------------------------------------------- batch C
def test_composite_index_order_key():
    code = "be.db.composite_index_order"
    pos = set()
    key_in_longer_pair = set()
    for seed in range(120):
        inst = _make(code, seed)
        q = inst.prompt.code
        m = re.search(r"FROM (\w+)\nWHERE (\w+) = \$1 AND (\w+) (?:>=|<=|>|<) \$2\nORDER BY (\w+)", q)
        t, a, b, c = m.groups()
        assert len({a, b, c}) == 3
        opts = inst.prompt.options
        # ровно четыре двухколоночных индекса: две пары с переставленными колонками
        assert set(opts) == {f"индекс {t} ({a}, {b})", f"индекс {t} ({b}, {a})",
                             f"индекс {t} ({b}, {c})", f"индекс {t} ({c}, {b})"}
        assert len(opts) == 4
        # правильный: колонка равенства первой, диапазона второй
        assert opts[inst.answer] == f"индекс {t} ({a}, {b})"
        assert "фильтрацию в WHERE" in inst.prompt.text
        pos.add(inst.answer)
        lens = [len(o) for o in opts]
        assert max(lens) <= 1.4 * min(lens), opts
        L = lens[inst.answer]
        assert lens.count(L) >= 2  # длина ключа есть и у дистрактора
        if len(a) != len(c):
            key_in_longer_pair.add(len(a) > len(c))
    assert len(pos) == 4
    assert key_in_longer_pair == {True, False}  # по длине ключ не угадывается


NUMERIC_COLUMNS = {"birth_year", "total", "size", "price", "balance", "budget", "rating"}


def _column_type(name):
    """Ожидаемый тип колонки по смыслу имени (независимо от генератора)."""
    if name == "id" or name.endswith("_id"):
        return "Integer"
    if name.endswith("_at") or name == "deadline":
        return "DateTime"
    return "Integer" if name in NUMERIC_COLUMNS else "String"


def test_n_plus_one_model_column_types_match_names():
    seen = set()
    for seed in range(300):
        code = _make("be.db.n_plus_one_count", seed).prompt.code
        for name, kind in re.findall(r"^    (\w+) = Column\((\w+)", code, re.M):
            assert kind == _column_type(name), (name, kind)
            seen.add(kind)
    assert seen == {"Integer", "DateTime", "String"}


def test_n_plus_one_count_key():
    code = "be.db.n_plus_one_count"
    for seed in range(60):
        inst = _make(code, seed)
        n = int(re.search(r"\.limit\((\d+)\)", inst.prompt.code).group(1))
        assert 5 <= n <= 40
        assert inst.answer == n + 1
        assert "lazy" in inst.prompt.text.lower() or "ленив" in inst.prompt.text.lower()
        assert "joinedload" not in inst.prompt.code and "selectinload" not in inst.prompt.code
        code_text = inst.prompt.code
        ast.parse(code_text)  # корректный Python
        for attr in re.findall(r"\b(?:[A-Z]\w+)\.(\w+)", code_text.split("session.query")[1]):
            assert re.search(rf"^    {attr} = ", code_text, re.M), attr  # колонка объявлена в модели
        parent = re.search(r"session\.query\((\w+)\)", code_text).group(1)
        assert f"class {parent}(Base)" in code_text
        assert "SELECT-запросов" in inst.prompt.text
        for blob in (inst.prompt.text, inst.prompt.code):
            assert not re.search(rf"(?<![\w.]){n + 1}(?![\w.])", blob)
    assert len({_make(code, s).answer for s in range(60)}) >= 10


SCHEDULE_NAMES = {"lost update", "non-repeatable read", "phantom read", "write skew"}


def _classify(code_text):
    """Независимая классификация расписания по структуре."""
    if "INSERT" in code_text:
        return "phantom read"
    updates = re.findall(r"UPDATE .* WHERE (.*?);", code_text)
    if len(updates) == 1:
        return "non-repeatable read"
    return "lost update" if updates[0] == updates[1] else "write skew"


def test_isolation_anomaly_key():
    code = "be.db.isolation_anomaly"
    keys = set()
    for seed in range(120):
        inst = _make(code, seed)
        opts = inst.prompt.options
        assert len(opts) == 4 and len(set(opts)) == 4
        chosen = opts[inst.answer].lower()
        names = {o.lower() for o in opts}
        assert all(any(n in o for o in names) for n in SCHEDULE_NAMES)
        expected = _classify(inst.prompt.code)
        assert expected in chosen
        keys.add(expected)
        assert "COMMIT" in inst.prompt.code and "T1" in inst.prompt.code and "T2" in inst.prompt.code
    assert keys == SCHEDULE_NAMES


def _lines(code_text):
    """Шаги расписания (кто, оператор); строки-комментарии «-- …» пропускаются."""
    return [ln.split(": ", 1) for ln in code_text.split("\n") if not ln.startswith("--")]


ANOMALY_WORDS = ("lost", "update", "repeatable", "phantom", "skew", "потерян", "неповтор", "фантом",
                 "перекос", "аномал")


def test_isolation_schedule_starts_with_neutral_context_comment():
    """У всех четырёх расписаний первая строка — комментарий о сценарии; аномалию он не называет."""
    comments = {}
    for seed in range(200):
        inst = _make("be.db.isolation_anomaly", seed)
        lines = inst.prompt.code.split("\n")
        assert lines[0].startswith("-- ") and not any(ln.startswith("--") for ln in lines[1:])
        comment = lines[0].lower()
        assert not any(w in comment for w in ANOMALY_WORDS), comment
        kind = _classify(inst.prompt.code)
        comments.setdefault(kind, set()).add(lines[0])
        if kind == "write skew":  # инвариант назван по той же колонке, что меняет расписание
            col = re.search(r"WHERE (\w+) = true", inst.prompt.code).group(1)
            assert re.fullmatch(rf"-- правило: хотя бы один \w+ должен оставаться {col} = true", lines[0])
    assert set(comments) == SCHEDULE_NAMES


def test_isolation_values_consistent():
    seen = set()
    for seed in range(200):
        inst = _make("be.db.isolation_anomaly", seed)
        text = inst.prompt.code
        kind = _classify(text)
        seen.add(kind)
        lines = _lines(text)
        results = [int(m) for m in re.findall(r"-- (\d+)", text)]
        if kind == "lost update":
            assert len(results) == 2 and results[0] == results[1]
            order = [(who, stmt.split(" ")[0]) for who, stmt in lines]
            # T2 пишет только после COMMIT T1: иначе в PostgreSQL она ждала бы блокировку
            assert order.index(("T1", "COMMIT;")) < order.index(("T2", "UPDATE"))
            upd = [int(x) for x in re.findall(r"= (\d+) WHERE", text)]
            assert all(u < results[0] for u in upd)
        elif kind == "non-repeatable read":
            assert len(results) == 2
            assert int(re.search(r"SET \w+ = (\d+)", text).group(1)) == results[1] != results[0]
        elif kind == "phantom read":
            assert len(results) == 2 and results[1] == results[0] + 1
        else:
            assert results == [2, 2]
            names = re.findall(r"WHERE name = '([^']+)'", text)
            assert len(names) == 2 and names[0] != names[1]
        # во всех расписаниях транзакции параллельны и фиксируются
        assert text.count("BEGIN;") == 2 and text.count("COMMIT;") == 2
        assert "прочитано" not in text
    assert seen == SCHEDULE_NAMES


def test_window_frame_sum_key():
    code = "be.db.window_frame_sum"
    for seed in range(60):
        inst = _make(code, seed)
        t = _tables(inst)["daily_sales"]
        days = [r[_col(t, "day")] for r in t.rows]
        assert len(set(days)) == len(days)
        day = re.search(r"day = '(\d{4}-\d\d-\d\d)'", inst.prompt.text).group(1)
        ordered = sorted(t.rows, key=lambda r: r[_col(t, "day")])
        i = [r[_col(t, "day")] for r in ordered].index(day)
        assert i >= 1
        expected = ordered[i][_col(t, "amount")] + ordered[i - 1][_col(t, "amount")]
        assert inst.answer == expected
        assert "ROWS BETWEEN 1 PRECEDING AND CURRENT ROW" in inst.prompt.code
