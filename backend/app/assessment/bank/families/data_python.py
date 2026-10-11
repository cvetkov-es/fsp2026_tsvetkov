"""Семейства Data/Analytics · Python для данных.

Ключи pandas-заданий вычисляются эквивалентным кодом на чистом Python (или в SQLite): pandas в рабочий образ
не входит. Семантические тесты сверяют ключи с настоящим pandas (dev-зависимость). Используется только
устойчивая и документированная семантика pandas (см. глобальные ограничения плана).
"""
import math
import operator
import random
from collections import Counter

from app.assessment.bank.base import Generated, Prompt, Table, family, mcq
from app.assessment.bank.pysnippet import run_python_snippet
from app.assessment.bank.sqlite_sandbox import run_query, setup_sql

LIST_NAMES = ("xs", "nums", "values", "data", "scores", "items")
VAR_NAMES = ("x", "n", "v", "item")


def _output(code: str, hint: str, radicals: tuple) -> Generated:
    return Generated("text", Prompt(text="Что выведет программа?", code=code, language="python", answer_hint=hint),
                     run_python_snippet(code), radicals)


# --- da.python.comprehension_output -------------------------------------------------------
COMP_ELEMENTS = ("{v} * {k}", "{v} + {k}", "{v} ** 2", "{v} // {k}", "{v} - {k}")
COMP_CONDITIONS = ("{v} % {m} == 0", "{v} > {t}", "{v} < {t}", "{v} % 2 == 1")


@family(code="da.python.comprehension_output", specialization="data", area="python", level=1, fmt="output",
        space_size=len(LIST_NAMES) * len(VAR_NAMES) * len(COMP_ELEMENTS) * len(COMP_CONDITIONS) * 30**5,
        median_time_s=35)
def comprehension_output(rng: random.Random) -> Generated:
    name, v = rng.choice(LIST_NAMES), rng.choice(VAR_NAMES)
    while True:
        xs = [rng.randint(1, 30) for _ in range(rng.randint(5, 8))]
        elt = rng.choice(COMP_ELEMENTS).format(v=v, k=rng.randint(2, 5))
        cond = rng.choice(COMP_CONDITIONS).format(v=v, m=rng.choice((2, 3)), t=rng.randint(5, 25))
        code = f"{name} = {xs}\nresult = [{elt} for {v} in {name} if {cond}]\nprint(result)"
        out = run_python_snippet(code)
        if out != "[]" and out.count(",") + 1 < len(xs):  # фильтр отбрасывает часть, но не всё
            break
    return _output(code, "Ровно то, что напечатает print, например: [1, 2, 3]", ("list_comprehension",))


# --- da.python.dict_count_output -----------------------------------------------------------
WORD_POOLS = (("ok", "error", "warn", "info"), ("apple", "pear", "plum", "kiwi"), ("new", "paid", "sent", "done"),
              ("red", "green", "blue", "black"))
COUNT_VARS = (("words", "w", "counts"), ("events", "e", "freq"), ("tags", "t", "seen"), ("items", "x", "tally"))


@family(code="da.python.dict_count_output", specialization="data", area="python", level=1, fmt="output",
        space_size=len(WORD_POOLS) * len(COUNT_VARS) * 4**8 * 4, median_time_s=35)
def dict_count_output(rng: random.Random) -> Generated:
    pool = rng.choice(WORD_POOLS)
    seq, var, acc = rng.choice(COUNT_VARS)
    while True:
        words = [rng.choice(pool) for _ in range(rng.randint(6, 10))]
        asked = [w for w, c in Counter(words).items() if c >= 2]
        if asked:
            break
    code = "\n".join([f"{seq} = {words}", f"{acc} = {{}}", f"for {var} in {seq}:",
                      f"    {acc}[{var}] = {acc}.get({var}, 0) + 1", f"print({acc}['{rng.choice(sorted(asked))}'])"])
    return _output(code, "Ровно то, что напечатает print: одно число", ("dict_get_count",))


# --- da.python.pandas_filter_len -----------------------------------------------------------
CITIES = ("Казань", "Пермь", "Томск", "Самара", "Омск")
STATUSES = ("paid", "new", "canceled")
OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt}


