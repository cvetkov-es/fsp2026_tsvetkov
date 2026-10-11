"""Семантические тесты Frontend · фреймворк и состояние (React): ключ проверяется независимо от генератора."""
import re

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import frontend_framework as fw

from .._bank_helpers import area_codes, make

AREA_CODES = area_codes("framework", "frontend")


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)
    assert r.space_estimate >= 50_000, (code, r.space_estimate)


def _numbers(text: str) -> set[float]:
    return {float(x) for x in re.findall(r"(?<![\w#.-])-?\d+(?:\.\d+)?", text)}


def _mcq_parts(inst):
    key = inst.prompt.options[inst.answer]
    return key, [o for i, o in enumerate(inst.prompt.options) if i != inst.answer]


# ------------------------------------------------------------------ props_vs_state
def test_props_vs_state_key():
    rows = set()
    for seed in range(200):
        inst = make("fe.framework.props_vs_state", seed)
        key, others = _mcq_parts(inst)
        if "вычисляется из этих props" in inst.prompt.text:
            assert key == fw.PVS_OPTIONS["derive"]  # производное значение не хранят, а вычисляют
            rows.add("derive")
        else:
            assert "из props его не вычислить" in inst.prompt.text and key == fw.PVS_OPTIONS["state"]
            rows.add("state")
        assert set(others) <= set(fw.PVS_OPTIONS.values()) - {key}
    assert rows == {"derive", "state"}


# ------------------------------------------------------------------ list_keys
def test_list_keys_key():
    for seed in range(200):
        inst = make("fe.framework.list_keys", seed)
        key, others = _mcq_parts(inst)
        assert key in fw.LIST_KEYS_CORRECT and set(others) <= set(fw.LIST_KEYS_WRONG)
        assert re.search(r"key=\{(index|i|idx)\}", inst.prompt.code)  # в коде ключ — индекс
        assert "defaultValue" in inst.prompt.code  # у полей своё состояние в DOM, оно и «съезжает»


# ------------------------------------------------------------------ stale_setstate_count
def test_stale_setstate_count_key():
    seen = set()
    for seed in range(200):
        inst = make("fe.framework.stale_setstate_count", seed)
        code = inst.prompt.code
        var, setter, start = re.search(r"const \[(\w+), (\w+)\] = useState\((\d+)\);", code).groups()
        calls = re.findall(rf"^    {setter}\({var} \+ (\d+)\);$", code, re.M)
        assert 2 <= len(calls) <= 5
        # все вызовы читают одно и то же значение из замыкания рендера: побеждает последний
        assert inst.answer == int(start) + int(calls[-1])
        assert inst.answer not in _numbers(code)
        seen.add(inst.answer)
    assert len(seen) >= 30


# ------------------------------------------------------------------ functional_update_count
def test_functional_update_count_key():
    seen = set()
    for seed in range(200):
        inst = make("fe.framework.functional_update_count", seed)
        code = inst.prompt.code
        var, setter, start = re.search(r"const \[(\w+), (\w+)\] = useState\((\d+)\);", code).groups()
        calls = re.findall(rf"^    {setter}\(\((\w+)\) => \1 \+ (\d+)\);$", code, re.M)
        assert 2 <= len(calls) <= 5
        assert inst.answer == int(start) + sum(int(d) for _, d in calls)  # каждый вызов видит свежее значение
        assert inst.answer not in _numbers(code)
        seen.add(inst.answer)
    assert len(seen) >= 30


# ------------------------------------------------------------------ controlled_input
def test_controlled_input_key():
    for seed in range(200):
        inst = make("fe.framework.controlled_input", seed)
        code = inst.prompt.code
        init = re.search(r"useState\('([^']*)'\)", code).group(1)
        var = re.search(r"const \[(\w+),", code).group(1)
        assert f"value={{{var}}}" in code and "onChange" not in code and "defaultValue" not in code
        key, _ = _mcq_parts(inst)
        assert key.startswith(f"«{init}» —")  # поле остаётся с исходным значением


