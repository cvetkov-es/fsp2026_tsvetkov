import re

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.canon import canonical
from app.assessment.bank.checks import check_family

from ._helpers import assert_mcq_form, make, skill_codes

CODES = skill_codes("frontend_basics")
SEEDS = range(40)


@pytest.mark.parametrize("code", CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)


def test_volume_and_areas():
    assert len(CODES) == 10
    assert sorted(REGISTRY[c].level for c in CODES) == [1, 1, 2, 2, 2, 2, 3, 3, 3, 4]
    assert {REGISTRY[c].area for c in CODES} == {"js", "markup"}
    assert not any(c.startswith("fe.") for c in CODES)


def test_array_mutators_by_emulation():
    for seed in SEEDS:
        inst = make("sk.fe.array_mutators_output", seed)
        lines = inst.prompt.code.splitlines()
        xs = [int(x) for x in re.search(r"\[(.*)\]", lines[0]).group(1).split(", ")]
        for line in lines[1:-1]:
            op, args = re.search(r"\.(\w+)\((.*)\);", line).groups()
            a = [int(x) for x in args.split(", ")] if args else []
            if op == "push":
                xs.append(a[0])
            elif op == "pop":
                xs.pop()
            elif op == "shift":
                xs.pop(0)
            elif op == "unshift":
                xs.insert(0, a[0])
            else:
                xs[a[0]:a[0] + a[1]] = a[2:]
        assert inst.answer == canonical("text", ",".join(map(str, xs)))


def test_hex_to_rgb():
    for seed in SEEDS:
        inst = make("sk.fe.hex_to_rgb", seed)
        h = re.search(r"#([0-9a-fA-F]{6})", inst.prompt.code).group(1)
        assert inst.answer == f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


OPS = {">": lambda a, b: a > b, "<": lambda a, b: a < b, ">=": lambda a, b: a >= b, "===": lambda a, b: a == b}
ARITH = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b}


def test_template_ternary():
    for seed in SEEDS:
        inst = make("sk.fe.template_ternary_output", seed)
        code = inst.prompt.code
        a, b = map(int, re.search(r"const a = (-?\d+), b = (-?\d+);", code).groups())
        op, w1, w2, ar = re.search(r"\$\{a (\S+) b \? '([^']+)' : '([^']+)'\}: \$\{a (\S) b\}", code).groups()
        assert inst.answer == f"{w1 if OPS[op](a, b) else w2}: {ARITH[ar](a, b)}"


def test_object_keys_order():
    for seed in SEEDS:
        inst = make("sk.fe.object_keys_order_output", seed)
        keys = re.findall(r"(\w+): ", re.search(r"\{ (.*) \}", inst.prompt.code).group(1))
        ints = sorted(int(k) for k in keys if k.isdigit())
        assert inst.answer == canonical("text", ",".join([*map(str, ints), *[k for k in keys if not k.isdigit()]]))
        assert any(k.isdigit() for k in keys) and any(not k.isdigit() for k in keys)


def test_rem_em_px():
    for seed in SEEDS:
        inst = make("sk.fe.rem_em_px", seed)
        css = inst.prompt.code
        root = float(re.search(r"html \{ font-size: (\d+)px; \}", css).group(1))
        parent = float(re.search(r"\{ font-size: ([\d.]+)em; \}", css).group(1))
        value, unit = re.search(r": ([\d.]+)(r?em); \}$", css).groups()
        px = float(value) * root * (1 if unit == "rem" else parent)
        assert px.is_integer() and inst.answer == px


def test_media_query_last_match_wins():
    for seed in SEEDS:
        inst = make("sk.fe.media_query_winner", seed)
        w = int(re.search(r"ширина окна (\d+)px", inst.prompt.text).group(1))
        css = inst.prompt.code
        color = re.search(r"^\.\w+ \{ color: (\w+); \}", css).group(1)
        for kind, px, c in re.findall(r"@media \((min|max)-width: (\d+)px\) \{ \.\w+ \{ color: (\w+); \} \}", css):
            if (kind == "min" and w >= int(px)) or (kind == "max" and w <= int(px)):
                color = c
        assert inst.prompt.options[inst.answer] == color
    assert_mcq_form("sk.fe.media_query_winner")


def test_label_for_matches_id():
    for seed in SEEDS:
        inst = make("sk.fe.label_for_name", seed)
        ok = []
        for o in inst.prompt.options:
            f = re.search(r'<label for="([^"]+)"', o)
            i = re.search(r'<input id="([^"]+)"', o)
            ok.append(bool(f and i and f.group(1) == i.group(1)))
        assert ok.count(True) == 1 and ok.index(True) == inst.answer
    assert_mcq_form("sk.fe.label_for_name")


JS_VALUES = {"0": 0, "''": "", "null": None, "undefined": "undefined", "42": 42, "'ok'": "ok"}


def _falsy(v) -> bool:
    return v in (0, "", None, "undefined")


def _js_str(v) -> str:
    return "null" if v is None else str(v)


def test_nullish_vs_or():
    for seed in SEEDS:
        inst = make("sk.fe.nullish_vs_or_output", seed)
        code = inst.prompt.code
        a = JS_VALUES[re.search(r"const a = (.+);", code).group(1)]
        b = JS_VALUES[re.search(r"const b = (.+);", code).group(1)]
        o = re.search(r"const o = (.+);", code).group(1)
        ox = "undefined" if o in ("null", "undefined", "{}") else JS_VALUES[re.search(r"x: (.+) \}", o).group(1)]
        d1, d2, d3 = re.search(r"\$\{a \?\? (\w+)\}\] \[\$\{b \|\| (\w+)\}\] \[\$\{o\?\.x \?\? (\w+)\}", code).groups()
        r1 = d1 if a in (None, "undefined") else a
        r2 = d2 if _falsy(b) else b
        r3 = d3 if ox in (None, "undefined") else ox
        assert inst.answer == f"[{_js_str(r1)}] [{_js_str(r2)}] [{_js_str(r3)}]"


def test_destructuring_default_only_for_undefined():
    for seed in SEEDS:
        inst = make("sk.fe.destructuring_defaults_output", seed)
        code = inst.prompt.code
        defaults = dict(re.findall(r"(\w) = (\w+)", re.search(r"const \{ (.*) \} =", code).group(1)))
        src = dict(re.findall(r"(\w): ([^,}]+)", re.search(r"\} = \{ (.*) \};", code).group(1)))
        out = []
        for k in sorted(defaults):
            v = src.get(k, "undefined").strip()
            out.append(defaults[k] if v == "undefined" else JS_VALUES[v] if v in JS_VALUES else v)
        assert inst.answer == " ".join(f"[{_js_str(v)}]" for v in out)


def test_fetch_rejects_only_on_network_error():
    for seed in SEEDS:
        inst = make("sk.fe.fetch_404_flow", seed)
        status = int(re.search(r"ответил статусом (\d+)", inst.prompt.text).group(1))
        checked = "if (!res.ok)" in inst.prompt.code
        expected = f"Ошибка: HTTP {status}" if checked and not 200 <= status <= 299 else f"OK: {status}"
        assert inst.prompt.options[inst.answer] == expected
    assert_mcq_form("sk.fe.fetch_404_flow")
