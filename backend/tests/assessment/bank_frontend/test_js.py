"""Семантические тесты Frontend · JS/TS: ключ проверяется независимо от генератора."""
import re

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import frontend_js as js

from .._bank_helpers import area_codes, make, row_for

AREA_CODES = area_codes("js", "frontend")


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)
    assert r.space_estimate >= 50_000, (code, r.space_estimate)


def _consts(code: str) -> dict[str, str]:
    """const имя = литерал; → {имя: литерал} (литерал без точки с запятой)."""
    return dict(re.findall(r"^const (\w+) = (.+);$", code, re.M))


# ------------------------------------------------------------------ typeof_output
def _typeof(literal: str) -> str:
    """typeof литерала по правилам ECMAScript — своя таблица, без исполнения JS."""
    if literal == "null" or literal.startswith(("[", "{", "new ")):
        return "object"  # typeof null — исторически "object"; массивы и Date — объекты
    if literal == "undefined":
        return "undefined"
    if literal == "NaN" or re.fullmatch(r"-?\d+(\.\d+)?", literal):
        return "number"
    if re.fullmatch(r"\d+n", literal):
        return "bigint"
    if literal[0] in "'\"`":
        return "string"
    if literal.startswith("Symbol("):
        return "symbol"
    if literal in ("true", "false"):
        return "boolean"
    if "=>" in literal or literal.startswith("function"):
        return "function"
    raise AssertionError(literal)


def test_typeof_output_key():
    seen = set()
    for seed in range(200):
        inst = make("fe.js.typeof_output", seed)
        consts = _consts(inst.prompt.code)
        names = re.fullmatch(r"console\.log\(typeof (\w+), typeof (\w+), typeof (\w+)\);",
                             inst.prompt.code.splitlines()[-1]).groups()
        assert len(consts) == 3 and set(names) == set(consts)
        assert inst.answer == " ".join(_typeof(consts[n]) for n in names)
        traps = [c for c in consts.values() if c == "null" or c == "NaN" or c.startswith(("[", "new "))]
        assert traps, consts  # хотя бы одна ловушка: null, NaN, массив или Date
        assert inst.kind == "text" and inst.prompt.language == "javascript"
        seen.add(inst.answer)
    assert len(seen) >= 40


# ------------------------------------------------------------------ const_array_mutation_output
def test_const_array_mutation_key():
    seen = set()
    for seed in range(200):
        inst = make("fe.js.const_array_mutation_output", seed)
        lines = inst.prompt.code.splitlines()
        name, init = re.fullmatch(r"const (\w+) = \[(.+)\];", lines[0]).groups()
        xs = [int(x) for x in init.split(", ")]
        for ln in lines[1:-1]:  # независимое исполнение операций над списком Python
            if m := re.fullmatch(rf"{name}\.push\((\d+)\);", ln):
                xs.append(int(m.group(1)))
            elif m := re.fullmatch(rf"{name}\.unshift\((\d+)\);", ln):
                xs.insert(0, int(m.group(1)))
            elif m := re.fullmatch(rf"{name}\[(\d+)\] = (\d+);", ln):
                xs[int(m.group(1))] = int(m.group(2))
            else:
                raise AssertionError(ln)
        idx = re.fullmatch(rf"console\.log\({name}\.length, {name}\[(\d+)\]\);", lines[-1]).group(1)
        assert inst.answer == f"{len(xs)} {xs[int(idx)]}"
        seen.add(inst.answer)
    assert len(seen) >= 50


# ------------------------------------------------------------------ equality_coercion_output
def _parse(lit: str):
    if lit == "null":
        return ("null",)
    if lit == "undefined":
        return ("undefined",)
    if lit == "NaN":
        return ("num", float("nan"))
    if lit in ("true", "false"):
        return ("bool", lit == "true")
    if lit.startswith("'"):
        return ("str", lit[1:-1])
    if lit.startswith("["):
        return ("arr", lit[1:-1])
    return ("num", float(lit))


def _to_number(v) -> float:
    kind = v[0]
    if kind == "num":
        return v[1]
    if kind == "bool":
        return float(v[1])
    if kind == "str":
        s = v[1].strip()
        if s == "":
            return 0.0
        try:
            return float(s)
        except ValueError:
            return float("nan")
    raise AssertionError(v)


