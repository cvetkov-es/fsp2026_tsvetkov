"""Семантические тесты Frontend · HTML, CSS, доступность: ключ проверяется независимо от генератора."""
import re

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import frontend_markup as mk

from .._bank_helpers import area_codes, make, row_for

AREA_CODES = area_codes("markup", "frontend")


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


def _css_px(css: str, prop: str) -> list[int]:
    m = re.search(rf"^\s*{prop}: ([^;]+);$", css, re.M)
    return [int(x) for x in re.findall(r"(\d+)px", m.group(1))] if m else []


def _horizontal_padding(css: str) -> int:
    """Сумма левого и правого padding по правилам сокращённой записи (1–4 значения)."""
    p = _css_px(css, "padding")
    if len(p) == 1:
        return 2 * p[0]
    if len(p) in (2, 3):
        return 2 * p[1]  # второе значение — и правый, и левый отступ
    return p[1] + p[3]


# ------------------------------------------------------------------ semantic_tag
def test_semantic_tag_key():
    seen = set()
    for seed in range(200):
        inst = make("fe.markup.semantic_tag", seed)
        row = row_for(inst.prompt.text, mk.SEMANTIC_ROWS)
        _, correct, pool = row
        key = inst.prompt.options[inst.answer]
        others = [o for i, o in enumerate(inst.prompt.options) if i != inst.answer]
        assert key == correct and set(others) <= set(pool) and correct not in pool
        seen.add(correct)
    assert len(seen) == len(mk.SEMANTIC_ROWS)


# ------------------------------------------------------------------ content_box_width
def test_content_box_width_key():
    forms = set()
    for seed in range(200):
        inst = make("fe.markup.content_box_width", seed)
        css = inst.prompt.code
        assert "box-sizing: content-box;" in css
        width = _css_px(css, "width")[0]
        border = _css_px(css, "border")[0]
        assert inst.answer == width + _horizontal_padding(css) + 2 * border
        assert inst.answer not in _numbers(css)  # ключ не совпадает ни с одним числом в коде
        forms.add(len(_css_px(css, "padding")))
    assert forms == {1, 2, 3, 4}


# ------------------------------------------------------------------ specificity_winner
def _specificity(selector: str) -> tuple[int, int, int]:
    """(id, классы и атрибуты, типы) — независимый разбор: id, .класс, [атрибут], имя тега."""
    ids = len(re.findall(r"#[\w-]+", selector))
    classes = len(re.findall(r"\.[\w-]+", selector)) + len(re.findall(r"\[[^\]]+\]", selector))
    bare = re.sub(r"#[\w-]+|\.[\w-]+|\[[^\]]+\]", " ", selector)
    types = len(re.findall(r"(?:^|[\s>+~])([a-z][\w-]*)", bare))
    return ids, classes, types


def test_specificity_winner_key():
    with_id = 0
    for seed in range(300):
        inst = make("fe.markup.specificity_winner", seed)
        rules = re.findall(r"^  (.+?) \{ color: (\w+); \}$", inst.prompt.code, re.M)
        assert len(rules) == 4
        specs = [_specificity(sel) for sel, _ in rules]
        assert len(set(specs)) == 4  # равных специфичностей нет — порядок правил не решает
        winner = rules[specs.index(max(specs))][1]
        assert inst.prompt.options[inst.answer] == winner
        assert sorted(inst.prompt.options) == sorted(c for _, c in rules)
        with_id += any(s[0] for s in specs)
        # каждый селектор действительно выбирает элемент из разметки
        el = re.search(r'<(\w+) id="([\w-]+)" class="([\w-]+) ([\w-]+)" data-([\w-]+)="(\w+)">', inst.prompt.code)
        tag, id_, c1, c2, attr, _ = el.groups()
        for sel, _ in rules:
            last = re.split(r"[\s>]+", sel)[-1]
            assert re.fullmatch(rf"({tag})?(#{id_})?((\.{c1})|(\.{c2}))*(\[data-{attr}(=\"\w+\")?\])?", last), sel
    assert 0.3 * 300 < with_id < 0.9 * 300  # бывают задания и без селектора по id


