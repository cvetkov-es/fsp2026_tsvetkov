import math
import random

from app.assessment.bank.base import SHUFFLES, Generated, Prompt, family, mcq, template_fields
from app.assessment.bank.pysnippet import run_python_snippet

FN = ("window_sums", "sliding_sums", "rolling_totals", "chunk_sums")
XS = ("xs", "values", "nums", "items")
KS = ("k", "size", "width", "w")
RES = ("result", "out", "sums", "acc")
SV = ("s", "total", "cur", "tmp")
IJ = (("i", "j"), ("a", "b"), ("start", "pos"), ("left", "idx"))

TEMPLATE = (
    "def {fn}({xs}, {k}):",
    "    {res} = []",
    "    for {i} in range(len({xs}) - {k} + 1):",
    "        {s} = 0",
    "        for {j} in range({i}, {i} + {k}):",
    "            {s} += {xs}[{j}]",
    "        {res}.append({s})",
    "    return {res}",
)
# номер строки (с 1) → (как правильно, как с ошибкой)
MUTATIONS = {
    3: ("- {k} + 1)", "- {k})"),
    4: ("{s} = 0", "{s} = 1"),
    5: ("{i} + {k})", "{i} + {k} - 1)"),
    6: ("{xs}[{j}]", "{xs}[{i}]"),
}


def _correct(xs: list[int], k: int) -> list[int]:
    return [sum(xs[i:i + k]) for i in range(len(xs) - k + 1)]


@family(code="be.debug.window_sums_bug", specialization="backend", area="debug", level=3,
        fmt="bug", space_size=4**6 * 4 * 9**6 * 2, median_time_s=90)
def window_sums_bug(rng: random.Random) -> Generated:
    i, j = rng.choice(IJ)
    names = {"fn": rng.choice(FN), "xs": rng.choice(XS), "k": rng.choice(KS),
             "res": rng.choice(RES), "s": rng.choice(SV), "i": i, "j": j}
    line = rng.choice(sorted(MUTATIONS))
    good, bad = (p.format(**names) for p in MUTATIONS[line])
    correct = [t.format(**names) for t in TEMPLATE]
    lines = list(correct)
    lines[line - 1] = lines[line - 1].replace(good, bad)
    code = "\n".join(lines)
    for _ in range(20):  # пример должен проявлять ошибку
        xs = [rng.randint(1, 9) for _ in range(rng.randint(5, 7))]
        k = rng.randint(2, 3)
        call = f"{names['fn']}({xs}, {k})"
        if run_python_snippet(code + f"\nprint({call})") != str(_correct(xs, k)):
            break
    text = (f"Функция {names['fn']} должна вернуть суммы всех подряд идущих окон длины "
            f"{names['k']}. Пример: {call} == {_correct(xs, k)}\n"
            "В какой строке ошибка?")
    numbered = "\n".join(f"{n:>2}| {ln}" for n, ln in enumerate(lines, start=1))
    return Generated(
        "line",
        Prompt(text=text, code=code, language="python", answer_hint=f"Номер строки:\n{numbered}"),
        line, ("window_sums", len(lines), sum(a != b for a, b in zip(lines, correct, strict=True))),
    )


# ---------------------------------------------------------------------------
# План 03b: наполнение области debug
# ---------------------------------------------------------------------------
SERVICES = ("billing", "catalog", "orders", "auth", "search", "notifications", "payments", "reports",
            "profile", "delivery", "inventory", "pricing")


def _numbered(lines) -> str:
    return "\n".join(f"{n:>2}| {ln}" for n, ln in enumerate(lines, start=1))


def _line_answer(text: str, lines, key: int, radicals: tuple) -> Generated:
    """Задание «найди строку»: код в prompt.code, нумерация — в подсказке формата ответа."""
    return Generated(
        "line",
        Prompt(text=text, code="\n".join(lines), language="python",
               answer_hint=f"Номер строки:\n{_numbered(lines)}"),
        key, radicals,
    )


def _exposing_example(make_call, fixed: str, code: str, tries: int = 2000) -> tuple[str, str]:
    """Пример (вызов, ожидаемый вывод), на котором код с ошибкой даёт неверный результат.

    Ожидаемое считается исправленным кодом; случайные входы, на которых код с ошибкой падает
    (исключение) или совпадает с исправленным, отбрасываются."""
    for _ in range(tries):
        call = make_call()
        want = run_python_snippet(fixed + f"\nprint({call})")
        try:
            got = run_python_snippet(code + f"\nprint({call})")
        except Exception:  # noqa: BLE001 - код с ошибкой вправе падать: такой вход не годится для примера
            continue
        if got != want:
            return call, want
    raise RuntimeError("пример не проявил ошибку")  # pragma: no cover


# --- be.debug.traceback_line -----------------------------------------------------
TB_MODULES = ("main", "service", "loader", "handlers", "billing", "storage", "parser", "client",
              "checkout", "scheduler", "exporter", "validator")
TB_FUNCS = ("run", "process", "load_data", "handle", "apply_rules", "save_all", "build_report",
            "sync_state", "dispatch", "prepare", "finalize", "execute")
TB_DIRS = ("/srv/app", "/opt/service", "/home/deploy/project", "/app/src")
TB_ERRORS = (
    ("ValueError", "amount must be positive"), ("RuntimeError", "connection pool is exhausted"),
    ("TypeError", "unsupported discount type"), ("PermissionError", "access denied for role guest"),
    ("TimeoutError", "upstream did not respond"), ("ValueError", "invalid currency code"),
    ("RuntimeError", "worker queue is closed"), ("LookupError", "unknown account number"),
)
TB_LINE_MIN, TB_LINE_MAX = 3, 240


@family(code="be.debug.traceback_line", specialization="backend", area="debug", level=1,
        fmt="bug", median_time_s=40,
        space_size=(math.perm(len(TB_MODULES), 3) * math.perm(len(TB_FUNCS), 2) * len(TB_DIRS)
                    * len(TB_ERRORS) * len(SERVICES)
                    * math.perm(TB_LINE_MAX - TB_LINE_MIN + 1, 3)))
