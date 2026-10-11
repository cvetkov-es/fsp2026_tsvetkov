import re
import threading

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import backend_debug as dbg
from app.assessment.bank.pysnippet import run_python_snippet

from ._helpers import area_codes
from ._helpers import make as _make
from ._helpers import row_for as _row_for
from ._helpers import template_regex as _template_regex

AREA_CODES = area_codes("debug")
SEEDS = range(60)


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)
    assert r.space_estimate >= 50_000, (code, r.space_estimate)


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]
    assert len(AREA_CODES) == 13


def _assert_no_line_label(text, key):
    """Ключ не назван в тексте как номер строки (числа примера в тексте допустимы — это входные данные)."""
    assert not re.search(rf"(?i)(строк\w*|line)\s*(№\s*)?{key}\b", text), text


def _run(code, expr):
    return run_python_snippet(code + f"\nprint({expr})")


def _example(text):
    """Пример из текста: 'вызов == ожидаемое'."""
    m = re.search(r"Пример: (.+?) == (.+?)\n", text)
    return m.group(1), m.group(2)


# ------------------------------------------------------------------ traceback_line
def test_traceback_line_key():
    code = "be.debug.traceback_line"
    seen = set()
    for seed in range(200):
        inst = _make(code, seed)
        tb = inst.prompt.code
        rows = tb.split("\n")
        assert rows[0] == "Traceback (most recent call last):"
        frames = re.findall(r'^  File "([^"]+)", line (\d+), in (\S+)$', tb, re.M)
        assert len(frames) == 3
        # после каждой строки File — строка кода с отступом в 4 пробела (формат CPython 3.12)
        for i, row in enumerate(rows):
            if row.startswith("  File "):
                assert rows[i + 1].startswith("    ") and not rows[i + 1].startswith("     ")
        assert re.fullmatch(r"\w+(Error): .+", rows[-1])
        assert frames[0][2] == "<module>"
        asked = re.search(r"файла (\w+\.py)", inst.prompt.text).group(1)
        hits = [n for path, n, _ in frames if path.endswith("/" + asked)]
        assert len(hits) == 1  # файл встречается ровно в одном кадре
        assert inst.answer == int(hits[0])
        assert frames[-1][0].endswith("/" + asked)  # самый глубокий кадр — там возникло исключение
        assert len({n for _, n, _ in frames}) == 3  # номера строк в кадрах различны
        assert not re.search(r"\d", inst.prompt.text)  # ключ в тексте не назван
        seen.add(inst.answer)
    assert len(seen) > 20


# ------------------------------------------------------------------ loop_count_output
def test_loop_count_key():
    code = "be.debug.loop_count_output"
    n = 300
    zero = neg = inexact = 0
    for seed in range(n):
        inst = _make(code, seed)
        a, b, s = map(int, re.search(r"range\((-?\d+), (-?\d+), (-?\d+)\)", inst.prompt.code).groups())
        assert s != 0
        # независимо: считаем итерации арифметикой, без range
        cnt = 0
        cur = a
        while (cur < b) if s > 0 else (cur > b):
            cnt += 1
            cur += s
        assert inst.answer == cnt and run_python_snippet(inst.prompt.code) == str(cnt)
        zero += cnt == 0
        neg += s < 0
        inexact += (b - a) % s != 0
    assert zero <= 0.1 * n
    assert neg >= 0.2 * n and inexact >= 0.3 * n


# ------------------------------------------------------------------ wrong_comparison_line
def _cmp_variants(line):
    """Все варианты строки с одним сменённым оператором сравнения."""
    out = []
    for op, alt in (("<=", "<"), ("<", "<="), (">=", ">"), (">", ">=")):
        for m in re.finditer(rf"(?<![<>=]){re.escape(op)}(?![=])", line):
            out.append(line[:m.start()] + alt + line[m.end():])
    return out


def test_wrong_comparison_key():
    code = "be.debug.wrong_comparison_line"
    keys = set()
    for seed in range(120):
        inst = _make(code, seed)
        lines = inst.prompt.code.split("\n")
        call, expected = _example(inst.prompt.text)
        key = inst.answer
        assert _run(inst.prompt.code, call) != expected  # мутированный код ошибается на примере
        # исправленный (обратная мутация строки-ключа) даёт ожидаемое
        fixes = []
        for variant in _cmp_variants(lines[key - 1]):
            fixed = "\n".join(lines[:key - 1] + [variant] + lines[key:])
            fixes.append(_run(fixed, call) == expected)
        assert any(fixes)
        # мутация в другой строке не чинит код: правка любой другой строки ответа не даёт
        for i, ln in enumerate(lines, start=1):
            if i == key:
                continue
            for variant in _cmp_variants(ln):
                other = "\n".join(lines[:i - 1] + [variant] + lines[i:])
                assert _run(other, call) != expected, (i, variant)
        _assert_no_line_label(inst.prompt.text, key)
        keys.add(key)
    assert len(keys) >= 3