# ------------------------------------------------------------------ border_box_content
def test_border_box_content_key():
    for seed in range(200):
        inst = make("fe.markup.border_box_content", seed)
        css = inst.prompt.code
        assert "box-sizing: border-box;" in css
        width, border = _css_px(css, "width")[0], _css_px(css, "border")[0]
        assert inst.answer == width - _horizontal_padding(css) - 2 * border > 0
        assert inst.answer not in _numbers(css)


# ------------------------------------------------------------------ alt_text
def test_alt_text_key():
    rows = set()
    for seed in range(300):
        inst = make("fe.markup.alt_text", seed)
        key = inst.prompt.options[inst.answer]
        if "декоративн" in inst.prompt.text:
            assert key == 'alt=""'  # декоративное изображение скрывают от скринридера пустым alt
            rows.add("decor")
        elif "график" in inst.prompt.text:
            a, b = re.search(r"с (\d+) до (\d+)", inst.prompt.text).groups()
            assert a in key and b in key  # alt передаёт данные графика
            rows.add("chart")
        else:
            company = re.search(r"логотип компании «(.+?)»", inst.prompt.text).group(1)
            assert key.startswith(f'alt="{company}') and "главн" in key  # назначение ссылки, а не вид
            rows.add("logo")
        assert all(o.startswith("alt=") or o == "Атрибут alt не указывать" for o in inst.prompt.options)
    assert rows == {"decor", "chart", "logo"}


# ------------------------------------------------------------------ flex_grow_width
def test_flex_grow_width_key():
    zero_grow = 0
    for seed in range(200):
        inst = make("fe.markup.flex_grow_width", seed)
        css = inst.prompt.code
        width = int(re.search(r"\.[\w-]+ \{\n  display: flex;\n  width: (\d+)px;\n  gap: (\d+)px;", css).group(1))
        gap = int(re.search(r"gap: (\d+)px;", css).group(1))
        items = re.findall(r"\.(\w+) \{ flex-grow: (\d+); flex-basis: (\d+)px; \}", css)
        assert 2 <= len(items) <= 3
        free = width - sum(int(b) for *_, b in items) - gap * (len(items) - 1)
        total_grow = sum(int(g) for _, g, _ in items)
        asked = re.search(r"ширина элемента \.(\w+)", inst.prompt.text).group(1)
        name, grow, basis = next(i for i in items if i[0] == asked)
        expected = int(basis) + free * int(grow) / total_grow
        assert free > 0 and float(expected).is_integer() and inst.answer == expected > 0
        if grow == "0":
            zero_grow += 1  # элемент без роста: ширина — его flex-basis (вход, а не утечка)
        else:
            assert inst.answer not in _numbers(css)
        assert "элементы пустые" in inst.prompt.text  # min-width: auto не ограничивает пустой элемент
    assert zero_grow >= 1  # бывает и элемент без роста: его ширина — flex-basis (доля — отдельный тест)


# ------------------------------------------------------------------ margin_collapse
def _margin(css_block: str, side: str) -> int:
    """Вертикальный отступ из margin-top / margin-bottom или сокращённой записи margin."""
    if m := re.search(rf"margin-{side}: (\d+)px;", css_block):
        return int(m.group(1))
    v = [int(t.removesuffix("px")) for t in re.search(r"margin: ([^;]+);", css_block).group(1).split()]
    top, bottom = (v[0], v[0]) if len(v) <= 2 else (v[0], v[2])  # 3–4 значения: верх, …, низ
    return top if side == "top" else bottom


def test_margin_collapse_key():
    padded = 0
    for seed in range(200):
        inst = make("fe.markup.margin_collapse", seed)
        css = inst.prompt.code.split("<style>")[1]
        first, second = re.findall(r"\.([\w-]+) \{\n(.*?)\n\}", css, re.S)
        bottom, top = _margin(first[1], "bottom"), _margin(second[1], "top")
        assert bottom > 0 and top > 0
        assert inst.answer == max(bottom, top)  # соседние вертикальные отступы схлопываются в больший
        assert re.search(rf'<div class="{first[0]}">.*</div>\n<div class="{second[0]}">', inst.prompt.code)
        padded += "padding" in css or "border" in css
    assert padded >= 100  # padding и border самих блоков не мешают схлопыванию между ними


