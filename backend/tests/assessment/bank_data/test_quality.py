"""Семантические тесты Data · качество данных и пайплайны: ключ пересчитывается независимо от генератора."""
import re
from collections import Counter

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import data_quality as dq

from .._bank_helpers import area_codes, make

AREA_CODES = area_codes("quality", "data")


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)
    assert r.space_estimate >= 50_000, (code, r.space_estimate)


def _rows(table) -> list[dict]:
    return [dict(zip(table.columns, r, strict=True)) for r in table.rows]


def _far(x: float, digits: int) -> bool:
    return abs((x * 10**digits) % 1 - 0.5) > 0.01


# ------------------------------------------------------------------ duplicate_keys
def test_duplicate_keys_key():
    forms = set()
    for seed in range(200):
        inst = make("da.quality.duplicate_keys", seed)
        col = re.search(r"COUNT\(DISTINCT (\w+)\)|GROUP BY (\w+)", inst.prompt.code)
        col = col.group(1) or col.group(2)
        counts = Counter(r[col] for r in _rows(inst.prompt.tables[0]))
        if "HAVING" in inst.prompt.code:
            want = sum(c > 1 for c in counts.values())  # ключей с повторами
            forms.add("keys")
        else:
            want = sum(counts.values()) - len(counts)  # лишних строк
            forms.add("extra")
        assert inst.answer == want > 0
    assert forms == {"keys", "extra"}


# ------------------------------------------------------------------ null_share
def test_null_share_key():
    for seed in range(200):
        inst = make("da.quality.null_share", seed)
        col = re.search(r"колонке (\w+)", inst.prompt.text).group(1)
        values = [r[col] for r in _rows(inst.prompt.tables[0])]
        share = values.count(None) / len(values) * 100
        assert inst.answer == round(share, 1) and _far(share, 1) and 0 < share < 100


# ------------------------------------------------------------------ orphans
def test_orphans_key():
    for seed in range(200):
        inst = make("da.quality.orphans", seed)
        parents, children = (_rows(t) for t in inst.prompt.tables)
        fk = re.search(r"ON p\.id = c\.(\w+)", inst.prompt.code).group(1)
        ids = {p["id"] for p in parents}
        assert inst.answer == sum(c[fk] not in ids for c in children) > 0


# ------------------------------------------------------------------ iqr_outliers
def test_iqr_outliers_key():
    import numpy as np
    for seed in range(200):
        inst = make("da.quality.iqr_outliers", seed)
        xs = [int(x) for x in re.search(r"\[(.+)\]", inst.prompt.code).group(1).split(", ")]
        assert "линейной интерполяцией" in inst.prompt.text
        q1, q3 = np.percentile(xs, [25, 75])  # по умолчанию — линейная интерполяция
        lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        assert inst.answer == sum(x < lo or x > hi for x in xs) >= 1
        assert all(abs(x - lo) > 0.5 and abs(x - hi) > 0.5 for x in xs)  # нет значений на границе


# ------------------------------------------------------------------ type_coercion
def test_type_coercion_key():
    import pandas as pd
    seen = set()
    for seed in range(200):
        inst = make("da.quality.type_coercion", seed)
        values = eval(re.search(r"pd\.Series\((\[.+?\])\)", inst.prompt.code).group(1))  # noqa: S307 — наш шаблон
        expr = re.search(r"^result = (.+)$", inst.prompt.code, re.M).group(1)
        try:
            out = eval(expr, {"pd": pd, "s": pd.Series(values)})  # noqa: S307 — настоящий pandas
            outcome = {"float64": "float_nan", "Int64": "int64_na"}[str(out.dtype)]
        except (ValueError, TypeError):
            outcome = "error"
        assert inst.prompt.options[inst.answer] == dq.COERCION_OPTIONS[outcome]
        seen.add(outcome)
    assert seen == {"float_nan", "int64_na", "error"}


# ------------------------------------------------------------------ idempotent_load
def test_idempotent_load_key():
    for seed in range(200):
        inst = make("da.quality.idempotent_load", seed)
        key = inst.prompt.options[inst.answer]
        assert key in dq.IDEMPOTENT_CORRECT
        assert all(o in dq.IDEMPOTENT_WRONG for i, o in enumerate(inst.prompt.options) if i != inst.answer)
        assert "INSERT INTO" in inst.prompt.code


