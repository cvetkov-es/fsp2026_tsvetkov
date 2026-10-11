"""Навык «Основы фронтенда»: области js и markup. Концепции — базовые, не повторяют семейства fe.*: навык проходит, например, бэкендер.

«Что выведет код» — настоящий вывод QuickJS нашего шаблонного кода; CSS и разметка — правила спецификаций.
"""
import math
import random

from app.assessment.bank.base import SHUFFLES, Generated, Prompt, family, mcq
from app.assessment.bank.jsrun import run_js_snippet

SPEC = "skill:frontend_basics"
ARRAYS = ("xs", "items", "ids", "queue", "stack", "scores", "list", "nums")
MAX_N = 99


def _output(code: str, hint: str, radicals: tuple) -> Generated:
    return Generated("text", Prompt(text="Что выведет код?", code=code, language="javascript", answer_hint=hint),
                     run_js_snippet(code), radicals)


# --- sk.fe.array_mutators_output --------------------------------------------------------------
@family(code="sk.fe.array_mutators_output", specialization=SPEC, area="js", level=1, fmt="output",
        space_size=len(ARRAYS) * MAX_N**4 * 5**3, median_time_s=45)
def array_mutators_output(rng: random.Random) -> Generated:
    name = rng.choice(ARRAYS)
    xs = [rng.randint(1, MAX_N) for _ in range(rng.randint(4, 6))]
    lines = [f"const {name} = [{', '.join(map(str, xs))}];"]
    size = len(xs)
    for _ in range(rng.randint(3, 4)):
        op = rng.choice(("push", "pop", "shift", "unshift", "splice") if size > 2 else ("push", "unshift"))
        if op in ("push", "unshift"):
            lines.append(f"{name}.{op}({rng.randint(1, MAX_N)});")
            size += 1
        elif op in ("pop", "shift"):
            lines.append(f"{name}.{op}();")
            size -= 1
        else:
            i, n = rng.randrange(size), rng.randint(0, 2)
            n = min(n, size - i)
            ins = [rng.randint(1, MAX_N) for _ in range(rng.randint(0, 1) if n else 1)]
            lines.append(f"{name}.splice({', '.join(map(str, [i, n, *ins]))});")
            size += len(ins) - n
    lines.append(f"console.log({name}.join(','));")
    return _output("\n".join(lines), "Числа через запятую, как их выведет join(',')", ("array_mutators",))


# --- sk.fe.hex_to_rgb -------------------------------------------------------------------------
SELECTORS = (".badge", ".btn", "h1", ".card", ".link", ".alert", ".tag", ".logo", "nav a", ".price")
PROPS = ("color", "background-color", "border-color", "outline-color")


@family(code="sk.fe.hex_to_rgb", specialization=SPEC, area="markup", level=1, fmt="calc",
        space_size=256**3 * len(SELECTORS) * len(PROPS), median_time_s=45)
def hex_to_rgb(rng: random.Random) -> Generated:
    r, g, b = (rng.randrange(256) for _ in range(3))
    hexs = f"#{r:02x}{g:02x}{b:02x}"
    hexs = hexs.upper() if rng.random() < 0.5 else hexs
    return Generated("text", Prompt(
        text="Запишите тот же цвет в формате rgb(r, g, b).",
        code=f"{rng.choice(SELECTORS)} {{ {rng.choice(PROPS)}: {hexs}; }}", language="css",
        answer_hint="Например: rgb(255, 128, 0)"), f"rgb({r}, {g}, {b})", ("hex_color",))


# --- sk.fe.template_ternary_output ------------------------------------------------------------
WORD_PAIRS = (("больше", "не больше"), ("да", "нет"), ("скидка", "без скидки"), ("в наличии", "под заказ"),
              ("онлайн", "офлайн"), ("готово", "в работе"), ("премиум", "базовый"), ("открыто", "закрыто"))
TERNARY_OPS = (">", "<", ">=", "===")
ARITH_OPS = ("+", "-", "*")


@family(code="sk.fe.template_ternary_output", specialization=SPEC, area="js", level=2, fmt="output",
        space_size=71**2 * len(TERNARY_OPS) * len(ARITH_OPS) * len(WORD_PAIRS), median_time_s=45)
def template_ternary_output(rng: random.Random) -> Generated:
    a = rng.randint(-20, 50)
    b = a if rng.random() < 0.2 else rng.randint(-20, 50)  # равенство — для >= и ===
    yes, no = rng.choice(WORD_PAIRS)
    code = "\n".join([
        f"const a = {a}, b = {b};",
        f"const label = `${{a {rng.choice(TERNARY_OPS)} b ? '{yes}' : '{no}'}}: ${{a {rng.choice(ARITH_OPS)} b}}`;",
        "console.log(label);",
    ])
    return _output(code, "Строка целиком, как её выведет console.log", ("template_ternary",))


# --- sk.fe.object_keys_order_output -----------------------------------------------------------
KEY_WORDS = ("name", "id", "zip", "city", "age", "role", "tag", "mode", "lang", "page", "user", "kind")
OBJECTS = ("o", "obj", "data", "config", "row", "item")