def _orders_table(rng: random.Random, n: int) -> Table:
    rows = tuple((i + 1, rng.choice(CITIES), rng.choice(STATUSES), rng.randrange(100, 2001, 50)) for i in range(n))
    return Table("df", ("id", "city", "status", "amount"), rows)


@family(code="da.python.pandas_filter_len", specialization="data", area="python", level=2, fmt="calc",
        space_size=10**9, median_time_s=50)
def pandas_filter_len(rng: random.Random) -> Generated:
    while True:
        table = _orders_table(rng, rng.randint(8, 12))
        col, values = rng.choice((("status", STATUSES), ("city", CITIES)))
        value = rng.choice(values)
        op = rng.choice(sorted(OPS))
        t = rng.choice([r[3] for r in table.rows])  # порог совпадает со значением в таблице
        idx = table.columns.index(col)
        count = sum(r[idx] == value and OPS[op](r[3], t) for r in table.rows)
        if count >= 1:
            break
    code = f"# df — таблица ниже\nprint(len(df[(df.amount {op} {t}) & (df.{col} == '{value}')]))"
    return Generated("number", Prompt(text="Что выведет программа?", code=code, language="python", tables=(table,),
                                      answer_hint="Целое число"), count, ("boolean_mask_len",))


# --- da.python.groupby_size ----------------------------------------------------------------------
@family(code="da.python.groupby_size", specialization="data", area="python", level=2, fmt="calc",
        space_size=10**9, median_time_s=50)
def groupby_size(rng: random.Random) -> Generated:
    table = _orders_table(rng, rng.randint(8, 12))
    col = rng.choice(("status", "city"))
    idx = table.columns.index(col)
    counts = Counter(r[idx] for r in table.rows)
    value = rng.choice(sorted(counts))
    code = f"# df — таблица ниже\nprint(df.groupby('{col}').size()['{value}'])"
    return Generated("number", Prompt(text="Что выведет программа?", code=code, language="python", tables=(table,),
                                      answer_hint="Целое число"), counts[value], ("groupby_size",))


# --- da.python.loc_vs_iloc_rows ----------------------------------------------------------------------
@family(code="da.python.loc_vs_iloc_rows", specialization="data", area="python", level=2, fmt="calc",
        space_size=10**9, median_time_s=50)
def loc_vs_iloc_rows(rng: random.Random) -> Generated:
    while True:
        n = rng.randint(6, 15)
        a = rng.randint(0, n - 3)
        b = rng.randint(a + 1, n - 1)
        answer = b - a + 1  # loc по меткам включает конец среза, iloc по позициям — нет
        if answer not in (a, b, n):
            break
    table = _orders_table(rng, n)
    code = "\n".join(["# df — таблица ниже; индекс по умолчанию: 0, 1, 2, …", f"part_loc = df.loc[{a}:{b}]",
                      f"part_iloc = df.iloc[{a}:{b}]", "print(len(part_loc))"])
    return Generated("number", Prompt(text="Что выведет программа?", code=code, language="python", tables=(table,),
                                      answer_hint="Целое число"), answer, ("loc_inclusive_slice",))


# --- da.python.left_merge_rows ----------------------------------------------------------------------------
@family(code="da.python.left_merge_rows", specialization="data", area="python", level=3, fmt="calc",
        space_size=10**9, median_time_s=75)
def left_merge_rows(rng: random.Random) -> Generated:
    key = rng.choice(("user_id", "client_id"))
    while True:
        ids = rng.sample(range(1, 100), rng.randint(4, 7))
        left = Table("users", (key, "name"), tuple((i, rng.choice(("Анна", "Олег", "Ирина", "Павел", "Мария"))) for i in ids))
        right = Table("orders", ("order_id", key, "amount"),
                      tuple((j + 1, rng.choice(ids + [rng.randint(100, 120)]), rng.randrange(100, 3001, 100))
                            for j in range(rng.randint(4, 9))))
        keys = [r[1] for r in right.rows]
        # ключ — эквивалентный LEFT JOIN в SQLite (pandas в рабочем образе нет)
        rows = run_query(setup_sql(left, right), f"SELECT * FROM users u LEFT JOIN orders o ON o.{key} = u.{key};")
        if len(keys) > len(set(keys)) and len(rows) != len(left.rows):
            break
    code = f"# users и orders — таблицы ниже\nmerged = pd.merge(users, orders, on='{key}', how='left')\nprint(len(merged))"
    return Generated("number", Prompt(text="Что выведет программа?", code=code, language="python",
                                      tables=(left, right), answer_hint="Целое число"), len(rows), ("left_merge",))