# ------------------------------------------------------------------ late_data
def test_late_data_key():
    for seed in range(200):
        inst = make("da.quality.late_data", seed)
        key = inst.prompt.options[inst.answer]
        assert key in dq.LATE_CORRECT
        assert all(o in dq.LATE_WRONG for i, o in enumerate(inst.prompt.options) if i != inst.answer)


# ------------------------------------------------------------------ scd2_rows
def test_scd2_rows_key():
    for seed in range(200):
        inst = make("da.quality.scd2_rows", seed)
        initial, log = (_rows(t) for t in inst.prompt.tables)
        tracked = set(re.search(r"по атрибутам (\w+) и (\w+)", inst.prompt.text).groups())
        current = {c["id"]: dict(c) for c in initial}
        rows = len(initial)
        noops = untracked = 0
        for ch in sorted(log, key=lambda r: r["changed_at"]):
            cur = current[ch["customer_id"]]
            if ch["attribute"] not in tracked:
                untracked += 1  # перезаписывается без новой версии
            elif cur[ch["attribute"]] == ch["new_value"]:
                noops += 1  # значение не изменилось — новой версии нет
            else:
                rows += 1
            cur[ch["attribute"]] = ch["new_value"]
        assert inst.answer == rows and noops + untracked >= 1


# ------------------------------------------------------------------ dag_order
def test_dag_order_key():
    from graphlib import TopologicalSorter
    for seed in range(200):
        inst = make("da.quality.dag_order", seed)
        deps = re.findall(r"^(\w+) зависит от (\w+)$", inst.prompt.code, re.M)
        graph = {}
        for task, dep in deps:
            graph.setdefault(task, set()).add(dep)
        order = list(TopologicalSorter(graph).static_order())
        # порядок единственный: каждая соседняя пара связана прямой зависимостью
        assert all((b, a) in deps for a, b in zip(order, order[1:], strict=False))
        steps = inst.prompt.steps
        assert [steps[i - 1] for i in inst.answer] == order and tuple(inst.answer) != tuple(range(1, len(steps) + 1))


# ------------------------------------------------------------------ partition_pruning
def _prunes_to_one(sql: str, col: str, day: str) -> bool:
    """Фильтр — сравнение самой колонки партиционирования с константами, задающими ровно один день."""
    where = sql.split("WHERE ", 1)[1].rstrip(";")
    if re.fullmatch(rf"{col} = DATE '{day}'", where):
        return True
    if re.fullmatch(rf"{col} BETWEEN DATE '{day}' AND DATE '{day}'", where):
        return True
    if re.fullmatch(rf"{col} IN \(DATE '{day}'\)", where):
        return True
    m = re.fullmatch(rf"{col} >= DATE '{day}' AND {col} < DATE '(\d{{4}}-\d{{2}}-\d{{2}})'", where)
    return bool(m) and m.group(1) > day
    

def test_partition_pruning_key():
    for seed in range(200):
        inst = make("da.quality.partition_pruning", seed)
        col = re.search(r"партиционирована по колонке (\w+)", inst.prompt.text).group(1)
        day = re.search(r"за (\d{4}-\d{2}-\d{2})", inst.prompt.text).group(1)
        good = [i for i, o in enumerate(inst.prompt.options) if _prunes_to_one(o, col, day)]
        assert good == [inst.answer]


# ------------------------------------------------------------------ backfill_order
BACKFILL_CUES = ("Приостановить", "Пересчитать", "Сверить", "подменить", "Возобновить")


def test_backfill_order_key():
    for seed in range(200):
        inst = make("da.quality.backfill_order", seed)
        steps = inst.prompt.steps
        stage = [next(i for i, cue in enumerate(BACKFILL_CUES) if cue in s) for s in steps]
        assert sorted(stage) == list(range(5))
        assert [stage[i - 1] for i in inst.answer] == list(range(5)) and tuple(inst.answer) != (1, 2, 3, 4, 5)


# ------------------------------------------------------------------ exactly_once_sink / contract_breaking
@pytest.mark.parametrize(("code", "correct", "wrong"), [
    ("da.quality.exactly_once_sink", "EXACTLY_ONCE_CORRECT", "EXACTLY_ONCE_WRONG"),
])
def test_table_mcq_key(code, correct, wrong):
    for seed in range(200):
        inst = make(code, seed)
        key = inst.prompt.options[inst.answer]
        assert key in getattr(dq, correct)
        assert all(o in getattr(dq, wrong) for i, o in enumerate(inst.prompt.options) if i != inst.answer)