# ------------------------------------------------------------------ icon_button_label
def test_icon_button_label_key():
    for seed in range(200):
        inst = make("fe.markup.icon_button_label", seed)
        key = inst.prompt.options[inst.answer]
        assert re.fullmatch(r'Добавить кнопке (атрибут )?aria-label="[^"]+"', key)
        action = re.search(r'aria-label="([^"]+)"', key).group(1)
        assert action.lower() in inst.prompt.text.lower()
        others = [o for i, o in enumerate(inst.prompt.options) if i != inst.answer]
        assert not any("aria-label" in o or "title" in o for o in others)  # у дистракторов имени нет
        assert "<button" in inst.prompt.code and "<svg" in inst.prompt.code and "aria-label" not in inst.prompt.code


# ------------------------------------------------------------------ cascade_important
def _cascade_winner(code: str) -> str:
    """Независимый каскад: важность → встроенный стиль → специфичность → порядок."""
    candidates = []
    inline = re.search(r'style="color: (\w+)( !important)?;"', code)
    if inline:
        candidates.append(((bool(inline.group(2)), 1, (0, 0, 0), 99), inline.group(1)))
    rules = re.findall(r"^  (.+?) \{ color: (\w+)( !important)?; \}$", code, re.M)
    for order, (sel, color, imp) in enumerate(rules):
        candidates.append(((bool(imp), 0, _specificity(sel), order), color))
    return max(candidates)[1]


def test_cascade_important_key():
    not_most_specific = with_inline = 0
    for seed in range(300):
        inst = make("fe.markup.cascade_important", seed)
        code = inst.prompt.code
        assert "!important" in code and "@layer" not in code
        assert inst.prompt.options[inst.answer] == _cascade_winner(code)
        rules = re.findall(r"^  (.+?) \{ color: (\w+)( !important)?; \}$", code, re.M)
        top_spec = max(rules, key=lambda r: _specificity(r[0]))[1]
        not_most_specific += inst.prompt.options[inst.answer] != top_spec
        with_inline += "style=" in code
        assert len(set(inst.prompt.options)) == 4
    assert not_most_specific >= 120 and 60 <= with_inline <= 240


# ------------------------------------------------------------------ grid_fr_width
ORDINALS = ("первой", "второй", "третьей", "четвёртой")


def test_grid_fr_width_key():
    for seed in range(200):
        inst = make("fe.markup.grid_fr_width", seed)
        css = inst.prompt.code
        width = int(re.search(r"^  width: (\d+)px;$", css, re.M).group(1))
        gap = int(re.search(r"column-gap: (\d+)px;", css).group(1))
        cols = re.search(r"grid-template-columns: (.+);", css).group(1).split()
        fixed = sum(int(c[:-2]) for c in cols if c.endswith("px"))
        frs = [int(c[:-2]) if c.endswith("fr") else 0 for c in cols]
        unit = (width - fixed - gap * (len(cols) - 1)) / sum(frs)
        k = ORDINALS.index(re.search(r"ширина (\w+) колонки", inst.prompt.text).group(1))
        assert cols[k].endswith("fr") and float(unit * frs[k]).is_integer()
        assert inst.answer == unit * frs[k] and inst.answer not in _numbers(css)
        assert 3 <= len(cols) <= 4 and any(c.endswith("px") for c in cols)


# ------------------------------------------------------------------ positive_tabindex
def test_positive_tabindex_key():
    for seed in range(200):
        inst = make("fe.markup.positive_tabindex", seed)
        key = inst.prompt.options[inst.answer]
        assert key in mk.TABINDEX_CORRECT
        assert all(o in mk.TABINDEX_WRONG for i, o in enumerate(inst.prompt.options) if i != inst.answer)
        values = [int(v) for v in re.findall(r'tabindex="(-?\d+)"', inst.prompt.code)]
        assert values and all(v > 0 for v in values) and len(set(values)) == len(values)