def traceback_line(rng: random.Random) -> Generated:
    m1, m2, m3 = rng.sample(TB_MODULES, 3)
    f2, f3 = rng.sample(TB_FUNCS, 2)
    base = rng.choice(TB_DIRS)
    l1, l2, l3 = rng.sample(range(TB_LINE_MIN, TB_LINE_MAX + 1), 3)
    exc, msg = rng.choice(TB_ERRORS)
    tb = "\n".join((
        "Traceback (most recent call last):",
        f'  File "{base}/{m1}.py", line {l1}, in <module>',
        f"    {f2}()",
        f'  File "{base}/{m2}.py", line {l2}, in {f2}',
        f"    {f3}()",
        f'  File "{base}/{m3}.py", line {l3}, in {f3}',
        f'    raise {exc}("{msg}")',
        f"{exc}: {msg}",
    ))
    text = (f"Скрипт сервиса «{rng.choice(SERVICES)}» завершился с ошибкой, вывод ниже. "
            f"На какой строке файла {m3}.py возникло исключение?")
    return Generated(
        "line", Prompt(text=text, code=tb, language="text", answer_hint="Номер строки"),
        l3, ("traceback", 3),
    )


# --- be.debug.loop_count_output --------------------------------------------------
LOOP_START_MIN, LOOP_START_MAX = -30, 30
LOOP_SPAN_MIN, LOOP_SPAN_MAX = 1, 90
LOOP_STEP_MAX = 9
LOOP_COUNTERS = ("count", "n", "total", "steps")
LOOP_VARS = ("i", "k", "x", "t")
LOOP_EMPTY_SHARE = 0.05  # доля экземпляров без итераций


@family(code="be.debug.loop_count_output", specialization="backend", area="debug", level=1,
        fmt="output", median_time_s=35,
        space_size=((LOOP_START_MAX - LOOP_START_MIN + 1) * (LOOP_SPAN_MAX - LOOP_SPAN_MIN + 1)
                    * LOOP_STEP_MAX * 2 * len(LOOP_COUNTERS) * len(LOOP_VARS)))
def loop_count_output(rng: random.Random) -> Generated:
    a = rng.randint(LOOP_START_MIN, LOOP_START_MAX)
    span = rng.randint(LOOP_SPAN_MIN, LOOP_SPAN_MAX)
    step = rng.randint(1, LOOP_STEP_MAX)
    if rng.random() < 0.5:
        step = -step
    empty = rng.random() < LOOP_EMPTY_SHARE
    b = a + (-span if empty else span) * (1 if step > 0 else -1)
    cnt, var = rng.choice(LOOP_COUNTERS), rng.choice(LOOP_VARS)
    code = (f"{cnt} = 0\nfor {var} in range({a}, {b}, {step}):\n    {cnt} += 1\nprint({cnt})")
    return Generated(
        "number",
        Prompt(text="Что выведет программа?", code=code, language="python",
               answer_hint="Целое число"),
        run_python_snippet(code), ("loop_count",),
    )


# --- be.debug.wrong_comparison_line ----------------------------------------------
CMP_FNS = ("check_batch", "audit_scores", "review_marks", "scan_readings", "verify_sizes", "screen_values")
CMP_XS = ("xs", "values", "nums", "items")
CMP_LOHI = (("lo", "hi"), ("low", "high"), ("lower", "upper"), ("floor", "ceil"))
CMP_X = ("x", "v", "item", "n")
CMP_CNT = ("cnt", "found", "hits", "k")
CMP_NEED = ("need", "quota", "minimum", "least")
CMP_TEMPLATE = (
    "def {fn}({xs}, {lo}, {hi}, {need}):",
    "    {cnt} = 0",
    "    for {x} in {xs}:",
    "        if {x} < {lo}:",
    "            continue",
    "        if {x} <= {hi}:",
    "            {cnt} += 1",
    "    return {cnt} >= {need}",
)
# номер строки (с 1) → (правильный оператор, оператор с ошибкой)
CMP_MUTATIONS = {4: ("<", "<="), 6: ("<=", "<"), 8: (">=", ">")}
CMP_X_MIN, CMP_X_MAX, CMP_LEN = 1, 15, 5
CMP_LO = (2, 6)
CMP_HI = (9, 14)
CMP_NEED_RANGE = (1, 4)


@family(code="be.debug.wrong_comparison_line", specialization="backend", area="debug", level=2,
        fmt="bug", median_time_s=55,
        # верхняя граница: пример дополнительно отбирается по проявлению ошибки
        space_size=(len(CMP_FNS) * len(CMP_XS) * len(CMP_LOHI) * len(CMP_X) * len(CMP_CNT) * len(CMP_NEED)
                    * len(CMP_MUTATIONS) * (CMP_X_MAX - CMP_X_MIN + 1) ** CMP_LEN
                    * (CMP_LO[1] - CMP_LO[0] + 1) * (CMP_HI[1] - CMP_HI[0] + 1)
                    * (CMP_NEED_RANGE[1] - CMP_NEED_RANGE[0] + 1)))
def wrong_comparison_line(rng: random.Random) -> Generated:
    lo, hi = rng.choice(CMP_LOHI)
    names = {"fn": rng.choice(CMP_FNS), "xs": rng.choice(CMP_XS), "lo": lo, "hi": hi,
             "need": rng.choice(CMP_NEED), "cnt": rng.choice(CMP_CNT), "x": rng.choice(CMP_X)}
    correct = [t.format(**names) for t in CMP_TEMPLATE]
    key = rng.choice(sorted(CMP_MUTATIONS))
    good, bad = CMP_MUTATIONS[key]
    lines = list(correct)
    lines[key - 1] = lines[key - 1].replace(f" {good} ", f" {bad} ", 1)
    code, fixed = "\n".join(lines), "\n".join(correct)
    def make_call():
        xs = [rng.randint(CMP_X_MIN, CMP_X_MAX) for _ in range(CMP_LEN)]
        args = (rng.randint(*CMP_LO), rng.randint(*CMP_HI), rng.randint(*CMP_NEED_RANGE))
        return f"{names['fn']}({xs}, {args[0]}, {args[1]}, {args[2]})"

    call, want = _exposing_example(make_call, fixed, code)
    text = (f"Функция {names['fn']} должна проверять, что в списке {names['xs']} не меньше {names['need']} "
            f"чисел из диапазона от {lo} до {hi} включительно.\nПример: {call} == {want}\n"
            "В какой строке ошибка?")
    return _line_answer(text, lines, key, ("wrong_comparison", len(lines)))


# --- be.debug.which_assert_fails -------------------------------------------------
WA_PAGES_TOTAL, WA_PAGES_PER = (1, 60), (2, 9)
WA_LIST_LEN, WA_LIST_VALUE = (3, 5), (1, 30)
WA_YEARS = (1600, 2999)
WA_LAST_TIES_MAX = 0.5  # доля проходящих списков, где последний элемент повторяет максимум
WA_TEMPLATES = (
    # (имена функции, параметры, строки кода) — функция с намеренной ошибкой на границе
    (("page_count", "pages_needed", "batches_for", "boxes_needed"),
     (("total", "per"), ("items", "size"), ("count", "cap")),
     ("def {fn}({a}, {b}):", "    return {a} // {b} + 1")),
    (("peak", "best_of", "highest", "top_value"),
     (("xs",), ("values",), ("nums",)),
     ("def {fn}({a}):", "    best = {a}[0]", "    for v in {a}[1:-1]:", "        if v > best:",
      "            best = v", "    return best")),
    (("is_leap", "leap_year", "has_feb_29", "long_year"),
     (("year",), ("y",), ("yr",)),
     ("def {fn}({a}):", "    if {a} % 400 == 0:", "        return True", "    return {a} % 4 == 0")),
)