def test_contract_breaking_key():
    kinds = set()
    for seed in range(200):
        inst = make("da.quality.contract_breaking", seed)
        fields = dict(re.findall(r"^  - name: (\w+)\n    type: (\w+)", inst.prompt.code, re.M))
        breaking = []
        for i, o in enumerate(inst.prompt.options):
            if m := re.search(r"Удалить поле (\w+)", o):
                assert m.group(1) in fields
                breaking.append(i)
                kinds.add("remove")
            elif m := re.search(r"Переименовать поле (\w+) в (\w+)", o):
                assert m.group(1) in fields
                breaking.append(i)
                kinds.add("rename")
            elif m := re.search(r"Сменить тип поля (\w+) с (\w+) на (\w+)", o):
                assert fields[m.group(1)] == m.group(2)
                breaking.append(i)  # несовместимая смена типа (расширений типа среди вариантов нет)
                kinds.add("type")
        assert breaking == [inst.answer]
    assert kinds == {"remove", "rename", "type"}


def test_contract_breaking_verb_heuristic_is_weak():
    """«Выбери вариант с глаголом Удалить / Переименовать» угадывает не чаще 60%: такие глаголы есть и у безопасных изменений."""
    hits = 0
    for seed in range(400):
        inst = make("da.quality.contract_breaking", seed)
        destructive = [i for i, o in enumerate(inst.prompt.options) if o.split()[0] in ("Удалить", "Переименовать")]
        hits += destructive == [inst.answer]
    assert hits / 400 <= 0.6, hits / 400


def test_partition_pruning_aggregate_fits_table():
    for seed in range(200):
        inst = make("da.quality.partition_pruning", seed)
        table = re.search(r"Таблица (\w+)", inst.prompt.text).group(1)
        agg = re.search(r"SELECT (.+?) FROM", inst.prompt.options[0]).group(1)
        assert agg in dq.PRUNE_AGGREGATES[table]



def test_backfill_first_step_freezes_writers():
    """Первым идёт остановка загрузок, пишущих в витрину: иначе пересчёт читает «движущуюся» цель."""
    for seed in range(100):
        inst = make("da.quality.backfill_order", seed)
        first = inst.prompt.steps[inst.answer[0] - 1]
        assert any(w in first for w in ("загрузк", "пишущ", "пишут"))


def test_exactly_once_sink_grammar():
    for seed in range(200):
        t = make("da.quality.exactly_once_sink", seed).prompt.text
        assert not re.search(r"в (витрину|таблицу фактов|хранилище|PostgreSQL) появляются", t) or \
            "в хранилище появляются" in t or "в PostgreSQL появляются" in t, t
        assert re.search(r"пишет результат в \S+", t)


def test_late_data_delay_exceeds_a_day():
    for seed in range(200):
        t = make("da.quality.late_data", seed).prompt.text
        assert int(re.search(r"опозданием до (\d+) ч", t).group(1)) in (48, 72)


def test_partition_pruning_no_equivalent_cast_pair():
    for seed in range(300):
        opts = make("da.quality.partition_pruning", seed).prompt.options
        assert sum("CAST(" in o for o in opts) <= 1  # нет двух равносильных дистракторов (урок 11)


def test_contract_breaking_has_no_type_widening():
    for seed in range(200):
        opts = make("da.quality.contract_breaking", seed).prompt.options
        widenings = {("int", "bigint"), ("smallint", "int"), ("real", "double")}
        changes = [re.search(r"с (\w+) на (\w+)$", o) for o in opts]
        assert not any(m and (m.group(1), m.group(2)) in widenings for m in changes)


def test_iqr_context_keeps_capitals():
    for seed in range(100):
        t = make("da.quality.iqr_outliers", seed).prompt.text
        assert "api," not in t and "Api" not in t


def test_null_wording_matches_rendered_cells():
    """Пустая ячейка отображается как NULL: тексты не говорят о «пустых» ячейках."""
    for code in ("da.quality.null_share",):
        for seed in range(50):
            assert "Пустые ячейки" not in make(code, seed).prompt.text


def test_dedupe_zero_key_is_rare():
    zeros = sum(make("da.sql.dedupe_row_number", s).answer == 0 for s in range(300))
    assert zeros <= 0.12 * 300, zeros