# ------------------------------------------------------------------ stacking_context
def _top_element(code: str) -> str:
    """Независимое правило: внутри родителя, создающего контекст наложения, потомок сравнивается с соседями
    только уровнем родителя; иначе — своим z-index в корневом контексте."""
    blocks = dict(re.findall(r"^\.([\w-]+) \{ (.+?) \}$", code, re.M))
    parent, child = re.search(r'<div class="([\w-]+)">\n  <div class="([\w-]+)"></div>', code).groups()
    siblings = [n for n in blocks if n not in (parent, child)]

    def z(name):
        m = re.search(r"z-index: (-?\d+)", blocks[name])
        return int(m.group(1)) if m else None

    p = blocks[parent]
    creates = z(parent) is not None or "opacity" in p or "transform" in p
    levels = {n: z(n) for n in siblings}
    if creates:
        levels[child] = z(parent) if z(parent) is not None else 0  # группа родителя, потомок наверху группы
    else:
        levels[child] = z(child)
    assert len(set(levels.values())) == len(levels)
    return max(levels, key=levels.get)


def test_stacking_context_key():
    winners, kinds = {"child": 0, "other": 0}, set()
    for seed in range(300):
        inst = make("fe.markup.stacking_context", seed)
        code = inst.prompt.code
        top = _top_element(code)
        assert inst.prompt.options[inst.answer] == f".{top}"
        child = re.search(r'<div class="[\w-]+">\n  <div class="([\w-]+)"></div>', code).group(1)
        winners["child" if top == child else "other"] += 1
        parent_css = re.search(r'<div class="([\w-]+)">\n', code).group(1)
        rule = re.search(rf"^\.{parent_css} \{{ (.+?) \}}$", code, re.M).group(1)
        kinds.add("z" if "z-index" in rule else "opacity" if "opacity" in rule
                  else "transform" if "transform" in rule else "none")
    assert kinds == {"z", "opacity", "transform", "none"}
    assert 0.25 < winners["child"] / 300 < 0.75


# ------------------------------------------------------------------ contrast_ratio
def _luminance(hex_color: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def test_contrast_ratio_key():
    for seed in range(200):
        inst = make("fe.markup.contrast_ratio", seed)
        colors = re.findall(r"#[0-9a-f]{6}", inst.prompt.text)
        shown = [float(x) for x in re.findall(r"относительная яркость (0\.\d{4})", inst.prompt.text)]
        assert len(colors) == 2 and len(shown) == 2
        for c, lum in zip(colors, shown, strict=True):
            assert abs(_luminance(c) - lum) < 5e-5  # яркости в тексте посчитаны верно
        hi, lo = max(shown), min(shown)
        ratio = (hi + 0.05) / (lo + 0.05)
        assert inst.answer == round(ratio, 1)
        assert abs(ratio * 10 - round(ratio * 10) - 0.5) > 0.1 and abs(ratio * 10 - round(ratio * 10) + 0.5) > 0.1
        assert round(hi / lo, 1) != inst.answer  # формула без +0.05 даёт другой ответ


def test_stacking_context_max_z_heuristic_is_weak():
    """«Сверху тот, у кого больше z-index» (без учёта контекста наложения) угадывает не чаще половины."""
    n = hits = 0
    for seed in range(600):
        inst = make("fe.markup.stacking_context", seed)
        code = inst.prompt.code
        parent = re.search(r'<div class="([\w-]+)">\n  <div', code).group(1)
        zs = {name: int(z) for name, z in re.findall(
            r"^\.([\w-]+) \{ position: (?:absolute|relative); z-index: (-?\d+); \}$", code, re.M) if name != parent}
        hits += f".{max(zs, key=zs.get)}" == inst.prompt.options[inst.answer]
        n += 1
    assert hits / n <= 0.5, hits / n



def test_flex_zero_grow_items_are_rare():
    zero = 0
    for seed in range(400):
        inst = make("fe.markup.flex_grow_width", seed)
        asked = re.search(r"ширина элемента \.(\w+)", inst.prompt.text).group(1)
        zero += bool(re.search(rf"\.{asked} \{{ flex-grow: 0;", inst.prompt.code))
    assert 0.01 * 400 <= zero <= 0.1 * 400, zero


def test_stacking_context_overlap_is_an_assumption():
    assert make("fe.markup.stacking_context", 0).prompt.text.startswith("Считайте, что")