# --- da.python.groupby_dropna --------------------------------------------------------------------------
@family(code="da.python.groupby_dropna", specialization="data", area="python", level=3, fmt="calc",
        space_size=10**9, median_time_s=70)
def groupby_dropna(rng: random.Random) -> Generated:
    while True:
        table = _orders_table(rng, rng.randint(8, 12))
        rows = [list(r) for r in table.rows]
        for r in rng.sample(rows, rng.randint(1, 3)):
            r[1] = None  # пропуск в ключе группировки
        cities = [r[1] for r in rows]
        groups = len({c for c in cities if c is not None})
        counted = sum(c is not None for c in cities)  # строки с NaN-ключом в группы не попадают
        form = rng.choice(("len", "sum"))
        answer = groups if form == "len" else counted
        if answer != {"len": len(set(cities)), "sum": len(cities)}[form]:
            break
    table = Table("df", table.columns, tuple(tuple(r) for r in rows))
    expr = "len(df.groupby('city').size())" if form == "len" else "df.groupby('city').size().sum()"
    code = f"# df — таблица ниже; NULL в колонке city — пропуски (в pandas — NaN)\nprint({expr})"
    return Generated("number", Prompt(text="Что выведет программа?", code=code, language="python", tables=(table,),
                                      answer_hint="Целое число"), answer, ("groupby_dropna",))


# --- da.python.chained_assignment ----------------------------------------------------------------------------
CHAINED_CORRECT = (
    "Нет: df[маска] — копия, и меняется она, а не df; нужно df.loc[маска, 'status'] = значение",
    "Нет: изменится временная копия, df останется прежним; правильно — через df.loc[маска, 'status']",
)
CHAINED_WRONG = (
    "Да: у строк, прошедших фильтр, в df поменяется status — это обычный способ обновить часть строк",
    "Да, но во всех строках сразу: присваивание по имени колонки не учитывает фильтр df[маска] вовсе",
    "Нет: pandas запрещает менять строковые колонки, сначала их нужно привести к типу category",
    "Будет KeyError: после фильтрации колонка status в результате недоступна",
)


@family(code="da.python.chained_assignment", specialization="data", area="python", level=3, fmt="mcq",
        space_size=10**9, median_time_s=70)
def chained_assignment(rng: random.Random) -> Generated:
    table = _orders_table(rng, rng.randint(6, 10))
    t = rng.choice([r[3] for r in table.rows])
    new = rng.choice(("vip", "priority", "checked", "archived"))
    code = f"# df — таблица ниже\ndf[df.amount > {t}]['status'] = '{new}'"
    text = "Изменится ли df после выполнения кода (pandas 2.x и новее)?"
    return mcq(rng, text, rng.choice(CHAINED_CORRECT), rng.sample(CHAINED_WRONG, 3), code=code, language="python",
               tables=(table,))


# --- da.python.vectorize_vs_apply --------------------------------------------------------------------------------
VECTOR_CASES = (("price", "qty", "*", "total"), ("revenue", "cost", "-", "profit"), ("clicks", "views", "/", "ctr"),
                ("base", "bonus", "+", "salary"))
VECTOR_CORRECT = (
    "Векторная операция идёт в скомпилированном коде над массивами, а apply вызывает Python-функцию на строку",
    "apply с axis=1 вызывает Python-функцию для каждой строки, а векторная операция — один проход в numpy",
)
VECTOR_WRONG = (
    "apply перед обработкой каждой строки копирует весь DataFrame целиком, отсюда и разница во времени",
    "Векторная операция автоматически распределяется по всем ядрам процессора, а apply работает в одном потоке",
    "apply по умолчанию сортирует данные по индексу перед вызовом функции, и эта сортировка занимает время",
    "Разница в кэшировании: результат векторной операции pandas запоминает и при повторном запуске не считает",
)