def _wa_expected(t: int, args: tuple):
    """Правильное поведение (то, что проверяют assert'ы); сама функция в задании содержит ошибку."""
    if t == 0:
        return -(-args[0] // args[1])
    if t == 1:
        return max(args[0])
    y = args[0]
    return (y % 4 == 0 and y % 100 != 0) or y % 400 == 0


def _wa_args(rng: random.Random, t: int, fail: bool) -> tuple:
    """Кандидат во входы; класс (падает / не падает) потом определяется исполнением."""
    if t == 0:
        return (rng.randint(*WA_PAGES_TOTAL), rng.randint(*WA_PAGES_PER))
    if t == 1:
        n = rng.randint(*WA_LIST_LEN)
        if not fail and rng.random() < WA_LAST_TIES_MAX:
            # последний элемент равен максимуму, который есть и раньше: assert проходит (values[1:-1]
            # и values[0] максимум видят), а «ожидаемое = последний элемент» перестаёт выдавать падающий
            head = [rng.randint(*WA_LIST_VALUE) for _ in range(n - 1)]
            return ([*head, max(head)],)
        return ([rng.randint(*WA_LIST_VALUE) for _ in range(n)],)
    if fail:  # век, не кратный 400: исправная функция скажет False
        return (rng.choice(_WA_CENTURIES),)
    # проходящие годы: «круглые» (кратные 400 и десяткам), високосные и случайные — чтобы форма не выдавала ключ
    roll = rng.random()
    pool = (_WA_LEAP400 if roll < 0.3 else _WA_ROUND if roll < 0.5 else _WA_LEAPS if roll < 0.6 else None)
    return (rng.choice(pool) if pool else rng.randint(*WA_YEARS),)


_WA_YEAR_RANGE = range(WA_YEARS[0], WA_YEARS[1] + 1)
_WA_CENTURIES = tuple(y for y in _WA_YEAR_RANGE if y % 100 == 0 and y % 400)
_WA_LEAP400 = tuple(y for y in _WA_YEAR_RANGE if y % 400 == 0)
_WA_ROUND = tuple(y for y in _WA_YEAR_RANGE if y % 10 == 0 and y % 100)
_WA_LEAPS = tuple(y for y in _WA_YEAR_RANGE if y % 4 == 0 and y % 100)
# размеры классов входов для честной оценки пространства (нижняя оценка)
_WA_FAIL = (
    sum(1 for a in range(WA_PAGES_TOTAL[0], WA_PAGES_TOTAL[1] + 1)
        for b in range(WA_PAGES_PER[0], WA_PAGES_PER[1] + 1) if a % b == 0),
    # последний элемент строго больше всех предыдущих (функция пропускает его)
    sum((m - 1) ** (n - 1) for n in range(WA_LIST_LEN[0], WA_LIST_LEN[1] + 1)
        for m in range(WA_LIST_VALUE[0], WA_LIST_VALUE[1] + 1)),
    len(_WA_CENTURIES),
)
_WA_PASS = (
    sum(1 for a in range(WA_PAGES_TOTAL[0], WA_PAGES_TOTAL[1] + 1)
        for b in range(WA_PAGES_PER[0], WA_PAGES_PER[1] + 1) if a % b),
    sum((WA_LIST_VALUE[1] - WA_LIST_VALUE[0] + 1) ** n for n in range(WA_LIST_LEN[0], WA_LIST_LEN[1] + 1))
    - sum((m - 1) ** (n - 1) for n in range(WA_LIST_LEN[0], WA_LIST_LEN[1] + 1)
          for m in range(WA_LIST_VALUE[0], WA_LIST_VALUE[1] + 1)),
    len(_WA_YEAR_RANGE) - len(_WA_CENTURIES),
)
WA_SPACE = sum(len(names) * len(params) * _WA_FAIL[i] * math.comb(_WA_PASS[i], 3) * SHUFFLES
               for i, (names, params, _) in enumerate(WA_TEMPLATES))


@family(code="be.debug.which_assert_fails", specialization="backend", area="debug", level=2,
        fmt="bug", space_size=WA_SPACE, median_time_s=55)
def which_assert_fails(rng: random.Random) -> Generated:
    t = rng.randrange(len(WA_TEMPLATES))
    names, params, tmpl = WA_TEMPLATES[t]
    fn, p = rng.choice(names), rng.choice(params)
    fmt = {"fn": fn, "a": p[0], "b": p[-1]}
    code = "\n".join(line.format(**fmt) for line in tmpl)
    passing: list[str] = []
    failing: list[str] = []
    while len(failing) < 1 or len(passing) < 3:
        args = _wa_args(rng, t, fail=len(failing) < 1 and rng.random() < 0.5)
        shown = ", ".join(repr(a) for a in args)
        line = f"assert {fn}({shown}) == {_wa_expected(t, args)!r}"
        if line in passing or line in failing:
            continue
        try:
            run_python_snippet(code + "\n" + line)
            if len(passing) < 3:
                passing.append(line)
        except AssertionError:
            if not failing:
                failing.append(line)
    text = "Что произойдёт при выполнении кода: какой из четырёх assert упадёт? Ровно один из них падает."
    return mcq(rng, text, failing[0], passing, code=code, language="python", radicals=("which_assert", 4))


# --- be.debug.accumulator_reset_line ---------------------------------------------
ACC_FNS = ("summarize", "aggregate", "tally", "collect_stats", "digest", "reduce_rows")
ACC_XS = ("xs", "values", "rows", "data")
ACC_SUM = ("total", "acc", "amount_sum", "s")
ACC_CNT = ("count", "n", "cnt", "seen")
ACC_X = ("x", "v", "item", "e")
ACC_TEMPLATE = (
    "def {fn}({xs}):",
    "    {acc} = 0",
    "    {cnt} = 0",
    "    for {x} in {xs}:",
    "        if {x} > 0:",
    "            {acc} += {x}",
    "            {cnt} += 1",
    "    return [{acc}, {cnt}]",
)
# (какая переменная, куда переносится инициализация)
ACC_VARIANTS = (("acc", "top"), ("acc", "if"), ("cnt", "top"), ("cnt", "if"), ("cnt", "before"))
ACC_X_MIN, ACC_X_MAX, ACC_LEN = -5, 9, 5


@family(code="be.debug.accumulator_reset_line", specialization="backend", area="debug", level=2,
        fmt="bug", median_time_s=55,
        # верхняя граница: пример дополнительно отбирается по проявлению ошибки
        space_size=(len(ACC_FNS) * len(ACC_XS) * len(ACC_SUM) * len(ACC_CNT) * len(ACC_X)
                    * len(ACC_VARIANTS) * (ACC_X_MAX - ACC_X_MIN + 1) ** ACC_LEN))
def accumulator_reset_line(rng: random.Random) -> Generated:
    names = {"fn": rng.choice(ACC_FNS), "xs": rng.choice(ACC_XS), "acc": rng.choice(ACC_SUM),
             "cnt": rng.choice(ACC_CNT), "x": rng.choice(ACC_X)}
    correct = [t.format(**names) for t in ACC_TEMPLATE]
    which, where = rng.choice(ACC_VARIANTS)
    moved = correct[1 if which == "acc" else 2].strip()
    rest = [ln for ln in correct if ln.strip() != moved]
    anchor = {"top": lambda ln: ln.lstrip().startswith("for "),
              "if": lambda ln: ln.lstrip().startswith("if "),
              "before": lambda ln: ln.lstrip().startswith(f"{names['cnt']} +=")}[where]
    idx = next(i for i, ln in enumerate(rest) if anchor(ln))
    if where == "before":
        rest.insert(idx, "            " + moved)
    else:
        rest.insert(idx + 1, ("        " if where == "top" else "            ") + moved)
    key = idx + 1 if where == "before" else idx + 2
    code, fixed = "\n".join(rest), "\n".join(correct)
    def make_call():
        return f"{names['fn']}({[rng.randint(ACC_X_MIN, ACC_X_MAX) for _ in range(ACC_LEN)]})"

    call, want = _exposing_example(make_call, fixed, code)
    text = (f"Функция {names['fn']} должна вернуть сумму положительных элементов списка и их количество."
            f"\nПример: {call} == {want}\nВ какой строке ошибка?")
    return _line_answer(text, rest, key, ("accumulator_reset", len(rest)))


# --- be.debug.mutate_while_iterating_line ----------------------------------------
MW_FNS = ("clean_up", "tidy_list", "sift", "refine", "normalize_items", "prepare")
MW_ITEMS = ("items", "values", "data", "nums")
MW_LIM = ("limit", "bound", "mark", "level")
MW_X = ("x", "v", "item", "e")
MW_REM = ("removed", "dropped", "gone", "cut")
# условие (с подстановкой), в паре с вычислением независимо от кода
MW_CONDS = (
    ("{x} < {lim}", lambda v, m: v < m),
    ("{x} > {lim}", lambda v, m: v > m),
    ("{x} % {lim} == 0", lambda v, m: v % m == 0),
)
MW_VARIANTS = (
    ("def {fn}({items}, {lim}):", "    {rem} = 0", "    for {x} in {items}:", "        if {cond}:",
     "            {items}.remove({x})", "            {rem} += 1", "    return {items}, {rem}"),
    ("def {fn}({items}, {lim}):", "    {rem} = 0", "    seen = 0", "    for {x} in {items}:",
     "        seen += 1", "        if {cond}:", "            {items}.remove({x})",
     "            {rem} += 1", "    return {items}, {rem}"),
    ("def {fn}({items}, {lim}):", "    {rem} = 0", "    if not {items}:", "        return {items}, {rem}",
     "    for {x} in {items}:", "        if {cond}:", "            {items}.remove({x})",
     "            {rem} += 1", "    return {items}, {rem}"),
)
MW_LEN = 7
MW_VALUE = (1, 9)
MW_LIM_RANGE = (2, 7)


@family(code="be.debug.mutate_while_iterating_line", specialization="backend", area="debug", level=3,
        fmt="bug", median_time_s=75,
        # верхняя граница: пример дополнительно отбирается по проявлению ошибки
        space_size=(len(MW_FNS) * len(MW_ITEMS) * len(MW_LIM) * len(MW_X) * len(MW_REM)
                    * len(MW_CONDS) * len(MW_VARIANTS) * (MW_VALUE[1] - MW_VALUE[0] + 1) ** MW_LEN
                    * (MW_LIM_RANGE[1] - MW_LIM_RANGE[0] + 1)))
def mutate_while_iterating_line(rng: random.Random) -> Generated:
    cond, _ = rng.choice(MW_CONDS)
    names = {"fn": rng.choice(MW_FNS), "items": rng.choice(MW_ITEMS), "lim": rng.choice(MW_LIM),
             "x": rng.choice(MW_X), "rem": rng.choice(MW_REM)}
    names["cond"] = cond.format(**names)
    lines = [t.format(**names) for t in rng.choice(MW_VARIANTS)]
    # ключ — строка `for`: достаточно изменить её одну (обход копии), строку remove одним изменением не починить
    key = next(i for i, ln in enumerate(lines, start=1) if ln.lstrip().startswith("for "))
    fixed_lines = list(lines)
    fixed_lines[key - 1] = lines[key - 1].replace(f" in {names['items']}:", f" in {names['items']}[:]:")
    code, fixed = "\n".join(lines), "\n".join(fixed_lines)

    def make_call():  # в списке должны быть подряд идущие подходящие элементы
        data = [rng.randint(*MW_VALUE) for _ in range(MW_LEN)]
        return f"{names['fn']}({data}, {rng.randint(*MW_LIM_RANGE)})"

    call, want = _exposing_example(make_call, fixed, code)
    text = (f"Функция {names['fn']} должна вернуть пару: список без элементов, подходящих под условие, "
            f"и число удалённых элементов.\nПример: {call} == {want}\n"
            "Какую одну строку достаточно изменить, чтобы функция давала ожидаемый результат?")
    return _line_answer(text, lines, key, ("mutate_while_iterating",))


# --- be.debug.flaky_test_cause ---------------------------------------------------
FLAKY_ENT = ("order", "invoice", "ticket", "session", "payment", "report", "booking", "parcel")
FLAKY_LABELS = ("red", "green", "blue", "amber", "grey", "cyan", "pink", "lime", "teal", "gold")
FLAKY_CFG = ("SETTINGS", "CONFIG", "OPTIONS", "FLAGS")
FLAKY_KEYS = ("debug", "verbose", "strict", "trace")
FLAKY_TTL = (1, 2, 3)
FLAKY_N = (30, 60)  # размер выборки в шаблоне с random.sample
FLAKY_IDS = (1000, 3000)  # верхняя граница randint: коллизия редкая, тест падает «иногда»
FLAKY_TAIL = "Почему последний тест фрагмента иногда падает?"
FLAKY_TIME = "Результат теста зависит от текущего времени на часах машины"
FLAKY_SET = "Результат теста зависит от порядка обхода множества строк"
FLAKY_STATE = "Результат теста зависит от общего состояния после других тестов"
FLAKY_RANDOM = "Результат теста зависит от случайных чисел без фиксированного seed"
_FLAKY_CAUSES = (FLAKY_TIME, FLAKY_SET, FLAKY_STATE, FLAKY_RANDOM)
_FLAKY_CODE = (
    (
        "def test_{x}_created_timestamp():\n"
        "    start = datetime.now().replace(microsecond=0)\n"
        "    {x} = create_{x}()\n"
        "    assert {x}.created_at == start",
        "def test_{x}_expires_today():\n"
        "    {x} = create_{x}(ttl_hours={h})\n"
        "    assert {x}.expires_at.date() == date.today()",
    ),
    (
        'def test_{x}_labels():\n'
        '    labels = {{"{a}", "{b}", "{c}"}}\n'
        '    assert list(labels) == ["{a}", "{b}", "{c}"]',
        'def test_{x}_export_header():\n'
        '    columns = {{"{a}", "{b}", "{c}"}}\n'
        '    header = ",".join(columns)\n'
        '    assert header == "{a},{b},{c}"',
    ),
    (
        '_registry = []\n\n'
        'def register(name):\n'
        '    _registry.append(name)\n'
        '    return len(_registry)\n\n'
        'def test_first_{x}_gets_id_1():\n'
        '    assert register("{a}") == 1\n\n'
        'def test_second_{x}_in_fresh_registry():\n'
        '    assert register("{b}") == 1',
        '{cfg} = {{"{k}": False}}\n\n'
        'def test_{k}_mode_enabled():\n'
        '    {cfg}["{k}"] = True\n'
        '    assert is_enabled({cfg}, "{k}")\n\n'
        'def test_{k}_is_off_by_default():\n'
        '    assert not is_enabled({cfg}, "{k}")',
    ),
    (
        "def test_{x}_ids_are_unique():\n"
        "    ids = [random.randint(1, {m}) for _ in range(10)]\n"
        "    assert len(set(ids)) == len(ids)",
        "def test_{x}_sample_has_no_zero():\n"
        "    sample = random.sample(range({n}), 5)\n"
        "    assert 0 not in sample",
    ),
)
FLAKY_ROWS = tuple(
    (templates, cause, tuple(c for c in _FLAKY_CAUSES if c != cause))
    for templates, cause in zip(_FLAKY_CODE, _FLAKY_CAUSES, strict=True)
)


def _flaky_values(rng: random.Random) -> dict:
    a, b, c = rng.sample(FLAKY_LABELS, 3)
    return {"x": rng.choice(FLAKY_ENT), "a": a, "b": b, "c": c, "h": rng.choice(FLAKY_TTL),
            "n": rng.randint(*FLAKY_N), "m": rng.randint(*FLAKY_IDS), "cfg": rng.choice(FLAKY_CFG),
            "k": rng.choice(FLAKY_KEYS)}


def _row_space(templates, sizes: dict) -> int:
    """Число различных фрагментов кода шаблонов: метки a, b, c берутся без повторов."""
    total = 0
    for t in templates:
        fields = template_fields(t)
        n = math.perm(len(FLAKY_LABELS), len(fields & {"a", "b", "c"}))
        for f in fields - {"a", "b", "c"}:
            n *= sizes[f]
        total += n
    return total


_FLAKY_SIZES = {
    "x": len(FLAKY_ENT), "h": len(FLAKY_TTL), "n": FLAKY_N[1] - FLAKY_N[0] + 1,
    "m": FLAKY_IDS[1] - FLAKY_IDS[0] + 1, "cfg": len(FLAKY_CFG), "k": len(FLAKY_KEYS),
}
FLAKY_SPACE = sum(_row_space(r[0], _FLAKY_SIZES) for r in FLAKY_ROWS) * len(SERVICES) * SHUFFLES


@family(code="be.debug.flaky_test_cause", specialization="backend", area="debug", level=3,
        fmt="mcq", space_size=FLAKY_SPACE, median_time_s=70)
def flaky_test_cause(rng: random.Random) -> Generated:
    templates, correct, pool = rng.choice(FLAKY_ROWS)
    code = rng.choice(templates).format(**_flaky_values(rng))
    text = (f"Тесты сервиса «{rng.choice(SERVICES)}» запускаются в CI в случайном порядке и параллельно; "
            f"фрагмент ниже то проходит, то падает при одном и том же коде. {FLAKY_TAIL}")
    return mcq(rng, text, correct, pool, code=code, language="python")


# --- be.debug.long_function_bug --------------------------------------------------
LF_FNS = ("merge_intervals", "join_ranges", "union_spans", "collapse_ranges", "fuse_segments", "combine_slots")
LF_IV = ("iv", "pairs", "spans", "slots")
LF_OUT = ("out", "merged", "res", "acc")
LF_CUR = (("cs", "ce"), ("cur_s", "cur_e"), ("a0", "a1"))
LF_LOOP = (("s", "e"), ("lo", "hi"), ("b", "f"))
LF_TEMPLATE = (
    "def {fn}({iv}):",
    "    if not {iv}:",
    "        return []",
    "    {iv} = sorted({iv}, key=lambda p: p[0])",
    "    {out} = []",
    "    {cs}, {ce} = {iv}[0]",
    "    for {s}, {e} in {iv}[1:]:",
    "        if {s} <= {ce}:",
    "            {ce} = max({ce}, {e})",
    "        else:",
    "            {out}.append(({cs}, {ce}))",
    "            {cs}, {ce} = {s}, {e}",
    "    {out}.append(({cs}, {ce}))",
    "    return {out}",
)
# номер строки (с 1) → (как правильно, как с ошибкой)
LF_MUTATIONS = {
    4: ("p[0]", "p[1]"), 8: (" <= ", " < "), 9: ("max(", "min("), 13: ("({cs}, {ce})", "({s}, {e})"),
}
LF_COUNT = 4  # отрезков в примере
LF_POINT_MAX = 20


@family(code="be.debug.long_function_bug", specialization="backend", area="debug", level=4,
        fmt="bug", median_time_s=105,
        space_size=(len(LF_FNS) * len(LF_IV) * len(LF_OUT) * len(LF_CUR) * len(LF_LOOP) * len(LF_MUTATIONS)
                    * math.comb(LF_POINT_MAX, 2) ** LF_COUNT))
def long_function_bug(rng: random.Random) -> Generated:
    cs, ce = rng.choice(LF_CUR)
    s, e = rng.choice(LF_LOOP)
    names = {"fn": rng.choice(LF_FNS), "iv": rng.choice(LF_IV), "out": rng.choice(LF_OUT),
             "cs": cs, "ce": ce, "s": s, "e": e}
    correct = [t.format(**names) for t in LF_TEMPLATE]
    key = rng.choice(sorted(LF_MUTATIONS))
    good, bad = (p.format(**names) for p in LF_MUTATIONS[key])
    lines = list(correct)
    lines[key - 1] = lines[key - 1].replace(good, bad, 1)
    code, fixed = "\n".join(lines), "\n".join(correct)
    def make_call():
        data = [tuple(sorted(rng.sample(range(1, LF_POINT_MAX + 1), 2))) for _ in range(LF_COUNT)]
        return f"{names['fn']}({data})"

    call, want = _exposing_example(make_call, fixed, code)
    text = (f"Функция {names['fn']} должна объединять пересекающиеся отрезки (пары «начало, конец»), в том числе "
            "соприкасающиеся — когда конец одного совпадает с началом другого, — и возвращать результат "
            f"по возрастанию начала.\nПример: {call} == {want}\nВ какой строке ошибка?")
    return _line_answer(text, lines, key, ("long_function", len(lines)))


# --- be.debug.bisect_steps -------------------------------------------------------
BISECT_N_MIN, BISECT_N_MAX = 10, 5000
BISECT_BRANCHES = ("main", "develop", "release", "staging", "hotfix", "stable")
BISECT_TESTS = ("test_checkout", "test_login", "test_export", "test_search", "test_refund", "test_sync",
                "test_upload", "test_invoice", "test_cache", "test_report", "test_queue", "test_profile")


@family(code="be.debug.bisect_steps", specialization="backend", area="debug", level=4,
        fmt="calc", median_time_s=95,
        space_size=((BISECT_N_MAX - BISECT_N_MIN + 1) * len(SERVICES) * len(BISECT_BRANCHES)
                    * len(BISECT_TESTS)))
def bisect_steps(rng: random.Random) -> Generated:
    # сначала ответ (равномерно), затем N из (2^(k-1), 2^k]; степени двойки и 2^(k-1)+1 — на границах
    k_min, k_max = (BISECT_N_MIN - 1).bit_length(), (BISECT_N_MAX - 1).bit_length()
    k = rng.randint(k_min, k_max)
    lo, hi = max(BISECT_N_MIN, (1 << (k - 1)) + 1), min(BISECT_N_MAX, 1 << k)
    roll = rng.random()
    n = hi if roll < 0.05 else lo if roll < 0.1 else rng.randint(lo, hi)
    steps = (n - 1).bit_length()  # ceil(log2 n) без float
    text = (f"В репозитории сервиса «{rng.choice(SERVICES)}» (ветка {rng.choice(BISECT_BRANCHES)}) тест "
            f"{rng.choice(BISECT_TESTS)} перестал проходить. Первый сломанный коммит — один из "
            "коммитов-кандидатов, концы диапазона уже проверены. "
            f"Число коммитов-кандидатов: {n}. Сколько проверок понадобится git bisect в худшем случае?")
    return Generated(
        "number", Prompt(text=text, answer_hint="Целое число проверок"), steps, ("bisect",),
    )


# --- be.debug.mock_wrong_target --------------------------------------------------
# (модуль, откуда импортируют, функция, вызывающая функция, аргумент, пример значения аргумента,
#  выражение в теле вызывающей функции, ожидаемый результат при моке, возвращающем v)
MOCK_NAMES = (
    ("pricing", "rates_client", "get_rate", "to_eur", "amount", 250, "{arg} * {f}(\"EUR\")",
     lambda v, s: s * v),
    ("orders", "stock_api", "fetch_stock", "can_ship", "qty", 50, "{f}(\"A-17\") >= {arg}",
     lambda v, s: v >= s),
    ("accounts", "user_service", "load_balance", "can_pay", "amount", 100, "{f}(42) >= {arg}",
     lambda v, s: v >= s),
    ("billing", "bank_api", "get_fee", "total_with_fee", "amount", 1200, "{arg} + {f}({arg})",
     lambda v, s: s + v),
    ("reports", "stats_client", "fetch_visits", "daily_average", "days", 7, "{f}(\"site\") // {arg}",
     lambda v, s: v // s),
    ("delivery", "geo_client", "get_distance", "eta_minutes", "speed", 30, "{f}(\"depot\") * 60 // {arg}",
     lambda v, s: v * 60 // s),
    ("auth", "sms_gateway", "get_attempts", "has_attempts", "limit", 100, "{f}(\"+7999\") < {arg}",
     lambda v, s: v < s),
    ("search", "index_api", "count_hits", "pages_needed", "per_page", 10, "-(-{f}(\"laptop\") // {arg})",
     lambda v, s: -(-v // s)),
    ("catalog", "images_cdn", "get_image_size", "fits_limit", "limit_kb", 100, "{f}(\"1.png\") <= {arg}",
     lambda v, s: v <= s),
    ("weather", "meteo_api", "get_temperature", "is_colder", "threshold", 100, "{f}(\"Kazan\") < {arg}",
     lambda v, s: v < s),
    ("loyalty", "crm_client", "get_points", "bonus_points", "multiplier", 3, "{f}(42) * {arg}",
     lambda v, s: v * s),
    ("shipping", "carrier_api", "get_tariff", "shipping_cost", "weight", 15, "{f}(\"RU\") * {arg}",
     lambda v, s: v * s),
)
MOCK_RETURN = (1, 199)
MOCK_STYLES = 2  # with patch(...) или декоратор @patch(...)
MOCK_TAIL = "Что не так и как это исправить?"
MOCK_ROWS = (
    (
        (
            "# {a}.py\nfrom {b} import {f}\n\n\ndef {caller}({arg}):\n    return {expr}\n\n\n"
            "# test_{a}.py\nfrom unittest.mock import patch\n\nimport {a}\n\n\n"
            "def test_{caller}():\n    with patch(\"{b}.{f}\", return_value={v}):\n"
            "        assert {a}.{caller}({sample}) == {r}",
            "# {a}.py\nfrom {b} import {f}\n\n\ndef {caller}({arg}):\n    return {expr}\n\n\n"
            "# test_{a}.py\nfrom unittest.mock import patch\n\nimport {a}\n\n\n"
            "@patch(\"{b}.{f}\", return_value={v})\n"
            "def test_{caller}(mock_{f}):\n    assert {a}.{caller}({sample}) == {r}",
        ),
        "Имя {f} уже импортировано в {a}; патчить {a}.{f} — там, где имя используется",
        (
            "patch умеет подменять только классы, а {f} — функция; использовать monkeypatch для {b}",
            "Для функции {f} подмена не срабатывает без autospec=True; передать autospec=True в patch",
            "Mock не перехватывает вызовы между модулями; передать MagicMock вместо Mock в patch",
        ),
    ),
)
MOCK_SPACE = len(MOCK_NAMES) * (MOCK_RETURN[1] - MOCK_RETURN[0] + 1) * MOCK_STYLES * SHUFFLES


@family(code="be.debug.mock_wrong_target", specialization="backend", area="debug", level=4,
        fmt="mcq", space_size=MOCK_SPACE, median_time_s=100)
def mock_wrong_target(rng: random.Random) -> Generated:
    templates, correct, pool = MOCK_ROWS[0]
    a, b, f, caller, arg, sample, expr, result = rng.choice(MOCK_NAMES)
    v = rng.randint(*MOCK_RETURN)
    vals = {"a": a, "b": b, "f": f, "caller": caller, "arg": arg, "sample": sample, "v": v,
            "expr": expr.format(arg=arg, f=f), "r": result(v, sample)}
    code = rng.choice(templates).format(**vals)
    text = (f"Тест подменяет сетевой вызов через patch, но всё равно обращается к настоящему {b}.{f}, "
            f"недоступному в CI. {MOCK_TAIL}")
    return mcq(rng, text, correct.format(**vals), [d.format(**vals) for d in pool], code=code,
               language="python")


# --- be.debug.check_then_act_race_line -------------------------------------------
RACE_LOCKS = ("lock", "mutex", "guard", "state_lock")
# когерентные кортежи: (функция, общее состояние, аргумент)
RACE_INT = (
    ("withdraw", "balance", "amount"), ("debit", "funds", "amount"), ("spend", "budget", "cost"),
    ("buy_ticket", "tickets_left", "qty"), ("take_item", "stock", "qty"), ("use_credits", "credits", "units"),
)
RACE_DICT = (
    ("reserve", "stock", "qty"), ("book_seats", "seats", "count"), ("claim_items", "inventory", "qty"),
    ("take_tickets", "tickets", "count"), ("hold_rooms", "rooms", "count"), ("order_goods", "shelf", "qty"),
)
# (функция, счётчик израсходованного, константа-предел, аргумент)
RACE_USED = (
    ("consume", "used", "LIMIT", "units"), ("add_usage", "spent", "BUDGET", "amount"),
    ("upload", "uploaded", "QUOTA", "size"), ("send_sms", "sent", "DAILY_CAP", "count"),
    ("load_batch", "loaded", "MAX_TOTAL", "items"), ("record_calls", "calls", "RATE_CAP", "count"),
)
RACE_INIT = (50, 990)  # шаг 10
RACE_LIMIT = (50, 990)  # шаг 10
RACE_TEMPLATES = (
    (  # проверка в строке 8
        "import threading", "", "{lock} = threading.Lock()", "{st} = {init}", "", "def {fn}({n}):",
        "    global {st}", "    if {st} >= {n}:", "        with {lock}:", "            {st} -= {n}",
        "        return True", "    return False",
    ),
    (  # проверка в строке 9
        "import threading", "", "{lock} = threading.Lock()", '{st} = {{"left": {init}}}', "",
        "def {fn}({n}):", "    {n} = int({n})", "    {n} = max({n}, 1)", '    if {st}["left"] < {n}:',
        "        return False", "    with {lock}:", '        {st}["left"] -= {n}', "    return True",
    ),
    (  # проверка в строке 10
        "import threading", "", "{lock} = threading.Lock()", "{st} = 0", "{cap} = {limit}", "",
        "def {fn}({n}):", "    global {st}", "    {n} = abs({n})", "    if {st} + {n} > {cap}:",
        "        return False", "    with {lock}:", "        {st} += {n}", "    return True",
    ),
)
_RACE_STEPS = (RACE_INIT[1] - RACE_INIT[0]) // 10 + 1
_RACE_LIMIT_STEPS = (RACE_LIMIT[1] - RACE_LIMIT[0]) // 10 + 1
RACE_SPACE = len(RACE_LOCKS) * len(SERVICES) * (
    len(RACE_INT) * _RACE_STEPS + len(RACE_DICT) * _RACE_STEPS + len(RACE_USED) * _RACE_LIMIT_STEPS)


@family(code="be.debug.check_then_act_race_line", specialization="backend", area="debug", level=5,
        fmt="bug", space_size=RACE_SPACE, median_time_s=135)
def check_then_act_race_line(rng: random.Random) -> Generated:
    t = rng.randrange(len(RACE_TEMPLATES))
    names = {"lock": rng.choice(RACE_LOCKS), "init": rng.randrange(RACE_INIT[0], RACE_INIT[1] + 1, 10),
             "limit": rng.randrange(RACE_LIMIT[0], RACE_LIMIT[1] + 1, 10)}
    if t == 2:
        names["fn"], names["st"], names["cap"], names["n"] = rng.choice(RACE_USED)
    else:
        names["fn"], names["st"], names["n"] = rng.choice((RACE_INT, RACE_DICT)[t])
    lines = [ln.format(**names) for ln in RACE_TEMPLATES[t]]
    # ключ — единственная строка-условие вне with, читающая общее состояние
    key = next(i for i, ln in enumerate(lines, start=1) if ln.strip().startswith("if "))
    text = (f"Сервис «{rng.choice(SERVICES)}» вызывает {names['fn']} сразу из нескольких потоков. "
            "Иногда общее значение выходит за допустимые пределы, хотя изменение защищено блокировкой. "
            "Какую строку нужно перенести под блокировку, чтобы устранить гонку?")
    return _line_answer(text, lines, key, ("check_then_act",))


# --- be.debug.memory_leak_cause --------------------------------------------------
LEAK_TAIL = "Какая причина роста памяти и как её устранить?"
LEAK_CACHE = "Словарь-кэш на уровне модуля растёт без границ; ограничить размер или срок жизни записей"
LEAK_CALLBACK = "Подписчики копятся у издателя и не отписываются; отписывать их, когда они больше не нужны"
LEAK_LOG = "Глобальный список записей лога только растёт; хранить ограниченное окно, например deque(maxlen=N)"
LEAK_LRU = "lru_cache на методе хранит ссылку на self в ключах; вынести кэшируемую функцию из класса"
LEAK_EXTRA = (
    "Циклические ссылки между объектами не собираются; вызывать gc.collect() по таймеру",
    "Каждый запрос порождает поток, и потоки не завершаются; ограничить размер пула потоков",
)
# когерентные кортежи для подстановки в шаблоны
LEAK_CACHE_SETS = (
    ("profile", "user_id", "load_profile"), ("price", "sku", "load_price"),
    ("rate", "currency", "fetch_rate"), ("user", "email", "find_user"),
    ("product", "item_id", "load_product"), ("session", "token", "load_session"),
    ("config", "name", "read_config"), ("weather", "city", "fetch_weather"),
)
LEAK_VIEW_SETS = (
    ("profile", "Profile", "saved"), ("order", "Order", "status_changed"), ("price", "Price", "updated"),
    ("cart", "Cart", "item_added"), ("chat", "Chat", "message"), ("stock", "Stock", "level_changed"),
)
LEAK_LOG_SETS = (("payment",), ("login",), ("transfer",), ("export",), ("signup",), ("refund",))
LEAK_CLASS_SETS = (
    ("CatalogReader", "price"), ("TariffTable", "rate"), ("WeatherClient", "forecast"),
    ("AccountLimits", "limit"), ("StockBoard", "left"), ("CurrencyDesk", "rate"),
)
_NO_SET = ((),)
# в каждый фрагмент добавлен безвредный «ложный след» из другой категории (ограниченная структура
# или парная отписка), чтобы причину нельзя было найти по одному ключевому слову
_LEAK_CODE = (
    (  # словарь-кэш без ограничений
        ("recent = deque(maxlen=100)\n_cache = {{}}\n\n\ndef get_{ent}({id}):\n    recent.append({id})\n"
         "    if {id} not in _cache:\n        _cache[{id}] = {loader}({id})\n    return _cache[{id}]",
         ("ent", "id", "loader"), LEAK_CACHE_SETS),
        ("@lru_cache(maxsize=64)\ndef {ent}_region(code):\n    return {loader}(code)\n\n\nPRICES = {{}}\n\n\n"
         "def {ent}_for(region, {id}):\n    key = (region, {id})\n    if key not in PRICES:\n"
         "        PRICES[key] = {loader}(*key)\n    return PRICES[key]",
         ("ent", "id", "loader"), LEAK_CACHE_SETS),
    ),
    (  # подписка без отписки
        ("# bus создаётся один раз при старте процесса\n@lru_cache(maxsize=32)\ndef load_{ent}_theme(user):\n"
         "    return read_theme(user)\n\n\ndef open_{ent}_view(bus, user):\n    view = {Cls}View(user)\n"
         "    bus.subscribe(view.on_update)\n    return view.render()",
         ("ent", "Cls", "ev"), LEAK_VIEW_SETS),
        ("# emitter создаётся один раз при старте процесса\nrecent = deque(maxlen=500)\n\n\n"
         "def attach_{ent}(emitter, state):\n    recent.append(state)\n    listener = {Cls}Listener(state)\n"
         "    emitter.on(\"{ev}\", listener.handle)\n    return listener",
         ("ent", "Cls", "ev"), LEAK_VIEW_SETS),
    ),
    (  # растущий список-лог
        ("@lru_cache(maxsize=256)\ndef route_for(path):\n    return match_route(path)\n\n\nREQUEST_LOG = []\n\n\n"
         "def handle(request):\n    REQUEST_LOG.append((time.time(), request.path, request.body))\n"
         "    return process(route_for(request.path), request)",
         (), _NO_SET),
        ("event_log = []\n\n\ndef record_{ent}(bus, event):\n    token = bus.subscribe(notify_ops)\n    try:\n"
         "        event_log.append(event.to_dict())\n        send_to_storage(event)\n    finally:\n"
         "        bus.unsubscribe(token)",
         ("ent",), LEAK_LOG_SETS),
    ),
    (  # lru_cache на методе
        ("recent = deque(maxlen=50)\n\n\nclass {cls}:\n    def __init__(self, session):\n"
         "        self.session = session\n\n    @lru_cache(maxsize=None)\n    def {m}(self, key):\n"
         "        return self.session.load(\"{m}\", key)\n\n\ndef handle(request):\n    recent.append(request.key)\n"
         "    return {cls}(request.session).{m}(request.key)",
         ("cls", "m"), LEAK_CLASS_SETS),
        ("class {cls}:\n    def __init__(self, path):\n        self.path = path\n\n    @lru_cache(maxsize=None)\n"
         "    def {m}(self, key):\n        return load_from(self.path, \"{m}\", key)\n\n\n"
         "def serve(bus, request):\n    token = bus.subscribe(audit)\n    try:\n"
         "        return {cls}(request.path).{m}(request.key)\n    finally:\n        bus.unsubscribe(token)",
         ("cls", "m"), LEAK_CLASS_SETS),
    ),
)
_LEAK_CAUSES = (LEAK_CACHE, LEAK_CALLBACK, LEAK_LOG, LEAK_LRU)


def _leak_pool(cause: str) -> tuple[str, ...]:
    others = tuple(c for c in _LEAK_CAUSES if c != cause)
    if cause == LEAK_LRU:  # неограниченный lru_cache — тоже неограниченный кэш: такой дистрактор спорен
        others = tuple(c for c in others if c != LEAK_CACHE)
    return others + LEAK_EXTRA


LEAK_ROWS = tuple(
    (tuple(t for t, _, _ in frags), cause, _leak_pool(cause))
    for frags, cause in zip(_LEAK_CODE, _LEAK_CAUSES, strict=True)
)
LEAK_SPACE = sum(
    sum(len(pool) for _, _, pool in frags) * len(SERVICES) * math.comb(len(_leak_pool(cause)), 3) * SHUFFLES
    for frags, cause in zip(_LEAK_CODE, _LEAK_CAUSES, strict=True))


def _leak_code(rng: random.Random, frags) -> str:
    template, keys, pool = rng.choice(frags)
    return template.format(**dict(zip(keys, rng.choice(pool), strict=True)))


@family(code="be.debug.memory_leak_cause", specialization="backend", area="debug", level=5,
        fmt="mcq", space_size=LEAK_SPACE, median_time_s=130)
def memory_leak_cause(rng: random.Random) -> Generated:
    i = rng.randrange(len(_LEAK_CODE))
    code = _leak_code(rng, _LEAK_CODE[i])
    _, correct, pool = LEAK_ROWS[i]
    text = (f"Долгоживущий сервис «{rng.choice(SERVICES)}» работает неделями, и память процесса постоянно "
            f"растёт. {LEAK_TAIL}")
    return mcq(rng, text, correct, rng.sample(pool, 3), code=code, language="python")