@family(code="sk.fe.object_keys_order_output", specialization=SPEC, area="js", level=2, fmt="output",
        space_size=len(OBJECTS) * math.perm(len(KEY_WORDS), 3) * 1000**2 * math.comb(5, 2), median_time_s=50)
def object_keys_order_output(rng: random.Random) -> Generated:
    n = rng.randint(5, 7)
    n_int = rng.randint(2, n - 2)
    keys = [str(k) for k in rng.sample(range(1000), n_int)] + rng.sample(KEY_WORDS, n - n_int)
    rng.shuffle(keys)
    name = rng.choice(OBJECTS)
    body = ", ".join(f"{k}: {rng.randint(0, MAX_N)}" for k in keys)
    code = f"const {name} = {{ {body} }};\nconsole.log(Object.keys({name}).join(','));"
    return _output(code, "Ключи через запятую, как их выведет join(',')", ("object_keys_order",))


# --- sk.fe.rem_em_px --------------------------------------------------------------------------
ROOT_PX = (10, 12, 14, 16, 18, 20)
PARENT_EM = (0.75, 1.25, 1.5, 2)
VALUES = (0.5, 1, 1.5, 2, 2.5, 3)
PARENTS = ("card", "panel", "modal", "sidebar", "hero", "footer", "toolbar", "menu")
CHILDREN = ("title", "body", "icon", "link", "label", "row", "badge", "note")
SPACING = ("padding", "margin", "gap", "margin-top", "padding-left")


def _num(x: float) -> str:
    return f"{x:g}"


@family(code="sk.fe.rem_em_px", specialization=SPEC, area="markup", level=2, fmt="calc",
        space_size=len(ROOT_PX) * len(PARENT_EM) * len(VALUES) * 2 * len(PARENTS) * len(CHILDREN) * len(SPACING),
        median_time_s=60)
def rem_em_px(rng: random.Random) -> Generated:
    while True:
        root, parent, value = rng.choice(ROOT_PX), rng.choice(PARENT_EM), rng.choice(VALUES)
        unit = rng.choice(("em", "rem"))
        px = value * root * (1 if unit == "rem" else parent)  # em свойства — от font-size элемента (унаследован)
        if px.is_integer():
            break
    p, c, prop = rng.choice(PARENTS), rng.choice(CHILDREN), rng.choice(SPACING)
    css = "\n".join([f"html {{ font-size: {root}px; }}", f".{p} {{ font-size: {_num(parent)}em; }}",
                     f".{p} .{c} {{ {prop}: {_num(value)}{unit}; }}"])
    return Generated("number", Prompt(
        text=f"Чему равен {prop} у .{c} внутри .{p} в пикселях? Других правил font-size нет.", code=css,
        language="css", answer_hint="Число пикселей"), px, ("rem_em",))


# --- sk.fe.media_query_winner -----------------------------------------------------------------
COLORS = ("red", "blue", "green", "orange", "purple", "teal", "navy", "olive", "maroon", "gray", "black", "coral")
BLOCKS = ("banner", "header", "promo", "card", "nav", "hero", "footer", "notice")


@family(code="sk.fe.media_query_winner", specialization=SPEC, area="markup", level=2, fmt="calc",
        space_size=len(BLOCKS) * math.perm(len(COLORS), 4) * 129**3 * 8 * 1281, median_time_s=60)
def media_query_winner(rng: random.Random) -> Generated:
    block = rng.choice(BLOCKS)
    base, *colors = rng.sample(COLORS, 4)
    width = rng.randrange(320, 1601)
    lines = [f".{block} {{ color: {base}; }}"]
    color = base
    for c in colors:
        kind = rng.choice(("min", "max"))
        bp = rng.randrange(320, 1601, 10)
        lines.append(f"@media ({kind}-width: {bp}px) {{ .{block} {{ color: {c}; }} }}")
        if (kind == "min" and width >= bp) or (kind == "max" and width <= bp):
            color = c  # совпало несколько — побеждает последнее по порядку (одинаковая специфичность)
    return mcq(rng, f"Какой цвет текста будет у .{block}, если ширина окна {width}px?", color,
               [c for c in (base, *colors) if c != color], code="\n".join(lines), language="css")


# --- sk.fe.label_for_name ---------------------------------------------------------------------
FIELDS = (("email", "Почта", "email"), ("phone", "Телефон", "tel"), ("city", "Город", "text"),
          ("login", "Логин", "text"), ("password", "Пароль", "password"), ("name", "Имя", "text"),
          ("company", "Компания", "text"), ("zip", "Индекс", "text"), ("birth", "Дата рождения", "date"),
          ("site", "Сайт", "url"))
FORM_IDS = 98


@family(code="sk.fe.label_for_name", specialization=SPEC, area="markup", level=3, fmt="mcq",
        space_size=math.perm(len(FIELDS), 4) * FORM_IDS**4 * SHUFFLES, median_time_s=60)