# ------------------------------------------------------------------ which_assert_fails
def test_which_assert_fails_key():
    code = "be.debug.which_assert_fails"
    positions, templates = set(), set()
    for seed in range(120):
        inst = _make(code, seed)
        opts = inst.prompt.options
        assert len(opts) == 4 and len(set(opts)) == 4
        assert all(re.fullmatch(r"assert \w+\(.+\) == .+", o) for o in opts), opts
        failed = []
        for i, o in enumerate(opts):
            try:
                run_python_snippet(inst.prompt.code + "\n" + o)
            except AssertionError:
                failed.append(i)
        assert failed == [inst.answer]  # ровно один assert падает
        assert inst.radicals == ("which_assert", 4)
        positions.add(inst.answer)
        templates.add(inst.prompt.code.split("\n")[0].split("(")[0].split()[-1])
    assert positions == {0, 1, 2, 3}
    assert len(templates) >= 6


def _opt_nums(o):
    return [int(x) for x in re.findall(r"-?\d+", o.split("==")[0])]


def _opt_expected(o):
    return o.split("== ")[1]


def _unique(vals, pick):
    target = pick(vals)
    idx = [i for i, v in enumerate(vals) if v == target]
    return idx[0] if len(idx) == 1 else None


def _odd_one(vals):
    for i, v in enumerate(vals):
        rest = [w for j, w in enumerate(vals) if j != i]
        if v not in rest and len(set(rest)) == 1:
            return i
    return None


def _int_or_zero(text):
    return int(text) if text.lstrip("-").isdigit() else 0


def _expected_is_last_arg(o):
    """Ожидаемое значение совпадает с последним числом в аргументах (для списка — с последним элементом)."""
    nums = _opt_nums(o)
    return bool(nums) and _opt_expected(o) == str(nums[-1])


WA_HEURISTICS = {  # одно поверхностное свойство, по которому можно «угадать» падающий assert
    "единственный год на 00": lambda os: _unique(
        [any(str(n).endswith("00") for n in _opt_nums(o)) for o in os], lambda v: True),
    "единственный непохожий ожидаемый результат": lambda os: _odd_one([_opt_expected(o) for o in os]),
    "самая длинная строка": lambda os: _unique([len(o) for o in os], max),
    "самая короткая строка": lambda os: _unique([len(o) for o in os], min),
    "наибольший аргумент": lambda os: _unique([max(_opt_nums(o)) for o in os], max),
    "наименьший аргумент": lambda os: _unique([min(_opt_nums(o)) for o in os], min),
    "наибольший ожидаемый": lambda os: _unique([_int_or_zero(_opt_expected(o)) for o in os], max),
    "наименьший ожидаемый": lambda os: _unique([_int_or_zero(_opt_expected(o)) for o in os], min),
    "ожидаемое равно последнему элементу": lambda os: _unique([_expected_is_last_arg(o) for o in os],
                                                              lambda v: True),
}


def test_which_assert_fails_has_no_single_feature_tell():
    """По любому одному поверхностному признаку падающий assert угадывается не чаще чем в 40% случаев."""
    scores = {t: {k: 0 for k in WA_HEURISTICS} for t in range(3)}
    count = [0, 0, 0]
    for seed in range(1500):
        inst = _make("be.debug.which_assert_fails", seed)
        t = 0 if "//" in inst.prompt.code else 1 if "[1:-1]" in inst.prompt.code else 2
        count[t] += 1
        for name, h in WA_HEURISTICS.items():
            scores[t][name] += h(inst.prompt.options) == inst.answer
    assert min(count) >= 400  # все три шаблона представлены
    for t in range(3):
        for name, hits in scores[t].items():
            assert hits / count[t] <= 0.4, (t, name, round(hits / count[t], 2))
    # в проходящих годах есть и високосные (True), и невисокосные, и круглые кратные 400
    years = [_opt_nums(o)[0] for seed in range(300)
             for inst in [_make("be.debug.which_assert_fails", seed)] if "% 400" in inst.prompt.code
             for i, o in enumerate(inst.prompt.options) if i != inst.answer]
    assert any(y % 400 == 0 for y in years) and any(y % 4 == 0 and y % 100 for y in years)


