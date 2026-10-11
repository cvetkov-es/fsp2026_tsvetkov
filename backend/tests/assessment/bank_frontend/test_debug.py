"""Семантические тесты Frontend · отладка и тестирование: ключ проверяется независимо от генератора."""
import json
import re

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import frontend_debug as dbg
from app.assessment.bank.jsrun import JsError, run_js_snippet

from .._bank_helpers import area_codes, make

AREA_CODES = area_codes("debug", "frontend")


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)
    assert r.space_estimate >= 50_000, (code, r.space_estimate)


def _mcq_parts(inst):
    key = inst.prompt.options[inst.answer]
    return key, [o for i, o in enumerate(inst.prompt.options) if i != inst.answer]


def _numbers(text: str) -> set[float]:
    return {float(x) for x in re.findall(r"(?<![\w#.-])-?\d+(?:\.\d+)?", text)}


def _numbered_lines(inst) -> list[str]:
    lines = inst.prompt.code.split("\n")
    assert inst.prompt.answer_hint == "Номер строки:\n" + "\n".join(f"{n:>2}| {ln}" for n, ln in enumerate(lines, 1))
    return lines


def _assert_no_line_label(text, key):
    assert not re.search(rf"(?i)(строк\w*|line)\s*(№\s*)?{key}\b", text), text


# ------------------------------------------------------------------ stack_trace_line
def test_stack_trace_line_key():
    seen = set()
    for seed in range(200):
        inst = make("fe.debug.stack_trace_line", seed)
        rows = inst.prompt.code.split("\n")
        assert re.fullmatch(r"(TypeError|ReferenceError): .+", rows[0])
        frames = [re.fullmatch(r"    at (\S+) \(([\w./-]+):(\d+):(\d+)\)", r).groups() for r in rows[1:]]
        assert 3 <= len(frames) <= 5
        asked = re.search(r"файла (\S+\.tsx)", inst.prompt.text).group(1)
        assert "указывает стек" in inst.prompt.text
        hits = [int(line) for _, path, line, _ in frames if path.endswith(asked)]
        assert len(hits) == 1 and (frames[0][1].endswith(asked) or "/utils/" in frames[0][1])  # сверху — компонент
        # или вызванная им вспомогательная функция
        assert inst.answer == hits[0] and not re.search(r"\d", inst.prompt.text.replace(asked, ""))
        seen.add(inst.answer)
    assert len(seen) > 30


# ------------------------------------------------------------------ text_matcher
def test_text_matcher_key():
    for seed in range(200):
        inst = make("fe.debug.text_matcher", seed)
        key, others = _mcq_parts(inst)
        text = re.search(r"текст «(.+?)»", inst.prompt.text).group(1)
        assert key in [c.format(text=text) for c in dbg.MATCHER_CORRECT]
        assert all(o in [w.format(text=text) for w in dbg.MATCHER_WRONG] for o in others)
        # нет пары «утверждение — его отрицание»: иначе выбор сужается до двух вариантов
        assert not any(o.replace(".not.", ".") == key.replace(".not.", ".") for o in others)


# ------------------------------------------------------------------ pagination_slice_count
def test_pagination_slice_count_key():
    seen = set()
    for seed in range(200):
        inst = make("fe.debug.pagination_slice_count", seed)
        const, size = re.search(r"const (\w+) = (\d+);", inst.prompt.code).groups()
        size = int(size)
        assert f"slice((page - 1) * {const}, page * {const})" in inst.prompt.code
        arr, n = re.search(r"Длина массива (\w+) — (\d+)\.", inst.prompt.text).groups()
        n = int(n)
        page = int(re.search(rf"\w+\({arr}, (\d+)\)\?", inst.prompt.text).group(1))
        start, end = (page - 1) * size, page * size
        assert inst.answer == len(range(n)[start:end])  # срез Python ведёт себя как Array.prototype.slice
        seen.add(inst.answer)
    assert 0 in seen and len(seen) >= 5


# ------------------------------------------------------------------ which_expect_fails
def _js_value(expect_line: str, fn_code: str):
    """Фактическое значение вызова из expect(...) — исполнение настоящего JS (QuickJS), независимо от генератора."""
    call = re.fullmatch(r"expect\((.+)\)\.toBe\((.+)\)", expect_line).group(1)
    try:
        return json.loads(run_js_snippet(fn_code + f"\nconsole.log(JSON.stringify({call}));"))
    except JsError:
        return "<исключение>"