def label_for_name(rng: random.Random) -> Generated:
    fields = rng.sample(FIELDS, 4)

    def markup(field, broken: str | None) -> str:
        f, title, typ = field
        n = rng.randint(1, FORM_IDS)
        fid = f"{f}-{n}"
        if broken == "mismatch":
            return f'<label for="{fid}">{title}</label> <input id="{f}-{n + 1}" type="{typ}">'
        if broken == "name":
            return f'<label for="{fid}">{title}</label> <input name="{fid}" type="{typ}">'
        if broken == "no_for":
            return f'<label>{title}</label> <input id="{fid}" type="{typ}">'
        return f'<label for="{fid}">{title}</label> <input id="{fid}" type="{typ}">'

    correct = markup(fields[0], None)
    distractors = [markup(fl, b) for fl, b in zip(fields[1:], ("mismatch", "name", "no_for"), strict=True)]
    return mcq(rng, "У какого поля есть подпись, которую прочитает скринридер (доступное имя через label)?",
               correct, distractors, radicals=("label_for", 4))


# --- sk.fe.nullish_vs_or_output ---------------------------------------------------------------
JS_LITERALS = ("0", "''", "null", "undefined", "42", "'ok'")
OBJ_LITERALS = ("null", "undefined", "{}", "{ x: 0 }", "{ x: null }", "{ x: 'ok' }", "{ x: '' }")


@family(code="sk.fe.nullish_vs_or_output", specialization=SPEC, area="js", level=3, fmt="output",
        space_size=len(JS_LITERALS) ** 2 * len(OBJ_LITERALS) * MAX_N**3, median_time_s=60)
def nullish_vs_or_output(rng: random.Random) -> Generated:
    d1, d2, d3 = (rng.randint(1, MAX_N) for _ in range(3))
    code = "\n".join([
        f"const a = {rng.choice(JS_LITERALS)};",
        f"const b = {rng.choice(JS_LITERALS)};",
        f"const o = {rng.choice(OBJ_LITERALS)};",
        f"console.log(`[${{a ?? {d1}}}] [${{b || {d2}}}] [${{o?.x ?? {d3}}}]`);",
    ])
    return _output(code, "Строка целиком: три значения в квадратных скобках", ("nullish_or",))


# --- sk.fe.destructuring_defaults_output ------------------------------------------------------
LETTERS = ("a", "b", "c", "p", "q", "x", "y", "z")
SOURCE_VALUES = ("null", "undefined", "0", "''", "42", "'ok'", None)  # None — ключа в объекте нет


@family(code="sk.fe.destructuring_defaults_output", specialization=SPEC, area="js", level=3, fmt="output",
        space_size=math.comb(len(LETTERS), 3) * len(SOURCE_VALUES) ** 3 * MAX_N**3, median_time_s=55)
def destructuring_defaults_output(rng: random.Random) -> Generated:
    names = sorted(rng.sample(LETTERS, 3))
    pattern = ", ".join(f"{n} = {rng.randint(1, MAX_N)}" for n in names)
    source = [(n, v) for n in names if (v := rng.choice(SOURCE_VALUES)) is not None]
    rng.shuffle(source)
    obj = "{ " + ", ".join(f"{n}: {v}" for n, v in source) + " }"
    code = f"const {{ {pattern} }} = {obj};\nconsole.log(`{' '.join(f'[${{{n}}}]' for n in names)}`);"
    return _output(code, "Строка целиком: три значения в квадратных скобках", ("destructuring_defaults",))


# --- sk.fe.fetch_404_flow ---------------------------------------------------------------------
STATUSES = (200, 201, 204, 400, 401, 403, 404, 409, 422, 429, 500, 502, 503)
RESOURCES = ("orders", "users", "cart", "products", "invoices", "reviews", "tickets", "files", "teams", "posts")


@family(code="sk.fe.fetch_404_flow", specialization=SPEC, area="js", level=4, fmt="mcq",
        space_size=len(STATUSES) * 2 * len(RESOURCES) * 9999 * SHUFFLES, median_time_s=70)
def fetch_404_flow(rng: random.Random) -> Generated:
    status = rng.choice(STATUSES)
    checked = rng.random() < 0.5
    lines = ["async function load() {", "  try {",
             f"    const res = await fetch('/api/{rng.choice(RESOURCES)}/{rng.randint(1, 9999)}');"]
    if checked:
        lines.append("    if (!res.ok) throw new Error(`HTTP ${res.status}`);")
    lines += ["    console.log(`OK: ${res.status}`);", "  } catch (e) {", "    console.log(`Ошибка: ${e.message}`);",
              "  }", "}", "load();"]
    # fetch отклоняется только при сетевой ошибке; 4xx и 5xx — обычный ответ с res.ok === false
    key = f"Ошибка: HTTP {status}" if checked and not 200 <= status <= 299 else f"OK: {status}"
    other_ok = f"OK: {200 if status != 200 else 204}"
    options = [f"OK: {status}", f"Ошибка: HTTP {status}", "Ошибка: Failed to fetch", other_ok]
    return mcq(rng, f"Сервер ответил статусом {status}, сеть работает. Что выведет load()?", key,
               [o for o in options if o != key], code="\n".join(lines), language="javascript",
               radicals=("fetch_status", 4))