# ------------------------------------------------------------------ accumulator_reset_line
def test_accumulator_reset_key():
    code = "be.debug.accumulator_reset_line"
    keys = set()
    for seed in range(120):
        inst = _make(code, seed)
        lines = inst.prompt.code.split("\n")
        call, expected = _example(inst.prompt.text)
        key = inst.answer
        moved = lines[key - 1]
        assert re.fullmatch(r"\s{8,}\w+ = 0", moved)  # инициализация внутри цикла
        assert _run(inst.prompt.code, call) != expected
        # возвращаем строку на место (первая строка тела функции) — результат совпадает с ожидаемым
        fixed = lines[:key - 1] + lines[key:]
        fixed.insert(1, "    " + moved.strip())
        assert _run("\n".join(fixed), call) == expected
        _assert_no_line_label(inst.prompt.text, key)
        keys.add(key)
    assert len(keys) >= 3


# ------------------------------------------------------------------ mutate_while_iterating_line
def test_mutate_while_iterating_key():
    code = "be.debug.mutate_while_iterating_line"
    keys = set()
    for seed in range(120):
        inst = _make(code, seed)
        lines = inst.prompt.code.split("\n")
        call, expected = _example(inst.prompt.text)
        key = inst.answer
        assert 7 <= len(lines) <= 10
        assert sum(".remove(" in ln for ln in lines) == 1
        assert lines[key - 1].lstrip().startswith("for ")  # ключ — строка for, а не remove
        assert ".remove(" not in lines[key - 1]
        assert "одну строку достаточно изменить" in inst.prompt.text
        # независимо: условие из кода и список из примера → ожидаемое «исправленной» версией
        cond = re.search(r"if (.+):", "\n".join(lines[key:])).group(1)
        items = re.search(r"\((\[.*?\]), (\d+)\)", call)
        data, lim = eval(items.group(1)), int(items.group(2))  # noqa: S307 - наш же текст
        var = re.search(r"for (\w+) in", inst.prompt.code).group(1)
        limname = re.search(r"def \w+\(\w+, (\w+)\)", inst.prompt.code).group(1)
        keep = [v for v in data if not eval(cond, {}, {var: v, limname: lim})]  # noqa: S307
        assert expected == str((keep, len(data) - len(keep)))
        assert _run(inst.prompt.code, call) != expected  # пропущенный сосед проявляет ошибку
        # замена одной строки-ключа на обход копии даёт ожидаемое
        copy_line = re.sub(r" in (\w+):$", r" in \1[:]:", lines[key - 1])
        fixed = lines[:key - 1] + [copy_line] + lines[key:]
        assert _run("\n".join(fixed), call) == expected
        # строку remove одной правкой не починить: любая замена remove-строки на pass/del/continue не даёт ожидаемого
        r = next(i for i, ln in enumerate(lines) if ".remove(" in ln)
        ind = " " * _indent(lines[r])
        for repl_line in (ind + "pass", ind + "continue", ind + f"del {var}"):
            try:
                out = _run("\n".join(lines[:r] + [repl_line] + lines[r + 1:]), call)
            except Exception:  # noqa: BLE001
                continue
            assert out != expected
        _assert_no_line_label(inst.prompt.text, key)
        keys.add(key)
    assert len(keys) >= 3


# ------------------------------------------------------------------ пулы и пространство
POOL_NAMES = (
    "SERVICES", "TB_MODULES", "TB_FUNCS", "TB_DIRS", "TB_ERRORS", "LOOP_COUNTERS", "LOOP_VARS",
    "CMP_FNS", "CMP_XS", "CMP_LOHI", "CMP_X", "CMP_CNT", "CMP_NEED", "ACC_FNS", "ACC_XS", "ACC_SUM",
    "ACC_CNT", "ACC_X", "MW_FNS", "MW_ITEMS", "MW_LIM", "MW_X", "MW_REM", "FLAKY_ENT", "FLAKY_LABELS",
    "FLAKY_CFG", "FLAKY_KEYS", "FLAKY_TTL", "LF_FNS", "LF_IV", "LF_OUT", "LF_CUR", "LF_LOOP",
    "BISECT_BRANCHES", "BISECT_TESTS", "MOCK_NAMES", "LEAK_EXTRA", "LEAK_CACHE_SETS", "LEAK_VIEW_SETS", "LEAK_LOG_SETS",
    "LEAK_CLASS_SETS", "RACE_LOCKS", "RACE_INT", "RACE_DICT", "RACE_USED",
)