def test_which_expect_fails_key():
    kinds = set()
    for seed in range(120):
        inst = make("fe.debug.which_expect_fails", seed)
        failing = []
        for i, opt in enumerate(inst.prompt.options):
            expected = json.loads(re.fullmatch(r"expect\(.+\)\.toBe\((.+)\)", opt).group(1).replace("'", '"'))
            if _js_value(opt, inst.prompt.code) != expected:
                failing.append(i)
        assert failing == [inst.answer], (inst.prompt.code, inst.prompt.options)
        kinds.add(re.search(r"function (\w+)", inst.prompt.code).group(1))
    assert len(kinds) == 4


# ------------------------------------------------------------------ onclick_called_line
def test_onclick_called_line_key():
    positions = set()
    for seed in range(200):
        inst = make("fe.debug.onclick_called_line", seed)
        lines = _numbered_lines(inst)
        calls = [i for i, ln in enumerate(lines, 1) if re.search(r"on[A-Z]\w*=\{\w+\(\)\}", ln)]
        assert calls == [inst.answer]  # обработчик вызывается при рендере, а не передаётся
        assert "Too many re-renders" in inst.prompt.text
        _assert_no_line_label(inst.prompt.text, inst.answer)
        assert 8 <= len(lines) <= 16
        positions.add(inst.answer)
    assert len(positions) >= 3


# ------------------------------------------------------------------ missing_await_test
def test_missing_await_test_key():
    forms = set()
    for seed in range(200):
        inst = make("fe.debug.missing_await_test", seed)
        key, others = _mcq_parts(inst)
        assert key in dbg.AWAIT_CORRECT and set(others) <= set(dbg.AWAIT_WRONG)
        code = inst.prompt.code
        assert "await " not in code and "return " not in code  # промис никто не ждёт
        forms.add("waitFor" if "waitFor" in code else "async" if "async" in code else "then")
    assert forms == {"waitFor", "async", "then"}


def test_which_expect_fails_has_no_surface_tell():
    """Падающая проверка не выделяется видом: ни длиной, ни особым символом в ожидаемом значении,
    ни совпадением ожидаемого с одним из аргументов (эвристики угадывают не чаще 50%)."""
    n = 0
    tells = {"longest": 0, "special_char": 0, "expected_is_arg": 0}
    for seed in range(300):
        inst = make("fe.debug.which_expect_fails", seed)
        opts, key = inst.prompt.options, inst.answer
        lens = [len(o) for o in opts]
        tells["longest"] += lens[key] == max(lens) and lens.count(max(lens)) == 1
        special = [i for i, o in enumerate(opts) if re.search(r"…|\.0\d'|-.*-", o)]
        tells["special_char"] += special == [key]
        args_eq = [i for i, o in enumerate(opts) if (m := re.fullmatch(r"expect\(\w+\((.+)\)\)\.toBe\((.+)\)", o))
                   and m.group(2) in m.group(1).split(", ")[1:]]
        tells["expected_is_arg"] += args_eq == [key]
        n += 1
    assert all(v / n <= 0.5 for v in tells.values()), {k: v / n for k, v in tells.items()}


# ------------------------------------------------------------------ optional_chaining_line
def test_optional_chaining_line_key():
    positions = set()
    for seed in range(150):
        inst = make("fe.debug.optional_chaining_line", seed)
        lines = _numbered_lines(inst)
        fn = re.search(r"^function (\w+)\(", inst.prompt.code).group(1)
        with pytest.raises(JsError) as err:  # настоящий JS падает именно на этой строке
            run_js_snippet(inst.prompt.code)
        assert re.search(rf"at {fn} \(<input>:(\d+)\)", str(err.value)).group(1) == str(inst.answer)
        assert "TypeError" in str(err.value) and "?." in inst.prompt.code
        assert 8 <= len(lines) <= 12
        _assert_no_line_label(inst.prompt.text, inst.answer)
        positions.add(inst.answer)
    assert len(positions) >= 4


# ------------------------------------------------------------------ flaky_snapshot
def test_flaky_snapshot_key():
    sources = set()
    for seed in range(200):
        inst = make("fe.debug.flaky_snapshot", seed)
        key, others = _mcq_parts(inst)
        assert key in dbg.SNAPSHOT_CORRECT and set(others) <= set(dbg.SNAPSHOT_WRONG)
        src = re.search(r"Date\.now\(\)|Math\.random\(\)|new Date\(\)", inst.prompt.code)
        assert src and "toMatchSnapshot()" in inst.prompt.code  # в снимок попадает меняющееся значение
        sources.add(src.group(0))
    assert len(sources) == 3