# ------------------------------------------------------------------ effect_runs
def test_effect_runs_key():
    kinds = set()
    for seed in range(300):
        inst = make("fe.framework.effect_runs", seed)
        code = inst.prompt.code
        a, b = re.search(r"function \w+\(\{ (\w+), (\w+) \}\)", code).groups()
        deps_m = re.search(r"\}, \[([\w, ]*)\]\);", code)
        deps = None if deps_m is None else [d for d in deps_m.group(1).split(", ") if d]
        table = inst.prompt.tables[0]
        assert table.columns == ("рендер", a, b)
        rows = [dict(zip(table.columns, r, strict=True)) for r in table.rows]
        runs = 1  # при монтировании эффект выполняется всегда
        for prev, cur in zip(rows, rows[1:], strict=False):
            if deps is None or any(prev[d] != cur[d] for d in deps):
                runs += 1
        assert inst.answer == runs and 4 <= len(rows) <= 7
        kinds.add("none" if deps is None else "".join("a" if d == a else "b" for d in deps) or "[]")
    assert kinds == {"none", "[]", "a", "b", "ab"}


def _assert_no_line_label(text, key):
    """Ключ не назван в тексте как номер строки."""
    assert not re.search(rf"(?i)(строк\w*|line)\s*(№\s*)?{key}\b", text), text


def _numbered_hint_matches(inst):
    lines = inst.prompt.code.split("\n")
    assert inst.prompt.answer_hint == "Номер строки:\n" + "\n".join(f"{n:>2}| {ln}" for n, ln in enumerate(lines, 1))
    return lines


# ------------------------------------------------------------------ stale_interval_line
def test_stale_interval_line_key():
    positions = set()
    for seed in range(200):
        inst = make("fe.framework.stale_interval_line", seed)
        lines = _numbered_hint_matches(inst)
        var, setter = re.search(r"const \[(\w+), (\w+)\] = useState\(\d+\);", inst.prompt.code).groups()
        # строка, где колбэк интервала читает значение из замыкания первого рендера
        stale = [i for i, ln in enumerate(lines, 1) if re.fullmatch(rf"\s+{setter}\({var} \+ \d+\);", ln)]
        assert stale == [inst.answer]
        start = next(i for i, ln in enumerate(lines) if "setInterval(" in ln)
        assert start < inst.answer - 1 and "}, []);" in inst.prompt.code  # интервал создаётся один раз
        assert "один раз" in inst.prompt.text  # поэтому правка зависимостей — не исправление
        _assert_no_line_label(inst.prompt.text, inst.answer)
        assert 10 <= len(lines) <= 15
        positions.add(inst.answer)
    assert len(positions) >= 4


# ------------------------------------------------------------------ lift_state
def test_lift_state_key():
    for seed in range(200):
        inst = make("fe.framework.lift_state", seed)
        key, others = _mcq_parts(inst)
        parent = re.search(r"^Внутри (\w+)", inst.prompt.text).group(1)
        assert key.startswith("Поднять") and parent in key  # общее состояние — у общего родителя
        assert not any(o.startswith("Поднять") for o in others)


# ------------------------------------------------------------------ memo_rerenders
def test_memo_rerenders_key():
    literals = set()
    for seed in range(200):
        inst = make("fe.framework.memo_rerenders", seed)
        clicks = int(re.search(r"нажал кнопку (\d+) раз", inst.prompt.text).group(1))
        child = re.search(r"«render (\w+)»", inst.prompt.text).group(1)
        assert f"const {child} = React.memo(" in inst.prompt.code
        # проп ребёнка — литерал, новый на каждом рендере родителя: memo не спасает
        prop_line = re.search(rf"<{child} (\w+)=\{{(.+)\}} />", inst.prompt.code).group(2)
        assert prop_line[0] in "{[(" or prop_line.startswith("()")
        literals.add(prop_line[0])
        assert inst.answer == clicks + 1 and inst.answer not in _numbers(inst.prompt.code)
    assert len(literals) == 3


# ------------------------------------------------------------------ effect_cleanup_order
def test_effect_cleanup_order_key():
    variants = set()
    for seed in range(200):
        inst = make("fe.framework.effect_cleanup_order", seed)
        t = inst.prompt.text
        prop, x1 = re.search(r"монтируется с (\w+) = (\S+?),", t).groups()
        x2 = re.search(rf"с {prop} = (\S+?)(?:,| и)", t[t.index("затем"):]).group(1)
        steps = inst.prompt.steps
        # независимый порядок React: рендер → эффект; при смене зависимости — рендер, очистка старого, новый эффект
        if "размонтируется" in t:
            want = [f"Рендер с {prop} = {x1}", f"Эффект для {x1}", f"Рендер с {prop} = {x2}", f"Очистка для {x1}",
                    f"Эффект для {x2}", f"Очистка для {x2} при размонтировании"]
            variants.add("unmount")
        else:
            want = [f"Рендер с {prop} = {x1}", f"Эффект для {x1}", f"Повторный рендер с тем же {prop} = {x1}",
                    f"Рендер с {prop} = {x2}", f"Очистка для {x1}", f"Эффект для {x2}"]
            variants.add("same_deps")
        assert len(steps) == 6 and len(set(steps)) == 6
        order = [steps[i - 1] for i in inst.answer]
        assert [_canon_step(s, prop) for s in order] == want, (order, want)
        assert tuple(inst.answer) != tuple(range(1, 7))  # показ не совпадает с готовым ответом
    assert variants == {"unmount", "same_deps"}