def test_pools_have_no_duplicates():
    for name in POOL_NAMES:
        pool = getattr(dbg, name)
        assert len(set(pool)) == len(pool), name
    for names, params, _ in dbg.WA_TEMPLATES:
        assert len(set(names)) == len(names) and len(set(params)) == len(params)
    all_wa = [n for names, _, _ in dbg.WA_TEMPLATES for n in names]
    assert len(set(all_wa)) == len(all_wa)  # имена функций разных шаблонов не пересекаются


def test_mock_names_are_coherent_and_distinct():
    for col in range(4):  # модуль, источник, функция, вызывающая функция
        values = [row[col] for row in dbg.MOCK_NAMES]
        assert len(set(values)) == len(values), col
    stdlib = {"profile", "time", "random", "json", "re", "logging", "queue", "string", "types"}
    for a, b, f, caller, *_ in dbg.MOCK_NAMES:
        assert a != b and f != caller and a not in f and b.split("_")[0] != a
        assert a not in stdlib and b not in stdlib  # `import profile` затенил бы стандартную библиотеку


def test_leak_pools_are_plausible_and_row_specific():
    assert not set(dbg.LEAK_EXTRA) & set(dbg._LEAK_CAUSES)
    sizes = []
    for _, correct, pool in dbg.LEAK_ROWS:
        assert correct not in pool and len(set(pool)) == len(pool)
        assert set(dbg.LEAK_EXTRA) <= set(pool)
        sizes.append(len(pool))
    # у строки lru_cache неограниченный словарь-кэш не дистрактор: он тоже был бы правдоподобным ответом
    lru_pool = next(pool for _, c, pool in dbg.LEAK_ROWS if c == dbg.LEAK_LRU)
    assert dbg.LEAK_CACHE not in lru_pool and sizes == [5, 5, 5, 4]
    # мифы о GC и GIL убраны: дистракторы про циклы ссылок и потоки
    assert not any("GIL" in x or "gc.enable" in x for x in dbg.LEAK_EXTRA)


def test_space_is_derived_from_pools():
    f = REGISTRY
    assert f["be.debug.loop_count_output"].space_size == (
        (dbg.LOOP_START_MAX - dbg.LOOP_START_MIN + 1) * (dbg.LOOP_SPAN_MAX - dbg.LOOP_SPAN_MIN + 1)
        * dbg.LOOP_STEP_MAX * 2 * len(dbg.LOOP_COUNTERS) * len(dbg.LOOP_VARS))
    assert f["be.debug.traceback_line"].space_size == (
        12 * 11 * 10 * 12 * 11 * len(dbg.TB_DIRS) * len(dbg.TB_ERRORS) * len(dbg.SERVICES)
        * 238 * 237 * 236)
    assert f["be.debug.accumulator_reset_line"].space_size == (
        len(dbg.ACC_FNS) * len(dbg.ACC_XS) * len(dbg.ACC_SUM) * len(dbg.ACC_CNT) * len(dbg.ACC_X)
        * len(dbg.ACC_VARIANTS) * 15 ** dbg.ACC_LEN)
    assert f["be.debug.which_assert_fails"].space_size == dbg.WA_SPACE
    assert f["be.debug.mutate_while_iterating_line"].space_size == (
        len(dbg.MW_FNS) * len(dbg.MW_ITEMS) * len(dbg.MW_LIM) * len(dbg.MW_X) * len(dbg.MW_REM)
        * len(dbg.MW_CONDS) * len(dbg.MW_VARIANTS) * 9 ** dbg.MW_LEN * 6)
    assert f["be.debug.bisect_steps"].space_size == 4991 * len(dbg.SERVICES) * len(dbg.BISECT_BRANCHES) * 12
    assert f["be.debug.long_function_bug"].space_size == (
        len(dbg.LF_FNS) * len(dbg.LF_IV) * len(dbg.LF_OUT) * len(dbg.LF_CUR) * len(dbg.LF_LOOP) * 4
        * 190 ** dbg.LF_COUNT)
    # флаки: сервисы × разные фрагменты кода × порядок вариантов; метки a,b,c — без повторов
    fragments = 8 + 8 * 3 + 2 * 8 * 10 * 9 * 8 + 8 * 10 * 9 + 4 * 4 + 8 * 2001 + 8 * 31
    assert f["be.debug.flaky_test_cause"].space_size == fragments * len(dbg.SERVICES) * 24
    assert f["be.debug.mock_wrong_target"].space_size == 12 * 199 * 2 * 24
    # гонка: замки × сервисы × (кортежи функция/состояние × начальные значения)
    assert f["be.debug.check_then_act_race_line"].space_size == 4 * 12 * (6 * 95 + 6 * 95 + 6 * 95)
    # утечки: по строкам (фрагменты кода) × сервисы × выбор 3 из пула × порядок вариантов
    frags = {"cache": 8 + 8, "callback": 6 + 6, "log": 1 + 6, "lru": 6 + 6}
    pools = {"cache": 10, "callback": 10, "log": 10, "lru": 4}  # C(5,3) и C(4,3)
    assert f["be.debug.memory_leak_cause"].space_size == sum(
        frags[k] * 12 * pools[k] * 24 for k in frags)
    for code in AREA_CODES:
        assert REGISTRY[code].space_size >= 50_000, code