def _loose_eq(a, b) -> bool:
    """Абстрактное сравнение == (ECMAScript 7.2.15) для литералов из задания."""
    if a[0] == b[0] and a[0] != "arr":
        return _strict_eq(a, b)
    if {a[0], b[0]} == {"null", "undefined"}:
        return True
    if "null" in (a[0], b[0]) or "undefined" in (a[0], b[0]):
        return False
    if a[0] == "arr" and b[0] == "arr":
        return False  # два разных литерала массива — разные объекты
    if a[0] == "arr":
        return _loose_eq(("str", a[1].replace(" ", "")), b)  # ToPrimitive(массив) = join(',')
    if b[0] == "arr":
        return _loose_eq(a, ("str", b[1].replace(" ", "")))
    return _to_number(a) == _to_number(b)


def _strict_eq(a, b) -> bool:
    if a[0] != b[0]:
        return False
    if a[0] in ("null", "undefined"):
        return True
    if a[0] == "arr":
        return False
    return a[1] == b[1]  # NaN != NaN и в Python


def test_equality_coercion_key():
    seen_lines = set()
    for seed in range(200):
        inst = make("fe.js.equality_coercion_output", seed)
        out = []
        for ln in inst.prompt.code.splitlines():
            a, b, a2, b2 = re.fullmatch(r"console\.log\((.+?) == (.+?), (.+?) === (.+?)\);", ln).groups()
            assert (a, b) == (a2, b2)
            pa, pb = _parse(a), _parse(b)
            out.append(f"{str(_loose_eq(pa, pb)).lower()} {str(_strict_eq(pa, pb)).lower()}")
        assert len(out) == 3 and inst.answer == "\n".join(out)
        seen_lines.update(out)
    assert seen_lines == {"true false", "false false", "true true"}


# ------------------------------------------------------------------ array_chain_output
def _js_step(op: str, body: str, xs: list[int], init: int | None) -> list[int] | int:
    """map / filter / reduce по телу стрелочной функции; тело пересчитывается на Python."""
    if op == "map":
        m = re.fullmatch(r"\w+ ([*+-]) (\d+)", body)
        k = int(m.group(2))
        return [x * k if m.group(1) == "*" else x + k if m.group(1) == "+" else x - k for x in xs]
    if op == "filter":
        if m := re.fullmatch(r"\w+ % (\d+) === 0", body):
            return [x for x in xs if x % int(m.group(1)) == 0]
        m = re.fullmatch(r"\w+ ([<>]) (-?\d+)", body)
        t = int(m.group(2))
        return [x for x in xs if (x > t if m.group(1) == ">" else x < t)]
    assert op == "reduce" and re.fullmatch(r"\w+ \+ \w+", body)
    return init + sum(xs)


def test_array_chain_key():
    seen = set()
    for seed in range(200):
        inst = make("fe.js.array_chain_output", seed)
        code = inst.prompt.code
        xs = [int(x) for x in re.search(r"= \[(.+?)\];", code).group(1).split(", ")]
        steps = re.findall(r"\.(map|filter|reduce)\(\((?:\w+, )?\w+\) => (.+?)(?:, (\d+))?\);?$", code, re.M)
        assert [s[0] for s in steps][-1] == "reduce" and len(steps) == 3
        cur = xs
        for op, body, init in steps:
            before = cur
            cur = _js_step(op, body, cur, int(init) if init else None)
            if op == "filter":
                assert 2 <= len(cur) < len(before)  # фильтр действительно отбрасывает, но не всё
        assert inst.answer == str(cur)
        seen.add(inst.answer)
    assert len(seen) >= 100


# ------------------------------------------------------------------ string_number_ops_output
def _js_value(token: str):
    return token[1:-1] if token.startswith("'") else int(token)


def _js_to_number(v) -> int:
    return int(v) if isinstance(v, str) else v


def _js_eval(expr: str):
    """Литералы и операторы + - * слева направо (у * один оператор в выражении) по правилам JS."""
    tokens = re.findall(r"'\d+'|\d+|[+*-]", expr)
    acc = _js_value(tokens[0])
    for op, tok in zip(tokens[1::2], tokens[2::2], strict=True):
        v = _js_value(tok)
        if op == "+" and (isinstance(acc, str) or isinstance(v, str)):
            acc = f"{acc}{v}"
        elif op == "+":
            acc = acc + v
        elif op == "-":
            acc = _js_to_number(acc) - _js_to_number(v)
        else:
            acc = _js_to_number(acc) * _js_to_number(v)
    return acc