def _canon_step(step: str, prop: str) -> str:
    """Шаг из задания → каноническая запись: «Эффект: подключение к комнате X» → «Эффект для X»."""
    if m := re.fullmatch(r"(Эффект|Очистка)( при размонтировании)?: .* (\S+)", step):
        return f"{m.group(1)} для {m.group(3)}" + (" при размонтировании" if m.group(2) else "")
    return step


# ------------------------------------------------------------------ fetch_race_line
def test_fetch_race_line_key():
    positions = set()
    for seed in range(200):
        inst = make("fe.framework.fetch_race_line", seed)
        lines = _numbered_hint_matches(inst)
        flag = re.search(r"let (\w+) = false;", inst.prompt.code).group(1)
        setter = re.search(r"const \[\w+, (\w+)\] = useState\(null\);", inst.prompt.code).group(1)
        hits = [i for i, ln in enumerate(lines, 1) if re.fullmatch(rf"\s+{setter}\(\w+\);", ln)]
        assert hits == [inst.answer]
        # флаг отмены объявлен и выставляется при очистке, но при записи результата не проверяется
        assert re.search(rf"{flag} = true;", inst.prompt.code)
        assert inst.prompt.code.count(flag) == 2
        assert 12 <= len(lines) <= 18
        _assert_no_line_label(inst.prompt.text, inst.answer)
        positions.add(inst.answer)
    assert len(positions) >= 3


# ------------------------------------------------------------------ context_rerender
def test_context_rerender_key():
    for seed in range(200):
        inst = make("fe.framework.context_rerender", seed)
        key, others = _mcq_parts(inst)
        assert key in [c.format(**_ctx_names(inst)) for c in fw.CONTEXT_CORRECT]
        assert "Provider value={{" in inst.prompt.code  # value — новый объект на каждом рендере провайдера
        assert all(any(o == w.format(**_ctx_names(inst)) for w in fw.CONTEXT_WRONG) for o in others)


def _ctx_names(inst) -> dict:
    consumer = re.search(r"^function (\w+)\(\{ label \}\)", inst.prompt.code, re.M).group(1)
    return {"consumer": consumer}


# ------------------------------------------------------------------ hydration_mismatch
def test_hydration_mismatch_key():
    sources = set()
    for seed in range(200):
        inst = make("fe.framework.hydration_mismatch", seed)
        key, others = _mcq_parts(inst)
        assert key in fw.HYDRATION_CORRECT and set(others) <= set(fw.HYDRATION_WRONG)
        src = re.search(r"Date\.now\(\)|Math\.random\(\)|toLocaleTimeString\(\)|window\.innerWidth", inst.prompt.code)
        assert src, inst.prompt.code  # в рендере есть значение, разное на сервере и в браузере
        assert "useEffect" not in inst.prompt.code
        sources.add(src.group(0))
    assert len(sources) == 4



def test_memo_rerenders_count_agrees_with_noun():
    for seed in range(200):
        t = make("fe.framework.memo_rerenders", seed).prompt.text
        assert not re.search(r"\b[234] раз\b", t), t  # «2 раз» — ошибка согласования


def test_props_vs_state_names_are_consistent():
    female_first = {"Анна", "Ирина", "Мария", "Ольга", "Елена"}
    for seed in range(200):
        code = make("fe.framework.props_vs_state", seed).prompt.code
        if m := re.search(r'firstName="(\w+)" lastName="(\w+)"', code) or re.search(r'name="(\w+) (\w+)"', code):
            first, last = m.groups()
            assert (first in female_first) == last.endswith("а"), (first, last)
        if m := re.search(r'label="([^"]+)"', code):
            assert m.group(1) not in fw.FIRST_NAMES  # подпись элемента интерфейса, а не имя человека


def test_list_keys_option_does_not_name_another_variable():
    for seed in range(100):
        inst = make("fe.framework.list_keys", seed)
        assert "item.id" not in inst.prompt.options[inst.answer] or "item" in inst.prompt.code