# ------------------------------------------------------------------ MCQ: общие проверки
ROWS = {
    "be.debug.flaky_test_cause": "FLAKY_ROWS",
    "be.debug.mock_wrong_target": "MOCK_ROWS",
    "be.debug.memory_leak_cause": "LEAK_ROWS",
}
MCQ_CODES = [c for c in AREA_CODES if REGISTRY[c].fmt == "mcq"]
SEMI = ("be.debug.mock_wrong_target", "be.debug.memory_leak_cause")  # варианты «диагноз; исправление»


def _rows(code):
    return getattr(dbg, ROWS[code])


@pytest.mark.parametrize("code", MCQ_CODES)
def test_mcq_options_come_from_scenario_row(code):
    positions = set()
    for seed in range(120):
        inst = _make(code, seed)
        opts = inst.prompt.options
        assert len(opts) == 4 and len(set(opts)) == 4
        assert inst.radicals == ("mcq", 4)
        _, correct, pool = _row_for(inst.prompt.code, _rows(code))
        # варианты — шаблоны с подстановкой; сравниваем после подстановки по форме строки
        assert _template_regex(correct).fullmatch(opts[inst.answer]), (opts[inst.answer], correct)
        wrong = [o for i, o in enumerate(opts) if i != inst.answer]
        for o in wrong:
            assert any(_template_regex(p).fullmatch(o) for p in pool), o
            assert not _template_regex(correct).fullmatch(o)
        positions.add(inst.answer)
    assert positions == {0, 1, 2, 3}


@pytest.mark.parametrize("code", MCQ_CODES)
def test_mcq_rows_are_clean(code):
    rows = _rows(code)
    corrects = [r[1] for r in rows]
    assert len(set(corrects)) == len(corrects)
    for templates, correct, pool in rows:
        assert len(set(pool)) == len(pool) >= 3
        assert correct not in pool
        assert len(set(templates)) == len(templates) >= 1
        if code in SEMI:  # форма «диагноз; исправление» у всех вариантов
            assert all(";" in o for o in [correct, *pool])
            assert len({o.split()[0] for o in [correct, *pool]}) >= 3


@pytest.mark.parametrize("code", MCQ_CODES)
def test_option_lengths_balanced(code):
    """Длины вариантов близки (≤ 1.4×); доля «ключ самый длинный/короткий» — в test_mcq_form."""
    for seed in range(200):
        lens = [len(o) for o in _make(code, seed).prompt.options]
        assert max(lens) <= 1.4 * min(lens), lens


def test_same_question_tail_in_every_mcq_text():
    for code in MCQ_CODES:
        tails = {re.split(r"(?<=[.?])\s", _make(code, s).prompt.text.strip())[-1] for s in range(80)}
        assert len(tails) == 1, (code, tails)


# ------------------------------------------------------------------ flaky_test_cause
def _flaky_cause(code):
    """Независимая классификация фрагмента по признакам (ровно один признак на шаблон)."""
    marks = {
        "time": bool(re.search(r"datetime\.now\(\)|date\.today\(\)", code)),
        "set": bool(re.search(r'= \{"[^":]+", ', code)),
        "state": bool(re.search(r"^(_registry = \[\]|[A-Z]+ = \{\"\w+\": (True|False)\})", code, re.M)),
        "random": "random." in code,
    }
    on = [k for k, v in marks.items() if v]
    assert len(on) == 1, (on, code)
    return on[0]


def test_flaky_cause_matches_code():
    code = "be.debug.flaky_test_cause"
    seen = set()
    for seed in range(200):
        inst = _make(code, seed)
        cause = _flaky_cause(inst.prompt.code)
        seen.add(cause)
        key_text = inst.prompt.options[inst.answer]
        markers = {"time": "времен", "set": "множеств", "state": "состояни", "random": "случайн"}
        assert markers[cause] in key_text
        others = [o for i, o in enumerate(inst.prompt.options) if i != inst.answer]
        assert not any(markers[cause] in o for o in others)
        if cause == "set":  # порядок set из int детерминирован — значит, только строки
            assert not re.search(r"\{\d", inst.prompt.code)
            assert re.search(r'\{"\w+", "\w+"', inst.prompt.code)
    assert seen == {"time", "set", "state", "random"}