@family(code="da.python.vectorize_vs_apply", specialization="data", area="python", level=4, fmt="mcq",
        space_size=len(VECTOR_CASES) * 91 * 30 * len(VECTOR_CORRECT) * 4 * 24, median_time_s=80)
def vectorize_vs_apply(rng: random.Random) -> Generated:
    a, b, op, out = rng.choice(VECTOR_CASES)
    rows_m = rng.randint(1, 91) / 10
    slow = round(rows_m * rng.uniform(8, 25), 1)  # apply(axis=1): десятки секунд на миллион строк
    code = "\n".join([f"# df: {rows_m} млн строк", f"df['{out}'] = df.apply(lambda r: r.{a} {op} r.{b}, axis=1)"
                      f"  # {slow} с", f"df['{out}'] = df.{a} {op} df.{b}  # доли секунды"])
    return mcq(rng, "Почему второй вариант в десятки раз быстрее первого?", rng.choice(VECTOR_CORRECT),
               rng.sample(VECTOR_WRONG, 3), code=code, language="python")


# --- da.python.pivot_cell ----------------------------------------------------------------------------------------
REGIONS = ("north", "south", "east", "west")
QUARTERS = ("q1", "q2", "q3", "q4")


@family(code="da.python.pivot_cell", specialization="data", area="python", level=4, fmt="calc",
        space_size=10**9, median_time_s=100)
def pivot_cell(rng: random.Random) -> Generated:
    while True:
        regions, quarters = rng.sample(REGIONS, rng.randint(2, 3)), rng.sample(QUARTERS, rng.randint(2, 3))
        rows = tuple((i + 1, rng.choice(regions), rng.choice(quarters), rng.randrange(100, 5001, 100))
                     for i in range(rng.randint(8, 14)))
        cells = Counter((r[1], r[2]) for r in rows)
        multi = [c for c, k in cells.items() if k >= 2]
        if multi:
            break
    row, col = rng.choice(sorted(multi)) if rng.random() < 0.6 else rng.choice(sorted(cells))
    value = sum(r[3] for r in rows if (r[1], r[2]) == (row, col))  # aggfunc='sum' по строкам ячейки
    table = Table("df", ("id", "region", "quarter", "amount"), rows)
    code = ("# df — таблица ниже\npt = df.pivot_table(index='region', columns='quarter', values='amount', "
            f"aggfunc='sum')\nprint(pt.loc['{row}', '{col}'])")
    return Generated("number", Prompt(text="Какое число выведет программа?", code=code, language="python",
                                      tables=(table,), answer_hint="Число"), value, ("pivot_sum",))


# --- da.python.rolling_mean_at ----------------------------------------------------------------------------------
@family(code="da.python.rolling_mean_at", specialization="data", area="python", level=4, fmt="calc",
        space_size=100**6 * 4, median_time_s=90)
def rolling_mean_at(rng: random.Random) -> Generated:
    while True:
        xs = [rng.randint(1, 100) for _ in range(rng.randint(6, 10))]
        i = rng.randint(2, len(xs) - 1)
        mean = sum(xs[i - 2:i + 1]) / 3  # окно из трёх значений, заканчивающееся позицией i
        if abs((mean * 100) % 1 - 0.5) > 0.01:
            break
    name = rng.choice(("s", "sales", "visits", "temps"))
    code = f"{name} = pd.Series({xs})\nprint(round({name}.rolling(3).mean().iloc[{i}], 2))"
    return Generated("number", Prompt(text="Что выведет программа?", code=code, language="python",
                                      answer_hint="Число с двумя знаками после запятой"), round(mean, 2),
                     ("rolling_mean",))


