import ast
import re

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import backend_lang as lang_module

from ._helpers import area_codes
from ._helpers import make as _make

AREA_CODES = area_codes("lang")
SEEDS = range(30)


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


def test_int_division_key():
    for seed in SEEDS:
        inst = _make("be.lang.int_division_output", seed)
        x, y = map(int, re.findall(r"= (\d+)", inst.prompt.code))
        q, r = map(int, inst.answer.split())
        assert q * y + r == x and 0 <= r < y
        assert 10 <= x <= 9999 and 2 <= y <= 97


def test_dict_get_default_options():
    code = "be.lang.dict_get_default"
    for seed in SEEDS:
        inst = _make(code, seed)
        tree = ast.parse(inst.prompt.code)
        mapping = ast.literal_eval(tree.body[0].value)
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get")
        key, default = (ast.literal_eval(a) for a in call.args)
        assert key not in mapping and 3 <= len(mapping) <= 5
        opts = inst.prompt.options
        assert len(opts) == 4 and len(set(opts)) == 4
        assert opts[inst.answer] == str(default)
        assert str(default) not in [str(v) for v in mapping.values()]
        assert "None" in opts and any("KeyError" in o for o in opts)
        assert str(next(iter(mapping.values()))) in opts
    assert len({_make(code, s).answer for s in SEEDS}) > 1


def test_string_slicing_key():
    for seed in SEEDS:
        inst = _make("be.lang.string_slicing_output", seed)
        code = inst.prompt.code
        word = re.search(r'= "([a-z]+)"', code).group(1)
        assert 6 <= len(word) <= 12
        call = code.splitlines()[-1]
        parts = re.findall(r"\w+\[([^\]]*)\]", call)
        assert len(parts) == 3
        outs = []
        for p in parts:
            bounds = [int(v) if v else None for v in re.split(":", p)] if ":" in p else None
            assert bounds
            outs.append(word[slice(*bounds)])
        assert inst.answer == " ".join(outs)


def test_set_ops_len_key():
    seen = set()
    for seed in SEEDS:
        inst = _make("be.lang.set_ops_len", seed)
        code = inst.prompt.code
        lists = [ast.literal_eval(m) for m in re.findall(r"\[[\d, ]+\]", code)]
        assert len(lists) == 2 and all(8 <= len(x) <= 12 for x in lists)
        a, b = map(set, lists)
        op = re.search(r"len\(\w+ ([|&-]) \w+\)", code).group(1)
        want = {"|": len(a | b), "&": len(a & b), "-": len(a - b)}[op]
        seen.add(op)
        assert int(inst.answer) == want
        assert not re.search(r"\d", inst.prompt.text)
    assert seen == {"|", "&", "-"}


def test_mutable_default_key():
    for seed in SEEDS:
        inst = _make("be.lang.mutable_default_output", seed)
        lines = inst.prompt.code.splitlines()
        shared: list[int] = []
        for ln in lines[3:-1]:
            m = re.fullmatch(r"\w+\((\d+)(, \[\])?\)", ln)
            assert m, ln
            if m.group(2):
                continue
            shared.append(int(m.group(1)))
        last = lines[-1]
        n_explicit = sum(1 for ln in lines[3:-1] if ln.endswith("[])"))
        assert n_explicit == 1
        m = re.fullmatch(r"print\(\w+\((\d+)\)\)", last)
        assert m, last
        shared.append(int(m.group(1)))
        assert inst.answer == str(shared)
        assert 3 <= len(lines) - 3 <= 4  # вызовов вместе с print