# ------------------------------------------------------------------ long_function_bug
def _merge(iv):
    out = []
    for s, e in sorted(iv):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _unmutate(line):
    """Обратная мутация строки (независимая от генератора), если строка — одна из четырёх точек."""
    if "key=lambda" in line:
        return line.replace("p[1]", "p[0]")
    if re.search(r"if \w+ < \w+:", line):
        return line.replace(" < ", " <= ")
    if "= min(" in line:
        return line.replace("= min(", "= max(")
    return None


def test_long_function_bug_key():
    code = "be.debug.long_function_bug"
    keys = set()
    for seed in range(200):
        inst = _make(code, seed)
        lines = inst.prompt.code.split("\n")
        assert 12 <= len(lines) <= 15
        call, expected = _example(inst.prompt.text)
        intervals = eval(re.search(r"\((\[.*\])\)", call).group(1))  # noqa: S307 - наш же текст
        assert expected == str(_merge(intervals))
        key = inst.answer
        assert _run(inst.prompt.code, call) != expected
        # исправление строки-ключа возвращает ожидаемое: проверяем на пяти случайных входах
        line = lines[key - 1]
        fixed_line = _unmutate(line)
        if fixed_line is None:  # мутация «последняя пара вместо накопленного интервала»
            assert re.fullmatch(r"    \w+\.append\(\(\w+, \w+\)\)", line)
            first = re.search(r"    (\w+), (\w+) = \w+\[0\]", "\n".join(lines))
            fixed_line = line.split(".append")[0] + f".append(({first.group(1)}, {first.group(2)}))"
        fixed = "\n".join(lines[:key - 1] + [fixed_line] + lines[key:])
        assert _run(fixed, call) == expected
        # правка любой другой строки (из тех же четырёх типов исправлений) пример не чинит
        for i, ln in enumerate(lines, start=1):
            other_fix = _unmutate(ln)
            if i == key or other_fix is None or other_fix == ln:
                continue
            other = "\n".join(lines[:i - 1] + [other_fix] + lines[i:])
            assert _run(other, call) != expected, (i, ln)
        _assert_no_line_label(inst.prompt.text, key)
        keys.add(key)
    assert len(keys) == 4


# ------------------------------------------------------------------ bisect_steps
def test_bisect_steps_key():
    code = "be.debug.bisect_steps"
    answers = []
    powers = 0
    for seed in range(600):
        inst = _make(code, seed)
        n = int(re.search(r"коммитов-кандидатов: (\d+)", inst.prompt.text).group(1))
        assert 10 <= n <= 5000
        # пересчёт: делим диапазон пополам (худший случай — большая половина) до одного кандидата
        steps, size = 0, n
        while size > 1:
            size = (size + 1) // 2
            steps += 1
        assert inst.answer == steps
        assert "концы диапазона уже проверены" in inst.prompt.text
        assert not re.search(r"\blog|логарифм|\b2\^", inst.prompt.text)  # формулу не называем
        assert "худшем случае" in inst.prompt.text
        answers.append(steps)
        powers += n & (n - 1) == 0
    assert set(answers) == set(range(4, 14))
    # ответ распределён ровно, а не жмётся к 12: самый частый ≤ 20%
    assert max(answers.count(a) for a in set(answers)) <= 0.2 * len(answers)
    assert powers >= 0.03 * len(answers)  # границы (степени двойки) встречаются


