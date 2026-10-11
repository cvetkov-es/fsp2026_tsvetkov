"""Семантические тесты Data · Python для данных: ключи pandas-заданий сверяются с настоящим pandas (dev)."""
import ast
import re
from collections import Counter

import pandas as pd
import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family

from .._bank_helpers import area_codes, make

AREA_CODES = area_codes("python", "data")


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)
    assert r.space_estimate >= 50_000, (code, r.space_estimate)


def _df(table) -> pd.DataFrame:
    return pd.DataFrame(list(table.rows), columns=list(table.columns))


# ------------------------------------------------------------------ comprehension_output
def test_comprehension_output_key():
    for seed in range(200):
        inst = make("da.python.comprehension_output", seed)
        tree = ast.parse(inst.prompt.code)
        xs = ast.literal_eval(tree.body[0].value)
        comp = tree.body[1].value
        # независимо: элемент и условие включения вычисляются интерпретатором по их собственным выражениям
        elt, cond = ast.unparse(comp.elt), ast.unparse(comp.generators[0].ifs[0])
        var = comp.generators[0].target.id
        want = [eval(elt, {}, {var: x}) for x in xs if eval(cond, {}, {var: x})]  # noqa: S307 — наш шаблон
        assert inst.answer == str(want)


# ------------------------------------------------------------------ dict_count_output
def test_dict_count_output_key():
    for seed in range(200):
        inst = make("da.python.dict_count_output", seed)
        tree = ast.parse(inst.prompt.code)
        words = ast.literal_eval(tree.body[0].value)
        asked = re.search(r"print\(\w+\['(\w+)'\]\)", inst.prompt.code).group(1)
        assert inst.answer == str(Counter(words)[asked]) and Counter(words)[asked] >= 2


# ------------------------------------------------------------------ pandas_filter_len
def test_pandas_filter_len_key():
    for seed in range(200):
        inst = make("da.python.pandas_filter_len", seed)
        df = _df(inst.prompt.tables[0])
        expr = re.search(r"print\(len\((df\[.+\])\)\)", inst.prompt.code).group(1)
        want = len(eval(expr, {"df": df}))  # noqa: S307 — настоящий pandas на нашем выражении
        assert inst.answer == want


# ------------------------------------------------------------------ groupby_size
def test_groupby_size_key():
    for seed in range(200):
        inst = make("da.python.groupby_size", seed)
        df = _df(inst.prompt.tables[0])
        col, value = re.search(r"groupby\('(\w+)'\)\.size\(\)\['(\w+)'\]", inst.prompt.code).groups()
        assert inst.answer == int(df.groupby(col).size()[value])


# ------------------------------------------------------------------ loc_vs_iloc_rows
def test_loc_vs_iloc_rows_key():
    for seed in range(200):
        inst = make("da.python.loc_vs_iloc_rows", seed)
        df = _df(inst.prompt.tables[0])  # индекс по умолчанию — RangeIndex 0..N-1
        a, b = (int(x) for x in re.search(r"df\.loc\[(\d+):(\d+)\]", inst.prompt.code).groups())
        assert f"df.iloc[{a}:{b}]" in inst.prompt.code and "print(len(part_loc))" in inst.prompt.code
        assert inst.answer == len(df.loc[a:b]) == len(df.iloc[a:b]) + 1  # loc включает конец среза


# ------------------------------------------------------------------ left_merge_rows
def test_left_merge_rows_key():
    for seed in range(200):
        inst = make("da.python.left_merge_rows", seed)
        left, right = (_df(t) for t in inst.prompt.tables)
        key = re.search(r"on='(\w+)'", inst.prompt.code).group(1)
        merged = pd.merge(left, right, on=key, how="left")
        assert inst.answer == len(merged)
        assert right[key].duplicated().any()  # дубликаты ключа справа размножают строки
        assert inst.answer != len(left)


# ------------------------------------------------------------------ groupby_dropna
def test_groupby_dropna_key():
    forms = set()
    for seed in range(200):
        inst = make("da.python.groupby_dropna", seed)
        df = _df(inst.prompt.tables[0])
        assert df["city"].isna().sum() >= 1
        expr = re.search(r"print\((.+)\)$", inst.prompt.code, re.M).group(1)
        assert inst.answer == int(eval(expr, {"df": df}))  # noqa: S307 — настоящий pandas, dropna=True по умолчанию
        forms.add("len" if expr.startswith("len(") else "sum")
    assert forms == {"len", "sum"}