def test_negative_floor_div_key():
    for seed in SEEDS:
        inst = _make("be.lang.negative_floor_div_output", seed)
        x, y = map(int, re.findall(r"= (\d+)", inst.prompt.code))
        assert x % y != 0 and 7 <= x <= 999 and 2 <= y <= 19
        q, r, t = map(int, inst.answer.split())
        assert q * y + r == -x and 0 <= r < y
        assert t == -(x // y) and t == q + 1


def test_closure_late_binding_key():
    for seed in SEEDS:
        inst = _make("be.lang.closure_late_binding_output", seed)
        code = inst.prompt.code
        n = int(re.search(r"range\((\d+)\)", code).group(1))
        k = int(re.search(r"[*] (\d+)|(\d+) [*]", code).group(0).replace("*", "").strip())
        vals = ast.literal_eval(inst.answer)
        assert len(vals) == n and set(vals) == {(n - 1) * k}


def test_generator_exhaustion_key():
    for seed in SEEDS:
        inst = _make("be.lang.generator_exhaustion_output", seed)
        code = inst.prompt.code
        m = re.search(r"\((.+) for (\w+) in range\(1, (\d+)\)\)", code)
        expr, var, stop = m.group(1), m.group(2), int(m.group(3))
        vals = [eval(expr, {}, {var: x}) for x in range(1, stop)]  # noqa: S307
        first_fn = re.search(r"print\((\w+)\(", code).group(1)
        first = {"sum": sum, "max": max, "min": min}[first_fn](vals)
        tail = "0" if "len(list(" in code else "[]"
        assert inst.answer == f"{first} 0 {tail}"


def test_cpu_bound_mcq():
    correct = {r[0] for r in lang_module.CPU_ROWS}
    assert len({_make("be.lang.cpu_bound_parallelism", s).answer for s in SEEDS}) > 1
    for seed in SEEDS:
        inst = _make("be.lang.cpu_bound_parallelism", seed)
        assert inst.prompt.options[inst.answer] in correct
        for r in lang_module.CPU_ROWS:
            if inst.prompt.options[inst.answer] == r[0]:
                assert set(inst.prompt.options) == {r[0], *r[1]}
                assert r[0] not in r[1]


def test_lock_order_mcq():
    correct = {r[0] for r in lang_module.LOCK_ROWS}
    for seed in SEEDS:
        inst = _make("be.lang.lock_order_deadlock", seed)
        right = inst.prompt.options[inst.answer]
        assert right in correct and len(set(inst.prompt.options)) == 4
        row = next(r for r in lang_module.LOCK_ROWS if r[0] == right)
        assert set(inst.prompt.options) == {row[0], *row[1]} and right not in row[1]
    assert len({_make("be.lang.lock_order_deadlock", s).answer for s in SEEDS}) > 1


def test_mutable_hash_key_mcq_and_shown_output():
    correct = {r[0] for r in lang_module.HASH_ROWS}
    for seed in SEEDS:
        inst = _make("be.lang.mutable_hash_key", seed)
        right = inst.prompt.options[inst.answer]
        assert right in correct and len(inst.prompt.options) == 4 and len(set(inst.prompt.options)) == 4
        row = next(r for r in lang_module.HASH_ROWS if r[0] == right)
        assert set(inst.prompt.options) == {row[0], *row[1]} and right not in row[1]
        # независимый прогон: объект с изменённым полем не находится в set
        *body, last = inst.prompt.code.splitlines()
        env: dict = {"__name__": "__main__"}
        exec("\n".join(body), env)  # noqa: S102
        shown = eval(last[len("print("):-1], env)  # noqa: S307
        assert shown is False and f"печатает {shown}" in inst.prompt.text
    assert len({_make("be.lang.mutable_hash_key", s).answer for s in SEEDS}) > 1


def test_async_blocking_bug_key():
    blocking = re.compile(r"time\.sleep\(|requests\.get\(|open\(.*\)\.read\(\)")
    for seed in SEEDS:
        inst = _make("be.lang.async_blocking_bug", seed)
        lines = inst.prompt.code.splitlines()
        assert 12 <= len(lines) <= 14
        assert 3 <= sum("await " in ln for ln in lines) <= 4
        ans = inst.answer
        ans = int(ans)
        assert blocking.search(lines[ans - 1]) and "await" not in lines[ans - 1]
        for n, ln in enumerate(lines, start=1):
            if n == ans or ln.startswith("async def"):
                continue
            assert not blocking.search(ln)
            if re.search(r"\w\(", ln):
                assert "await " in ln, ln
        assert not re.search(r"\d", inst.prompt.text)
        ast.parse(inst.prompt.code)
    assert len({_make("be.lang.async_blocking_bug", s).answer for s in SEEDS}) > 3


MCQ_ROWS = {"be.lang.cpu_bound_parallelism": lang_module.CPU_ROWS,
            "be.lang.lock_order_deadlock": lang_module.LOCK_ROWS,
            "be.lang.mutable_hash_key": lang_module.HASH_ROWS}


@pytest.mark.parametrize("code", sorted(MCQ_ROWS))
def test_mcq_options_have_symmetric_length(code):
    for correct, distractors in MCQ_ROWS[code]:
        lens = [len(o) for o in (correct, *distractors)]
        assert max(lens) <= 1.4 * min(lens), (code, lens)


@pytest.mark.parametrize("code", sorted(MCQ_ROWS))
def test_key_is_neither_longest_nor_shortest_in_its_row(code):
    """Длина варианта не выдаёт ключ ни в одной строке таблицы сценариев."""
    for correct, distractors in MCQ_ROWS[code]:
        lens = [len(d) for d in distractors]
        assert min(lens) <= len(correct) <= max(lens), (code, correct, len(correct), lens)


def test_cpu_bound_text_has_at_most_one_colon_per_sentence():
    """Задача с двоеточием внутри («Монте-Карло: …») не даёт двух двоеточий в одном предложении."""
    tasks = set()
    for seed in range(200):
        text = _make("be.lang.cpu_bound_parallelism", seed).prompt.text
        tasks |= {t for t in lang_module.CPU_TASKS if t in text}
        for sentence in re.split(r"(?<=[.?])\s", text):
            assert sentence.count(":") <= 1, sentence
    assert any(":" in t for t in tasks)


def test_lock_options_are_diagnosis_and_fix():
    for correct, distractors in lang_module.LOCK_ROWS:
        for o in (correct, *distractors):
            diagnosis, fix = o.split("; ")
            assert ":" in diagnosis and fix and ":" not in fix


def test_no_number_noun_agreement_traps():
    """Число в тексте не должно склоняться: нет «N ядрами», «N тысяч»."""
    for code in ("be.lang.cpu_bound_parallelism", "be.lang.lock_order_deadlock"):
        for seed in range(200):
            text = _make(code, seed).prompt.text
            assert not re.search(r"\d+ (ядр|тысяч)", text), text