def test_string_number_ops_key():
    kinds = set()
    for seed in range(200):
        inst = make("fe.js.string_number_ops_output", seed)
        args = re.fullmatch(r"console\.log\((.+)\);", inst.prompt.code).group(1).split(", ")
        assert len(args) == 4
        values = [_js_eval(a) for a in args]
        assert inst.answer == " ".join(str(v) for v in values)
        kinds.update(type(v).__name__ for v in values)
    assert kinds == {"str", "int"}  # в ответах и склейки строк, и числа


# ------------------------------------------------------------------ var_let_closure_output
def test_var_let_closure_key():
    seen = set()
    var_first = 0
    for seed in range(200):
        inst = make("fe.js.var_let_closure_output", seed)
        code = inst.prompt.code
        loops = re.findall(
            r"for \((var|let) (\w+) = (\d+); \2 < (\d+); \2\+\+\) \{\n  setTimeout\(\(\) => \w+\.push\(\2\), (\d+)\);\n\}",
            code)
        assert [k for k, *_ in loops] in (["var", "let"], ["let", "var"])
        var_first += loops[0][0] == "var"
        # независимая модель: таймеры по (задержка, порядок постановки); var — одна переменная на цикл
        timers = []
        for kind, _, start, stop, delay in loops:
            for v in range(int(start), int(stop)):
                timers.append((int(delay), len(timers), int(stop) if kind == "var" else v))
        assert re.search(r"setTimeout\(\(\) => console\.log\(\w+\.join\(' '\)\), 100\);$", code)
        assert inst.answer == " ".join(str(v) for *_, v in sorted(timers))
        seen.add(inst.answer)
    assert 0.3 < var_first / 200 < 0.7 and len(seen) >= 100


# ------------------------------------------------------------------ default_sort_output
def test_default_sort_key():
    for seed in range(200):
        inst = make("fe.js.default_sort_output", seed)
        name, init = re.search(r"const (\w+) = \[(.+?)\];", inst.prompt.code).groups()
        xs = [int(x) for x in init.split(", ")]
        assert f"{name}.sort();" in inst.prompt.code and 5 <= len(xs) <= 7 and len(set(xs)) == len(xs)
        assert sorted(map(str, xs)) != [str(x) for x in sorted(xs)]  # строковый порядок отличается от числового
        assert {len(str(x)) for x in xs} >= {1, 2}
        assert inst.answer == " ".join(sorted(map(str, xs)))


# ------------------------------------------------------------------ spread_shallow_copy_output
def test_spread_shallow_copy_key():
    replaced = 0
    for seed in range(200):
        inst = make("fe.js.spread_shallow_copy_output", seed)
        code = inst.prompt.code
        obj, top, top_v, nested, field, nested_v = re.match(
            r"const (\w+) = \{ id: \d+, (\w+): '(\w+)', (\w+): \{ (\w+): '(\w+)' \} \};", code).groups()
        copy = re.search(rf"const (\w+) = \{{ \.\.\.{obj} \}};", code).group(1)
        assert re.search(rf"^{copy}\.{top} = '\w+';$", code, re.M)  # верхний уровень копии — свой
        if m := re.search(rf"^{copy}\.{nested}\.{field} = '(\w+)';$", code, re.M):
            nested_v = m.group(1)  # вложенный объект общий: изменение видно и в оригинале
        else:
            assert re.search(rf"^{copy}\.{nested} = \{{ {field}: '\w+' \}};$", code, re.M)
            replaced += 1  # копии присвоен новый объект — оригинал не меняется
        assert code.endswith(f"console.log({obj}.{top}, {obj}.{nested}.{field});")
        assert inst.answer == f"{top_v} {nested_v}"
    assert 0.2 < replaced / 200 < 0.5