# ------------------------------------------------------------------ chained_assignment
def test_chained_assignment_key():
    for seed in range(100):
        inst = make("da.python.chained_assignment", seed)
        df = _df(inst.prompt.tables[0])
        before = df.copy()
        stmt = re.search(r"^(df\[df\..+\]\['status'\] = '\w+')$", inst.prompt.code, re.M).group(1)
        with pytest.warns(Warning):  # pandas предупреждает о цепочном присваивании
            exec(stmt, {"df": df})  # noqa: S102 — наш шаблон
        pd.testing.assert_frame_equal(df, before)  # df не изменился
        key = inst.prompt.options[inst.answer]
        assert key.startswith("Нет") and ".loc[" in key


# ------------------------------------------------------------------ vectorize_vs_apply
def test_vectorize_vs_apply_key():
    from app.assessment.bank.families import data_python as dp
    for seed in range(200):
        inst = make("da.python.vectorize_vs_apply", seed)
        key = inst.prompt.options[inst.answer]
        assert key in dp.VECTOR_CORRECT
        assert all(o in dp.VECTOR_WRONG for i, o in enumerate(inst.prompt.options) if i != inst.answer)
        assert ".apply(" in inst.prompt.code and "axis=1" in inst.prompt.code


# ------------------------------------------------------------------ pivot_cell
def test_pivot_cell_key():
    multi = 0
    for seed in range(200):
        inst = make("da.python.pivot_cell", seed)
        df = _df(inst.prompt.tables[0])
        code = inst.prompt.code
        index, columns, values = re.search(r"index='(\w+)', columns='(\w+)', values='(\w+)'", code).groups()
        assert "aggfunc='sum'" in code
        row, col = re.search(r"pt\.loc\['(\w+)', '(\w+)'\]", code).groups()
        pt = df.pivot_table(index=index, columns=columns, values=values, aggfunc="sum")
        assert inst.answer == float(pt.loc[row, col])
        multi += ((df[index] == row) & (df[columns] == col)).sum() >= 2
    assert multi >= 60  # в ячейке часто несколько строк: агрегация важна


# ------------------------------------------------------------------ rolling_mean_at
def test_rolling_mean_at_key():
    for seed in range(200):
        inst = make("da.python.rolling_mean_at", seed)
        xs = ast.literal_eval(re.search(r"pd\.Series\((\[.+\])\)", inst.prompt.code).group(1))
        w, i = (int(x) for x in re.search(r"rolling\((\d+)\)\.mean\(\)\.iloc\[(\d+)\]", inst.prompt.code).groups())
        value = pd.Series(xs).rolling(w).mean().iloc[i]
        assert i >= w - 1 and not pd.isna(value)
        assert inst.answer == round(float(value), 2)


# ------------------------------------------------------------------ category_dtype
def test_category_dtype_key():
    from app.assessment.bank.families import data_python as dp
    for seed in range(200):
        inst = make("da.python.category_dtype", seed)
        key = inst.prompt.options[inst.answer]
        assert key in dp.CATEGORY_CORRECT and "category" in key
        assert all(o in dp.CATEGORY_WRONG for i, o in enumerate(inst.prompt.options) if i != inst.answer)


# ------------------------------------------------------------------ float_sum_output
def test_float_sum_output_key():
    seen = set()
    for seed in range(200):
        inst = make("da.python.float_sum_output", seed)
        env = {}
        exec(inst.prompt.code.replace("print(", "result = ("), {}, env)  # noqa: S102 — наш шаблон, CPython float
        assert inst.answer == " ".join(str(v) for v in env["result"])
        seen.add(inst.answer)
    assert len(seen) >= 3



def test_float_sum_equality_is_derivable():
    """== выводится рассуждением: двоичные дроби (0.5, 0.25, …) складываются точно, десятичные (0.1, 1.1, …) — нет;
    сравнения со знаком ошибки (>) нет — его нельзя вывести за разумное время."""
    for seed in range(300):
        code = make("da.python.float_sum_output", seed).prompt.code
        step = float(re.search(r"^\w+ = (\d+\.\d+)$", code, re.M).group(1))
        assert ">" not in code.split("print(")[1] and "<" in code.split("print(")[1]
        env = {}
        exec(code.replace("print(", "result = ("), {}, env)  # noqa: S102 — наш шаблон
        exact = (step * 2**10).is_integer()
        checks = code.split("print(")[1]
        eq_first = checks.index("==") < checks.index("abs(")
        eq_value = env["result"][0 if eq_first else 1]
        assert eq_value is exact, (step, code)


def test_vectorize_apply_timing_is_realistic():
    for seed in range(200):
        code = make("da.python.vectorize_vs_apply", seed).prompt.code
        rows = float(re.search(r"# df: ([\d.]+) млн строк", code).group(1))
        secs = float(re.search(r"axis=1\)  # ([\d.]+) с", code).group(1))
        assert 8 <= secs / rows <= 25  # apply(axis=1): порядка десятков секунд на миллион строк



def test_groupby_dropna_wording_matches_rendered_cells():
    for seed in range(50):
        assert "пустые значения" not in make("da.python.groupby_dropna", seed).prompt.code