# ------------------------------------------------------------------ long_component_bug
def test_long_component_bug_key():
    keys = set()
    for seed in range(120):
        inst = make("fe.debug.long_component_bug", seed)
        lines = _numbered_lines(inst)
        call, expected = re.search(r"Пример: (.+?) должен вернуть (\{.+?\}),", inst.prompt.text).groups()
        broken = run_js_snippet(inst.prompt.code + f"\nconsole.log(JSON.stringify({call}));")
        assert json.loads(broken) != json.loads(expected)  # пример проявляет ошибку
        # исправление одной строки ключа (по таблице мутаций) даёт ожидаемый результат
        items, per, page = re.search(r"function \w+\((\w+), (\w+), (\w+)\)", inst.prompt.code).groups()
        names = {"items": items, "per": per, "page": page}
        bad = lines[inst.answer - 1]
        fixes = [bad.replace(wrong.format(**names), right.format(**names))
                 for right, wrong in dbg.PAGINATE_MUTATIONS.values() if wrong.format(**names) in bad]
        assert fixes
        fixed = lines[:inst.answer - 1] + [fixes[0]] + lines[inst.answer:]
        out = run_js_snippet("\n".join(fixed) + f"\nconsole.log(JSON.stringify({call}));")
        assert json.loads(out) == json.loads(expected)
        keys.add(inst.answer)
    assert len(keys) >= 4


# ------------------------------------------------------------------ profiler_hotspot
def test_profiler_hotspot_key():
    traps = 0
    for seed in range(300):
        inst = make("fe.debug.profiler_hotspot", seed)
        table = inst.prompt.tables[0]
        rows = [dict(zip(table.columns, r, strict=True)) for r in table.rows]
        total = {r["Компонент"]: r["Рендеров"] * r["Среднее время, мс"] for r in rows}
        stable = [r["Компонент"] for r in rows if r["Пропсы между рендерами"] == "не меняются"]
        best = max(stable, key=total.get)  # memo пропускает рендер только при неизменных пропсах
        assert inst.prompt.options[inst.answer] == best
        assert all(total[best] >= 1.2 * total[c] for c in stable if c != best)  # без почти равных
        traps += max(total, key=total.get) != best  # больше всего времени — у компонента с меняющимися пропсами
    assert traps >= 120


# ------------------------------------------------------------------ fake_timers
def test_fake_timers_key():
    for seed in range(200):
        inst = make("fe.debug.fake_timers", seed)
        key, others = _mcq_parts(inst)
        delay = re.search(r"delay=\{(\d+)\}", inst.prompt.code).group(1)
        assert "useFakeTimers" in key and delay in key  # нужно продвинуть время на задержку debounce
        assert not any("useFakeTimers" in o for o in others)
        assert "useFakeTimers" not in inst.prompt.code and "advanceTimers" not in inst.prompt.code


# ------------------------------------------------------------------ ui_race_line
def test_ui_race_line_key():
    positions = set()
    for seed in range(200):
        inst = make("fe.debug.ui_race_line", seed)
        lines = _numbered_lines(inst)
        latest = re.search(r"^let (\w+) = '';$", inst.prompt.code, re.M).group(1)
        render_fn = re.search(r"^  (\w+)\(results\);$", inst.prompt.code, re.M).group(1)
        hits = [i for i, ln in enumerate(lines, 1) if ln == f"  {render_fn}(results);"]
        assert hits == [inst.answer]
        # последний запрос запоминается, но перед отрисовкой результат с ним не сравнивается
        assert inst.prompt.code.count(latest) == 2 and "await fetch(" in inst.prompt.code
        assert 11 <= len(lines) <= 15
        _assert_no_line_label(inst.prompt.text, inst.answer)
        positions.add(inst.answer)
    assert len(positions) >= 3


# ------------------------------------------------------------------ listener_leak
def test_listener_leak_key():
    events = set()
    for seed in range(200):
        inst = make("fe.debug.listener_leak", seed)
        key, others = _mcq_parts(inst)
        assert key in dbg.LISTENER_CORRECT and set(others) <= set(dbg.LISTENER_WRONG)
        event = re.search(r"addEventListener\('(\w+)'", inst.prompt.code).group(1)
        assert "removeEventListener" not in inst.prompt.code and "return" not in inst.prompt.code.split("useEffect")[1].split("}, [")[0]
        events.add(event)
    assert len(events) >= 3



def test_stack_trace_has_no_parent_frame_below_react():
    for seed in range(100):
        rows = make("fe.debug.stack_trace_line", seed).prompt.code.split("\n")[1:]
        react = [i for i, r in enumerate(rows) if "react-dom" in r]
        assert all("react-dom" in r for r in rows[react[0]:])  # ниже кадров React — только React


def test_pagination_zero_answer_is_rare():
    zeros = sum(make("fe.debug.pagination_slice_count", s).answer == 0 for s in range(300))
    assert zeros <= 0.12 * 300, zeros