# ------------------------------------------------------------------ mock_wrong_target
def test_mock_wrong_target_coherent():
    code = "be.debug.mock_wrong_target"
    seen = set()
    for seed in range(200):
        inst = _make(code, seed)
        src = inst.prompt.code
        b, f = re.search(r"^from (\w+) import (\w+)$", src, re.M).groups()
        a = re.search(r"^# (\w+)\.py$", src, re.M).group(1)
        assert re.search(rf"^# test_{a}\.py$", src, re.M)
        assert re.search(rf'patch\("{b}\.{f}"', src)  # мок поставлен в источнике, а вызов идёт из a
        assert f"import {a}" in src and f"{a}." in src
        v = int(re.search(r"return_value=(\d+)", src).group(1))
        # независимо: исполняем модуль a с функцией f, возвращающей v, и сверяем ожидание теста
        body = src.split("# test_")[0]
        body = re.sub(r"^# .*\n|^from .*\n", "", body, flags=re.M)
        ns = {f: lambda *args, _v=v: _v}
        exec(body, ns)  # noqa: S102 - наш шаблонный код
        caller, sample, want = re.search(rf"{a}\.(\w+)\((.+?)\) == (.+)$", src, re.M).groups()
        assert ns[caller](eval(sample)) == eval(want)  # noqa: S307
        # имя функции соответствует телу: числа/логика, а не «умножь на k»
        assert "* " + str(v) not in body
        assert f"{b}.{f}" in inst.prompt.text
        assert f"патчить {a}.{f} — там, где имя используется" in inst.prompt.options[inst.answer]
        assert a != b
        assert all(f"{a}.{f}" not in o for i, o in enumerate(inst.prompt.options) if i != inst.answer)
        seen.add((a, b, f))
    assert len(seen) == len(dbg.MOCK_NAMES)


# ------------------------------------------------------------------ memory_leak_cause
def _leak_cause(code):
    """Независимо: причина = конструкция, которая действительно растёт (ложные следы её не дают)."""
    marks = {
        "cache": bool(re.search(r"^\w+ = \{\}$", code, re.M)) and bool(re.search(r"^\s+\w+\[\w+\] = ", code, re.M)),
        "callback": bool(re.search(r"\.(subscribe|on)\(", code)) and "unsubscribe" not in code,
        "log": bool(re.search(r"^\w+ = \[\]$", code, re.M)),
        # вариант ответа называет lru_cache — значит, во фрагменте именно lru_cache, а не @cache
        "lru": "@lru_cache(maxsize=None)" in code,
    }
    on = [k for k, v in marks.items() if v]
    assert len(on) == 1, (on, code)
    return on[0]


def _naive_leak_guess(code, order):
    """Наивный классификатор: «конструкция есть в коде — значит, это причина», по приоритету."""
    present = {
        "lru": bool(re.search(r"lru_cache|@cache", code)),
        "callback": bool(re.search(r"subscribe|\.on\(", code)),
        "log": bool(re.search(r"= \[\]|deque", code)),
        "cache": "= {}" in code,
    }
    return next(c for c in order if present[c])


def test_memory_leak_cause_matches_code():
    code = "be.debug.memory_leak_cause"
    words = {"cache": "Словарь-кэш", "callback": "Подписчики", "log": "список записей лога", "lru": "lru_cache"}
    seen = set()
    for seed in range(300):
        inst = _make(code, seed)
        cause = _leak_cause(inst.prompt.code)
        seen.add(cause)
        assert words[cause] in inst.prompt.options[inst.answer]
        # ни один дистрактор не называет ту же причину
        assert not any(words[cause] in o for i, o in enumerate(inst.prompt.options) if i != inst.answer)
        if cause == "lru":  # неограниченный словарь-кэш не среди дистракторов этой строки
            assert not any(words["cache"] in o for o in inst.prompt.options)
            assert "@cache" not in inst.prompt.code
    assert seen == set(words)


def test_memory_leak_not_solvable_by_keywords():
    """Каждый фрагмент содержит ложный след другой категории: поиск ключевого слова близок к случайному."""
    from itertools import permutations
    insts = [_make("be.debug.memory_leak_cause", seed) for seed in range(400)]
    truth = [_leak_cause(i.prompt.code) for i in insts]
    best = max(
        sum(_naive_leak_guess(i.prompt.code, order) == t for i, t in zip(insts, truth, strict=True)) / len(insts)
        for order in permutations(("lru", "callback", "log", "cache")))
    assert best <= 0.7, best
    # и отдельно: по вариантам ответа — «выбрать вариант, чья конструкция есть в коде» тоже не работает
    hits = 0
    for inst in insts:
        mentioned = [i for i, o in enumerate(inst.prompt.options)
                     if (("lru_cache" in o and re.search(r"lru_cache|@cache", inst.prompt.code))
                         or ("Словарь-кэш" in o and "= {}" in inst.prompt.code)
                         or ("Подписчики" in o and "subscribe" in inst.prompt.code)
                         or ("deque" in o and re.search(r"= \[\]|deque", inst.prompt.code)))]
        hits += mentioned == [inst.answer]
    assert hits <= 0.5 * len(insts), hits


def test_leak_distractors_include_extras_at_random():
    extras = set()
    for seed in range(200):
        inst = _make("be.debug.memory_leak_cause", seed)
        extras |= {o for o in inst.prompt.options if o in dbg.LEAK_EXTRA}
    assert extras == set(dbg.LEAK_EXTRA)