# ------------------------------------------------------------------ event_loop_order_output
def _event_loop(code: str) -> list[str]:
    """Независимая модель event loop: синхронный код → микрозадачи (FIFO) → таймеры по (задержка, порядок)."""
    out, micro, timers = [], [], []
    body = re.search(r"async function (\w+)\(\) \{\n  console\.log\('(\w)'\);\n  await null;\n"
                     r"  console\.log\('(\w)'\);\n\}", code)
    fn, before, after = body.groups()
    for stmt in code[body.end():].strip().splitlines():
        if m := re.fullmatch(r"console\.log\('(\w)'\);", stmt):
            out.append(m.group(1))
        elif m := re.fullmatch(r"setTimeout\(\(\) => console\.log\('(\w)'\), (\d+)\);", stmt):
            timers.append((int(m.group(2)), len(timers), m.group(1)))
        elif m := re.fullmatch(r"Promise\.resolve\(\)\.then\(\(\) => console\.log\('(\w)'\)\);", stmt):
            micro.append((m.group(1), None))
        elif m := re.fullmatch(r"Promise\.resolve\(\)\.then\(\(\) => console\.log\('(\w)'\)\)"
                               r"\.then\(\(\) => console\.log\('(\w)'\)\);", stmt):
            micro.append((m.group(1), m.group(2)))
        elif stmt == f"{fn}();":
            out.append(before)
            micro.append((after, None))  # продолжение после await — микрозадача
        else:
            raise AssertionError(stmt)
    while micro:
        label, nxt = micro.pop(0)
        out.append(label)
        if nxt:
            micro.append((nxt, None))
    out += [label for *_, label in sorted(timers)]
    return out


def test_event_loop_order_key():
    seen = set()
    for seed in range(200):
        inst = make("fe.js.event_loop_order_output", seed)
        labels = _event_loop(inst.prompt.code)
        assert len(labels) == len(set(labels)) and inst.answer == " ".join(labels)
        statements = inst.prompt.code.split("}\n", 1)[1].strip().splitlines()
        assert 5 <= len(statements) <= 7
        seen.add(inst.answer)
    assert len(seen) >= 150


# ------------------------------------------------------------------ promise_all_vs_allsettled
def test_promise_all_vs_allsettled_key():
    for seed in range(200):
        inst = make("fe.js.promise_all_vs_allsettled", seed)
        row_for(inst.prompt.text, [(js.PA_TEMPLATES,)])
        key = inst.prompt.options[inst.answer]
        assert key in js.PA_OPTIONS["allSettled"] and "Promise.allSettled" in key
        others = [o for i, o in enumerate(inst.prompt.options) if i != inst.answer]
        strategies = {s for o in others for s, pool in js.PA_OPTIONS.items() if o in pool}
        assert len(strategies) == 3 and "allSettled" not in strategies  # три разные неверные стратегии
        assert not any("allSettled" in o for o in others)
        widgets = re.search(r": (.+?)\. ", inst.prompt.text).group(1).split(", ")
        assert 3 <= len(widgets) <= 6 and len(set(widgets)) == len(widgets)
        assert not re.search(r"\d", inst.prompt.text)  # без чисел перед существительными — нет и ошибок согласования


# ------------------------------------------------------------------ debounce_calls
def _debounce(times: list[int], wait: int) -> int:
    """Пошаговая симуляция по миллисекундам: событие перезапускает таймер, срабатывание — вызов."""
    deadline, calls, pending = None, 0, set(times)
    for t in range(0, max(times) + wait + 1):
        if deadline == t:
            calls += 1
            deadline = None
        if t in pending:
            deadline = t + wait
    return calls


def test_debounce_calls_key():
    seen = set()
    for seed in range(150):
        inst = make("fe.js.debounce_calls", seed)
        wait = int(re.search(r"задержкой (\d+) мс", inst.prompt.text).group(1))
        times = [int(x) for x in re.search(r"\[(.+)\]", inst.prompt.code).group(1).split(", ")]
        assert times == sorted(set(times)) and 8 <= len(times) <= 12 and 100 <= wait <= 500
        gaps = [b - a for a, b in zip(times, times[1:], strict=False)]
        assert wait not in gaps  # событие ровно в момент срабатывания — неоднозначность, её нет
        assert inst.answer == _debounce(times, wait) and inst.kind == "number"
        assert 1 < inst.answer < len(times)  # ни «каждое событие», ни «один раз в конце»
        seen.add(inst.answer)
    assert len(seen) >= 5