# --- da.python.category_dtype --------------------------------------------------------------------------------------
CATEGORY_COLUMNS = ("city", "country", "device", "plan", "status", "browser")
CATEGORY_CORRECT = (
    "Перевести колонку в category: строки хранятся один раз в словаре, в колонке — целые коды",
    "astype('category'): уникальные значения хранятся отдельно, а в строках — короткие коды",
)
CATEGORY_WRONG = (
    "Применить .str.strip() ко всей колонке: основную часть памяти занимают пробелы по краям строк",
    "Отсортировать DataFrame по этой колонке: одинаковые строки рядом хранятся компактнее",
    "Перевести колонку в float64: числа с плавающей точкой занимают меньше места, чем любые строки",
    "Сбросить индекс через reset_index(drop=True): основную память в DataFrame занимает индекс",
)


@family(code="da.python.category_dtype", specialization="data", area="python", level=5, fmt="mcq",
        space_size=len(CATEGORY_COLUMNS) * 50 * 199 * len(CATEGORY_CORRECT) * math.comb(len(CATEGORY_WRONG), 3) * 24,
        median_time_s=110)
def category_dtype(rng: random.Random) -> Generated:
    col = rng.choice(CATEGORY_COLUMNS)
    rows_m = rng.randint(1, 50)
    uniques = rng.randint(2, 200)
    mem = round(rows_m * rng.uniform(55, 70))
    code = "\n".join([f"df.shape              # ({rows_m}_000_000, 12)", f"df['{col}'].dtype      # object",
                      f"df['{col}'].nunique()  # {uniques}",
                      f"df['{col}'].memory_usage(deep=True) / 2**20  # ≈ {mem} МБ"])
    text = (f"Колонка {col} занимает основную часть памяти DataFrame. Как сильнее всего уменьшить её объём, не "
            "теряя информации?")
    return mcq(rng, text, rng.choice(CATEGORY_CORRECT), rng.sample(CATEGORY_WRONG, 3), code=code, language="python")


# --- da.python.float_sum_output ----------------------------------------------------------------------------------------
# двоичные дроби складываются точно; десятичные — с ошибкой округления (экземпляры, где ошибки случайно нет, отбрасываются)
FLOAT_EXACT_STEPS = (0.5, 0.25, 0.125, 0.75, 0.375, 1.5)
FLOAT_INEXACT_STEPS = (0.1, 0.2, 0.3, 0.7, 1.1)
FLOAT_STEP_NAMES = ("step", "delta", "dx", "inc")
FLOAT_TOLERANCES = ("1e-9", "1e-6", "1e-12")
FLOAT_STARTS = (0, 1, 2, 5, 10)


@family(code="da.python.float_sum_output", specialization="data", area="python", level=5, fmt="output",
        # шаг (точный или нет) × повторы × старт × имена × допуск × порядок двух сравнений
        space_size=(len(FLOAT_EXACT_STEPS) * 29 + len(FLOAT_INEXACT_STEPS) * 15) * len(FLOAT_STARTS) * 5
        * len(FLOAT_STEP_NAMES) * len(FLOAT_TOLERANCES) * 2, median_time_s=110)
def float_sum_output(rng: random.Random) -> Generated:
    name, st, tol = rng.choice(("total", "acc", "s", "result", "running")), rng.choice(FLOAT_STEP_NAMES), \
        rng.choice(FLOAT_TOLERANCES)
    exact = rng.random() < 0.5
    while True:
        step = rng.choice(FLOAT_EXACT_STEPS if exact else FLOAT_INEXACT_STEPS)
        n, start = rng.randint(2, 30), rng.choice(FLOAT_STARTS)
        target = f"{round(start + n * step, 10):g}"
        if "." not in target:
            target += ".0"
        acc = float(start)
        for _ in range(n):
            acc += step
        if (acc == float(target)) == exact:  # результат == совпадает с рассуждением «точно / неточно»
            break
    checks = [f"{name} == target", f"abs({name} - target) < {tol}"]
    rng.shuffle(checks)
    code = "\n".join([f"{st} = {step}", f"{name} = {float(start)}", f"for _ in range({n}):", f"    {name} += {st}",
                      f"target = {target}", f"print({', '.join(checks)})"])
    return _output(code, "Ровно то, что напечатает print: два значения True / False через пробел",
                   ("float_accumulation",))