# ------------------------------------------------------------------ check_then_act_race_line
class _BarrierLock:
    """Блокировка, у которой оба потока доходят до входа в `with` раньше, чем кто-то получит замок."""

    def __init__(self):
        self._lock = threading.Lock()
        self._barrier = threading.Barrier(2, timeout=5)

    def __enter__(self):
        self._barrier.wait()
        self._lock.acquire()

    def __exit__(self, *exc):
        self._lock.release()


def _indent(line):
    return len(line) - len(line.lstrip())


def _fix_race(lines, key):
    """Переносим проверку под блокировку: with перед проверкой, внутренний with убираем."""
    w = next(i for i, ln in enumerate(lines) if ln.strip().startswith("with ") and i > key - 1)
    lock_line = lines[w]
    iw = _indent(lock_line)
    body_end = next((i for i in range(w + 1, len(lines)) if _indent(lines[i]) <= iw), len(lines))
    out = lines[:key - 1]
    out.append(" " * _indent(lines[key - 1]) + lock_line.strip())
    for i in range(key - 1, len(lines)):
        if i == w:
            continue
        shift = 4
        if w < i < body_end:
            shift = 0  # тело внутреннего with: +4 за общий with, -4 за убранный внутренний
        out.append(" " * shift + lines[i])
    return out


def _race_outcome(code):
    ns = {"BarrierLock": _BarrierLock}
    exec(code.replace("threading.Lock()", "BarrierLock()"), ns)  # noqa: S102 - наш шаблонный код
    fn = ns[re.search(r"^def (\w+)\(", code, re.M).group(1)]
    if re.search(r"^[A-Z_]+ = \d+$", code, re.M):  # вариант с лимитом
        cap = ns[re.search(r"^([A-Z_]+) = \d+$", code, re.M).group(1)]
        amount, bad = cap // 2 + 1, lambda: ns[re.search(r"^([a-z_]+) = 0$", code, re.M).group(1)] > cap
    elif '["left"]' in code:
        d = ns[re.search(r"^(\w+) = \{", code, re.M).group(1)]
        amount, bad = d["left"] // 2 + 1, lambda: d["left"] < 0
    else:
        name = re.search(r"^([a-z_]+) = \d+$", code, re.M).group(1)
        amount, bad = ns[name] // 2 + 1, lambda: ns[name] < 0
    threads = [threading.Thread(target=fn, args=(amount,)) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return bad()


def test_check_then_act_race_key():
    code = "be.debug.check_then_act_race_line"
    keys = set()
    for seed in range(120):
        inst = _make(code, seed)
        lines = inst.prompt.code.split("\n")
        key = inst.answer
        assert 12 <= len(lines) <= 14
        w = next(i for i, ln in enumerate(lines, start=1) if ln.strip().startswith("with "))
        iw = _indent(lines[w - 1])
        body = [i for i in range(w + 1, len(lines) + 1) if _indent(lines[i - 1]) > iw]
        state = re.search(r"^([a-z_]+) = (\d+|\{)", inst.prompt.code, re.M).group(1)
        # ключ: условие `if`, которое стоит вне with-блока и читает общее состояние
        assert lines[key - 1].strip().startswith("if ") and key not in body and key < w
        ifs_outside = [i for i, ln in enumerate(lines, start=1)
                       if ln.strip().startswith("if ") and i not in body and state in ln]
        assert ifs_outside == [key]
        # все остальные строки, изменяющие состояние, — внутри with
        for i, ln in enumerate(lines, start=1):
            if re.search(rf"\b{state}\b.*(\+=|-=)", ln):
                assert i in body, ln
        # гонка реальна (оба потока прошли проверку), а перенос проверки под замок её убирает
        assert _race_outcome(inst.prompt.code) is True
        assert _race_outcome("\n".join(_fix_race(lines, key))) is False
        _assert_no_line_label(inst.prompt.text, key)
        keys.add(key)
    assert keys == {8, 9, 10}


# ------------------------------------------------------------------ компиляция всех показанных фрагментов
@pytest.mark.parametrize("code", AREA_CODES)
def test_every_python_block_compiles(code):
    """Код в заданиях — настоящий Python (ловит дубли параметров и т. п.): 300 экземпляров на семейство."""
    for seed in range(300):
        inst = _make(code, seed)
        if inst.prompt.language == "python":
            compile(inst.prompt.code, "<prompt>", "exec")
            for opt in inst.prompt.options or ():
                if opt.startswith("assert "):
                    compile(inst.prompt.code + "\n" + opt, "<prompt>", "exec")