# ------------------------------------------------------------------ microtask_starvation
def test_microtask_starvation_key():
    forms = set()
    for seed in range(200):
        inst = make("fe.js.microtask_starvation", seed)
        code = inst.prompt.code
        # код бесконечно ставит микрозадачи: рекурсивный then / queueMicrotask или await в while (true)
        if "while (true)" in code:
            forms.add("await")
            assert "await null;" in code
        else:
            fn = re.search(r"function (\w+)\(\)", code).group(1)
            assert f"Promise.resolve().then({fn});" in code or f"queueMicrotask({fn});" in code
            forms.add("then" if "then" in code else "queueMicrotask")
        assert re.search(r"setTimeout\(\(\) => console\.log\('\w+'\), \d+\);", code)
        key = inst.prompt.options[inst.answer]
        assert key in js.STARVE_CORRECT
        others = [o for i, o in enumerate(inst.prompt.options) if i != inst.answer]
        assert all(any(o == d.format(d=re.search(r"\), (\d+)\);", code).group(1)) for d in js.STARVE_WRONG)
                   for o in others)
    assert forms == {"await", "then", "queueMicrotask"}


# ------------------------------------------------------------------ ts_narrowing
# своя таблица правил TypeScript: какое условие с ранним return какие члены объединения убирает
TS_OBJECT_TYPES = {"null", "Date", "string[]"}  # typeof x === "object" истинно и для null


def _ts_removed(guard: str, members: list[str], declared: dict[str, str]) -> set[str]:
    if m := re.fullmatch(r'typeof \w+ === "(\w+)"', guard):
        t = m.group(1)
        return {x for x in members if x in TS_OBJECT_TYPES} if t == "object" else {t} & set(members)
    if re.fullmatch(r"\w+ === null", guard):
        return {"null"} & set(members)
    if re.fullmatch(r"\w+ === undefined", guard):
        return {"undefined"} & set(members)
    if re.fullmatch(r"\w+ instanceof Date", guard):
        return {"Date"} & set(members)
    if re.fullmatch(r"Array\.isArray\(\w+\)", guard):
        return {"string[]"} & set(members)
    if m := re.fullmatch(r'\w+\.kind (===|!==) "(\w+)"', guard):
        hit = {x for x in members if declared[x] == m.group(2)}
        return hit if m.group(1) == "===" else set(members) - hit
    if m := re.fullmatch(r'"(\w+)" in \w+', guard):
        return {x for x in members if f" {m.group(1)}(" in declared[x]}
    raise AssertionError(guard)


def test_ts_narrowing_key():
    trap_object = forms = 0
    seen_forms = set()
    for seed in range(300):
        inst = make("fe.js.ts_narrowing", seed)
        code = inst.prompt.code
        declared = {name: body for name, body in re.findall(r"^type (\w+) = (\{.+\});$", code, re.M)}
        kinds = {name: m.group(1) for name, body in declared.items()
                 if (m := re.search(r'kind: "(\w+)"', body))}
        union_src = re.search(r"\((\w+): (.+?)\): void", code).group(2)
        if union_src in re.findall(r"^type (\w+) = ", code, re.M):  # объединение задано псевдонимом
            union_src = re.search(rf"^type {union_src} = (.+);$", code, re.M).group(1)
        members = union_src.split(" | ")
        remaining = list(members)
        for guard in re.findall(r"^  if \((.+)\) return;$", code, re.M):
            removed = _ts_removed(guard, remaining, {**declared, **kinds} if kinds else declared)
            assert removed, guard  # каждое условие что-то сужает
            remaining = [x for x in remaining if x not in removed]
            trap_object += guard.endswith('=== "object"') and "null" in members
        assert remaining and inst.prompt.options[inst.answer] == " | ".join(remaining)
        assert len(set(inst.prompt.options)) == 4
        seen_forms.add("kind" if kinds else "in" if " in " in code else "typeof")
        forms += 1
    assert seen_forms == {"kind", "in", "typeof"} and trap_object >= 15



def test_microtask_starvation_has_no_zero_ms_phrase():
    for seed in range(200):
        assert "через 0 мс" not in " ".join(make("fe.js.microtask_starvation", seed).prompt.options)


def test_ts_narrowing_union_order_is_typescript_display_order():
    order = ["string", "number", "bigint", "boolean", "Date", "string[]", "null", "undefined"]
    for seed in range(200):
        inst = make("fe.js.ts_narrowing", seed)
        for opt in inst.prompt.options:
            parts = opt.split(" | ")
            if set(parts) <= set(order):
                assert parts == sorted(parts, key=order.index), opt
