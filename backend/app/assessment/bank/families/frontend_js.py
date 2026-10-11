"""Семейства Frontend · JS/TS."""
import itertools
import math
import random

from app.assessment.bank.base import Generated, Prompt, family, mcq, template_fields
from app.assessment.bank.jsrun import run_js_snippet

JS_VARS = ("a", "b", "c", "x", "y", "value", "item", "data", "result", "input", "payload", "entry")
WORDS = ("id", "name", "token", "user", "cart", "item", "page", "tag", "key", "mode", "lang", "role")
MAX_N = 99


def _output(code: str, hint: str, radicals: tuple, text: str = "Что выведет код?") -> Generated:
    """«Что выведет код»: ключ — настоящий вывод QuickJS нашего шаблонного кода."""
    return Generated("text", Prompt(text=text, code=code, language="javascript", answer_hint=hint),
                     run_js_snippet(code), radicals)


# --- fe.js.typeof_output --------------------------------------------------------
# ловушки: typeof null, typeof NaN, массив и Date — «object»/«number» вопреки интуиции
TYPEOF_TRAPS = {
    "null": lambda rng: "null",
    "nan": lambda rng: "NaN",
    "array": lambda rng: rng.choice(("[]", f"[{rng.randint(1, MAX_N)}]",
                                     f"[{rng.randint(1, MAX_N)}, {rng.randint(1, MAX_N)}]")),
    "date": lambda rng: "new Date()",
}
TYPEOF_OTHERS = {
    "undefined": lambda rng: "undefined",
    "number": lambda rng: str(rng.randint(0, MAX_N)),
    "arrow": lambda rng: f"() => {rng.randint(0, MAX_N)}",
    "bigint": lambda rng: f"{rng.randint(1, MAX_N)}n",
    "string": lambda rng: f"'{rng.choice(WORDS)}'",
    "symbol": lambda rng: f"Symbol('{rng.choice(WORDS)}')",
    "boolean": lambda rng: rng.choice(("true", "false")),
    "object": lambda rng: f"{{ {rng.choice(WORDS)}: {rng.randint(0, MAX_N)} }}",
}
TYPEOF_CATS = {**TYPEOF_TRAPS, **TYPEOF_OTHERS}


@family(code="fe.js.typeof_output", specialization="frontend", area="js", level=1, fmt="output",
        # ловушка × две другие категории × место ловушки × имена × порядок в console.log
        space_size=len(TYPEOF_TRAPS) * math.perm(len(TYPEOF_CATS) - 1, 2) * 3 * math.perm(len(JS_VARS), 3) * 6,
        median_time_s=35)
def typeof_output(rng: random.Random) -> Generated:
    trap = rng.choice(sorted(TYPEOF_TRAPS))
    cats = [trap, *rng.sample(sorted(set(TYPEOF_CATS) - {trap}), 2)]
    rng.shuffle(cats)
    names = rng.sample(JS_VARS, 3)
    decls = [f"const {n} = {TYPEOF_CATS[c](rng)};" for n, c in zip(names, cats, strict=True)]
    shown = rng.sample(names, 3)
    code = "\n".join([*decls, f"console.log({', '.join(f'typeof {n}' for n in shown)});"])
    return _output(code, "Ровно то, что выведет console.log: три слова через пробел", ("typeof", 3))


# --- fe.js.const_array_mutation_output -----------------------------------------
ARRAY_VARS = ("xs", "items", "list", "ids", "scores", "queue", "prices", "values")


@family(code="fe.js.const_array_mutation_output", specialization="frontend", area="js", level=1,
        fmt="output", median_time_s=35,
        # имя × начальный массив (только 3 числа — нижняя оценка) × push/unshift и значение × значение присваивания
        space_size=len(ARRAY_VARS) * MAX_N**3 * 2 * MAX_N * MAX_N)
def const_array_mutation_output(rng: random.Random) -> Generated:
    name = rng.choice(ARRAY_VARS)
    xs = [rng.randint(1, MAX_N) for _ in range(rng.randint(3, 5))]
    add = rng.choice(("push", "unshift"))
    i = rng.randrange(len(xs) + 1)
    j = rng.choice(sorted({0, i, len(xs)}))  # что печатаем: начало, изменённый элемент или конец
    code = "\n".join([
        f"const {name} = [{', '.join(map(str, xs))}];",
        f"{name}.{add}({rng.randint(1, MAX_N)});",
        f"{name}[{i}] = {rng.randint(1, MAX_N)};",
        f"console.log({name}.length, {name}[{j}]);",
    ])
    return _output(code, "Ровно то, что выведет console.log: значения через пробел, например: 3 7",
                   ("const_mutation", 2))


# --- fe.js.equality_coercion_output ----------------------------------------------
# пары литералов; {n} — число 1..99, {m} — цифра 2..9 (true == '{m}' ложно: true → 1)
EQ_PAIRS = (
    ("'{n}'", "{n}"), ("null", "undefined"), ("0", "''"), ("NaN", "NaN"), ("[]", "false"),
    ("'0'", "false"), ("null", "0"), ("null", "false"), ("[{n}]", "{n}"), ("[]", "[]"),
    ("true", "1"), ("true", "'{m}'"), ("'{n}'", "'{n}'"), ("{n}", "{n}"), ("undefined", "0"),
    ("''", "false"),
)


def _eq_renderings(pair: tuple[str, str]) -> int:
    a, b = pair
    sides = 1 if a == b else 2
    return sides * (MAX_N if "{n}" in a + b else 8 if "{m}" in a + b else 1)


@family(code="fe.js.equality_coercion_output", specialization="frontend", area="js", level=2,
        fmt="output", median_time_s=55,
        space_size=sum(math.prod(_eq_renderings(p) for p in t) for t in itertools.permutations(EQ_PAIRS, 3)))
def equality_coercion_output(rng: random.Random) -> Generated:
    lines = []
    for a, b in rng.sample(EQ_PAIRS, 3):
        if rng.random() < 0.5:
            a, b = b, a
        n, m = rng.randint(1, MAX_N), rng.randint(2, 9)
        a, b = a.format(n=n, m=m), b.format(n=n, m=m)
        lines.append(f"console.log({a} == {b}, {a} === {b});")
    return _output("\n".join(lines),
                   "Ровно то, что выведет код: по строке на каждый console.log, значения через пробел",
                   ("loose_vs_strict", 3))


# --- fe.js.array_chain_output -----------------------------------------------------
LAMBDA_VARS = ("x", "n", "v", "item")
ACC_VARS = ("sum", "acc", "total", "s")
MAP_OPS = (("*", range(2, 6)), ("+", range(1, 10)), ("-", range(1, 10)))


def _chain_filter(rng: random.Random, xs: list[int]) -> tuple[str, list[int]] | None:
    """Условие фильтра, которое отбрасывает часть элементов, но оставляет хотя бы два."""
    kind = rng.choice(("mod", "gt", "lt"))
    if kind == "mod":
        m = rng.choice((2, 3))
        body, kept = f"% {m} === 0", [x for x in xs if x % m == 0]
    else:
        t = rng.randint(min(xs), max(xs))
        body = f"{'>' if kind == 'gt' else '<'} {t}"
        kept = [x for x in xs if (x > t if kind == "gt" else x < t)]
    return (body, kept) if 2 <= len(kept) < len(xs) else None


@family(code="fe.js.array_chain_output", specialization="frontend", area="js", level=2, fmt="output",
        median_time_s=55,
        # имя массива × порядок map/filter × имена параметров × операция map и число × 5 чисел массива
        # (нижняя оценка: условие фильтра, начальное значение reduce и длины 6–8 не считаем)
        space_size=len(ARRAY_VARS) * 2 * len(LAMBDA_VARS) * len(ACC_VARS)
        * sum(len(r) for _, r in MAP_OPS) * 30**5)
def array_chain_output(rng: random.Random) -> Generated:
    name, v, acc = rng.choice(ARRAY_VARS), rng.choice(LAMBDA_VARS), rng.choice(ACC_VARS)
    while True:
        xs = [rng.randint(1, 30) for _ in range(rng.randint(5, 8))]
        op, ks = rng.choice(MAP_OPS)
        k = rng.choice(ks)
        mapped_first = rng.random() < 0.5

        def apply_map(ys: list[int], op=op, k=k) -> list[int]:
            return [y * k if op == "*" else y + k if op == "+" else y - k for y in ys]

        picked = _chain_filter(rng, apply_map(xs) if mapped_first else xs)
        if picked:
            break
    body, _ = picked
    map_line = f"  .map(({v}) => {v} {op} {k})"
    filter_line = f"  .filter(({v}) => {v} {body})"
    init = rng.randint(0, 20)
    code = "\n".join([
        f"const {name} = [{', '.join(map(str, xs))}];",
        f"const result = {name}",
        *((map_line, filter_line) if mapped_first else (filter_line, map_line)),
        f"  .reduce(({acc}, {v}) => {acc} + {v}, {init});",
        "console.log(result);",
    ])
    return _output(code, "Ровно то, что выведет console.log: одно число", ("map_filter_reduce", 3))


# --- fe.js.string_number_ops_output ---------------------------------------------
# + со строкой склеивает, - и * приводят к числу; выражения считаются слева направо
STR_NUM_TEMPLATES = (
    "'{a}' + {b}", "'{a}' - {b}", "{a} + {b} + '{c}'", "'{c}' + {a} + {b}", "'{a}' * '{b}'",
    "{a} + '{b}' - {c}",
)
STR_NUM_MAX = 20


@family(code="fe.js.string_number_ops_output", specialization="frontend", area="js", level=2,
        fmt="output", median_time_s=55,
        space_size=sum(math.prod(STR_NUM_MAX ** len(template_fields(t)) for t in ts)
                       for ts in itertools.permutations(STR_NUM_TEMPLATES, 4)))
def string_number_ops_output(rng: random.Random) -> Generated:
    exprs = [t.format(a=rng.randint(1, STR_NUM_MAX), b=rng.randint(1, STR_NUM_MAX), c=rng.randint(1, STR_NUM_MAX))
             for t in rng.sample(STR_NUM_TEMPLATES, 4)]
    return _output(f"console.log({', '.join(exprs)});",
                   "Ровно то, что выведет console.log: четыре значения через пробел", ("plus_vs_minus", 4))


# --- fe.js.var_let_closure_output ------------------------------------------------
OUT_VARS = ("out", "log", "seen", "calls")
LOOP_VARS = (("i", "j"), ("k", "n"), ("a", "b"), ("x", "y"))
LOOP_STARTS = range(0, 6)
LOOP_COUNTS = range(2, 6)
TIMER_DELAYS = (0, 5, 10, 20)


@family(code="fe.js.var_let_closure_output", specialization="frontend", area="js", level=3,
        fmt="output", median_time_s=80,
        # массив × имена переменных × какой цикл первый × (начало, число итераций, задержка) обоих циклов
        space_size=len(OUT_VARS) * len(LOOP_VARS) * 2 * 2
        * (len(LOOP_STARTS) * len(LOOP_COUNTS) * len(TIMER_DELAYS)) ** 2)
def var_let_closure_output(rng: random.Random) -> Generated:
    out = rng.choice(OUT_VARS)
    names = list(rng.choice(LOOP_VARS))
    rng.shuffle(names)
    kinds = ["var", "let"]
    rng.shuffle(kinds)
    lines = [f"const {out} = [];"]
    for kind, var in zip(kinds, names, strict=True):
        start = rng.choice(LOOP_STARTS)
        stop = start + rng.choice(LOOP_COUNTS)
        lines += [f"for ({kind} {var} = {start}; {var} < {stop}; {var}++) {{",
                  f"  setTimeout(() => {out}.push({var}), {rng.choice(TIMER_DELAYS)});",
                  "}"]
    lines.append(f"setTimeout(() => console.log({out}.join(' ')), 100);")
    return _output("\n".join(lines), "Ровно то, что выведет console.log: числа через пробел",
                   ("var_vs_let_in_loop", 2))


# --- fe.js.default_sort_output ----------------------------------------------------
@family(code="fe.js.default_sort_output", specialization="frontend", area="js", level=3, fmt="output",
        median_time_s=60,
        # имя × пять различных чисел (нижняя оценка: только длина 5, только числа 1..120)
        space_size=len(ARRAY_VARS) * math.perm(120, 5) // 2)
def default_sort_output(rng: random.Random) -> Generated:
    name = rng.choice(ARRAY_VARS)
    while True:  # есть и однозначные, и двузначные, и строковый порядок отличается от числового
        xs = rng.sample(range(1, 121), rng.randint(5, 7))
        lens = {len(str(x)) for x in xs}
        if {1, 2} <= lens and sorted(map(str, xs)) != [str(x) for x in sorted(xs)]:
            break
    code = "\n".join([f"const {name} = [{', '.join(map(str, xs))}];", f"{name}.sort();",
                      f"console.log({name}.join(' '));"])
    return _output(code, "Ровно то, что выведет console.log: числа через пробел", ("default_sort",))


# --- fe.js.spread_shallow_copy_output ---------------------------------------------
# (объект, поле верхнего уровня, его значения, вложенный объект, его поле, значения)
SPREAD_ENTITIES = (
    ("order", "status", ("new", "paid", "shipped", "closed"), "customer", "city",
     ("Omsk", "Tula", "Kazan", "Perm", "Sochi", "Tver")),
    ("user", "role", ("admin", "editor", "viewer", "guest"), "address", "city",
     ("Omsk", "Tula", "Kazan", "Perm", "Sochi", "Tver")),
    ("ticket", "state", ("open", "closed", "pending", "resolved"), "assignee", "name",
     ("Anna", "Oleg", "Irina", "Pavel", "Maria", "Ivan")),
    ("product", "badge", ("sale", "new", "hit", "basic"), "warehouse", "zone",
     ("north", "south", "east", "west", "center")),
    ("profile", "theme", ("dark", "light", "contrast", "sepia"), "settings", "lang",
     ("ru", "en", "de", "fr", "es")),
)
COPY_VARS = ("copy", "clone", "draft", "next")
MAX_ID = 999


@family(code="fe.js.spread_shallow_copy_output", specialization="frontend", area="js", level=3,
        fmt="output", median_time_s=70,
        # сущность × id × (старое, новое) значение поля и вложенного поля × имя копии × вид изменения × порядок
        space_size=sum(len(tv) * (len(tv) - 1) * len(nv) * (len(nv) - 1)
                       for _, _, tv, _, _, nv in SPREAD_ENTITIES) * MAX_ID * len(COPY_VARS) * 2 * 2)
def spread_shallow_copy_output(rng: random.Random) -> Generated:
    obj, top, top_values, nested, field, nested_values = rng.choice(SPREAD_ENTITIES)
    copy = rng.choice(COPY_VARS)
    top_old, top_new = rng.sample(top_values, 2)
    nested_old, nested_new = rng.sample(nested_values, 2)
    # изменение поля вложенного объекта видно в оригинале (объект общий), замена объекта целиком — нет
    nested_stmt = (f"{copy}.{nested} = {{ {field}: '{nested_new}' }};" if rng.random() < 1 / 3
                   else f"{copy}.{nested}.{field} = '{nested_new}';")
    stmts = [f"{copy}.{top} = '{top_new}';", nested_stmt]
    rng.shuffle(stmts)
    code = "\n".join([
        f"const {obj} = {{ id: {rng.randint(1, MAX_ID)}, {top}: '{top_old}', {nested}: {{ {field}: '{nested_old}' }} }};",
        f"const {copy} = {{ ...{obj} }};",
        *stmts,
        f"console.log({obj}.{top}, {obj}.{nested}.{field});",
    ])
    return _output(code, "Ровно то, что выведет console.log: два значения через пробел", ("spread_copy", 2))


# --- fe.js.event_loop_order_output ------------------------------------------------
ASYNC_NAMES = ("load", "run", "task", "main", "init", "job")
LABELS = "ABCDEFGHJK"


@family(code="fe.js.event_loop_order_output", specialization="frontend", area="js", level=4,
        fmt="output", median_time_s=110,
        # нижняя оценка: имя функции × расстановка 7 меток × порядок 5 операторов
        space_size=len(ASYNC_NAMES) * math.perm(len(LABELS), 7) * math.factorial(5))
def event_loop_order_output(rng: random.Random) -> Generated:
    while True:
        t, p, c, s = rng.randint(1, 2), rng.randint(1, 2), rng.randint(0, 1), rng.randint(1, 2)
        if 5 <= 1 + t + p + c + s <= 7:
            break
    labels = iter(rng.sample(LABELS, 2 + t + p + 2 * c + s))
    fn = rng.choice(ASYNC_NAMES)
    head = [f"async function {fn}() {{", f"  console.log('{next(labels)}');", "  await null;",
            f"  console.log('{next(labels)}');", "}"]
    ops = [f"{fn}();"]
    ops += [f"setTimeout(() => console.log('{next(labels)}'), {rng.choice((0, 10))});" for _ in range(t)]
    ops += [f"Promise.resolve().then(() => console.log('{next(labels)}'));" for _ in range(p)]
    ops += [f"Promise.resolve().then(() => console.log('{next(labels)}'))"
            f".then(() => console.log('{next(labels)}'));" for _ in range(c)]
    ops += [f"console.log('{next(labels)}');" for _ in range(s)]
    rng.shuffle(ops)
    code = "\n".join([*head, *ops])
    return Generated(
        "text",
        Prompt(text="В каком порядке будут выведены буквы?", code=code, language="javascript",
               answer_hint="Буквы в порядке вывода через пробел, например: A C B"),
        " ".join(run_js_snippet(code).split("\n")), ("event_loop", "sync_micro_macro"),
    )


# --- fe.js.promise_all_vs_allsettled ----------------------------------------------
PA_TEMPLATES = (
    "Дашборд параллельно загружает независимые виджеты: {widgets}. Если запрос одного виджета упадёт, "
    "остальные всё равно нужно показать, а на месте упавшего — сообщение об ошибке. Как дождаться запросов?",
    "Страница «{page}» одновременно делает независимые запросы: {widgets}. Ошибка одного запроса не должна "
    "мешать показать данные остальных, для упавшего выводится заглушка. Какой способ дождаться запросов подходит?",
    "При старте приложение параллельно запрашивает независимые блоки: {widgets}. Нужно дождаться всех "
    "запросов и отрисовать каждый блок: успешный — с данными, неуспешный — с текстом ошибки. Как это сделать?",
)
PA_WIDGETS = ("курс валют", "погода", "новости", "задачи", "календарь", "уведомления", "продажи за день",
              "лента активности", "профиль", "рекомендации")
PA_PAGES = ("Главная", "Кабинет", "Отчёты", "Обзор", "Аналитика")
# стратегии: правильная — allSettled; дистракторы — типовые ошибки (all отклоняется при первой ошибке,
# race/any берут один результат, последовательный await в общем try/catch обрывается на первой ошибке)
PA_OPTIONS = {
    "allSettled": ("Через Promise.allSettled: дождаться всех и показать каждый блок по статусу",
                   "Через Promise.allSettled: получить статус каждого запроса и отрисовать все блоки",
                   "Через Promise.allSettled: успешные показать с данными, упавшие — с ошибкой"),
    "all": ("Через Promise.all: дождаться всех запросов и показать все результаты одним рендером",
            "Через Promise.all: получить массив результатов и отрисовать блоки по порядку",
            "Через Promise.all в одном try/catch: при ошибке показать сообщение"),
    "race": ("Через Promise.race: показать результат запроса, который завершится первым",
             "Через Promise.race: дождаться первого завершившегося запроса и отрисовать блоки"),
    "any": ("Через Promise.any: взять первый успешный ответ и отрисовать по нему все блоки",
            "Через Promise.any: дождаться первого успешного запроса, а ошибки пропустить"),
    "sequential": ("Через цикл for…of: await каждого запроса внутри одного общего try/catch",
                   "Последовательно: await каждого запроса в цикле, всё в одном try/catch"),
}


def _pa_space() -> int:
    widgets = sum(math.perm(len(PA_WIDGETS), k) for k in range(3, 7))
    texts = widgets * (2 + len(PA_PAGES))  # шаблоны без страницы и шаблон со страницей
    wrong = [len(PA_OPTIONS[s]) for s in PA_OPTIONS if s != "allSettled"]
    triples = sum(math.prod(t) for t in itertools.combinations(wrong, 3))
    return texts * len(PA_OPTIONS["allSettled"]) * triples * 24


@family(code="fe.js.promise_all_vs_allsettled", specialization="frontend", area="js", level=4, fmt="mcq",
        space_size=_pa_space(), median_time_s=90)
def promise_all_vs_allsettled(rng: random.Random) -> Generated:
    widgets = ", ".join(rng.sample(PA_WIDGETS, rng.randint(3, 6)))
    text = rng.choice(PA_TEMPLATES).format(widgets=widgets, page=rng.choice(PA_PAGES))
    wrong = rng.sample(sorted(s for s in PA_OPTIONS if s != "allSettled"), 3)
    return mcq(rng, text, rng.choice(PA_OPTIONS["allSettled"]), [rng.choice(PA_OPTIONS[s]) for s in wrong])


# --- fe.js.debounce_calls ---------------------------------------------------------
DEBOUNCE_CONTEXTS = (("поиска", "ввода в поле поиска"), ("сохранения черновика", "нажатия клавиши в редакторе"),
                     ("пересчёта раскладки", "изменения размера окна"), ("подгрузки подсказок", "ввода адреса"))
DEBOUNCE_WAITS = tuple(range(100, 501, 50))


@family(code="fe.js.debounce_calls", specialization="frontend", area="js", level=4, fmt="calc",
        # нижняя оценка: контекст × задержка × 8 событий, у каждого интервала ≥ 8 значений
        space_size=len(DEBOUNCE_CONTEXTS) * len(DEBOUNCE_WAITS) * 8**7, median_time_s=100)
def debounce_calls(rng: random.Random) -> Generated:
    what, event = rng.choice(DEBOUNCE_CONTEXTS)
    wait = rng.choice(DEBOUNCE_WAITS)
    n = rng.randint(8, 12)
    large = set(rng.sample(range(n - 1), rng.randint(1, min(5, n - 2))))
    times = [rng.randrange(0, 201, 10)]
    for i in range(n - 1):  # интервал ровно в wait не бывает: иначе неясно, что раньше — таймер или событие
        gap = rng.randrange(wait + 20, wait + 401, 10) if i in large else rng.randrange(20, wait - 19, 10)
        times.append(times[-1] + gap)
    text = (f"Функция {what} обёрнута в debounce с задержкой {wait} мс (trailing): каждое событие {event} "
            f"перезапускает таймер, а функция вызывается, когда после последнего события прошло {wait} мс "
            "без новых событий. В начале серии вызова нет. События приходят в моменты времени из массива "
            "(мс от начала). Сколько раз будет вызвана функция?")
    calls = 1 + len(large)  # срабатывание после каждого «длинного» интервала и после последнего события
    return Generated("number", Prompt(text=text, code=f"const eventTimes = [{', '.join(map(str, times))}];",
                                      language="javascript", answer_hint="Целое число"),
                     calls, ("debounce_trailing",))


# --- fe.js.microtask_starvation -----------------------------------------------------
STARVE_CODES = {
    "then": ("function {fn}() {{", "  {c}++;", "  Promise.resolve().then({fn});", "}}"),
    "queueMicrotask": ("function {fn}() {{", "  {c}++;", "  queueMicrotask({fn});", "}}"),
    "await": ("async function {fn}() {{", "  while (true) {{", "    {c}++;", "    await null;", "  }}", "}}"),
}
STARVE_FNS = ("poll", "tick", "loop", "spin", "pump", "step")
STARVE_COUNTERS = ("n", "count", "ticks", "steps")
STARVE_MESSAGES = ("timer", "tick", "done", "render", "update", "ping")
STARVE_DELAYS = (10, 50, 100, 250)
STARVE_CORRECT = (
    "Колбэк таймера и отрисовка не выполнятся: очередь микрозадач никогда не опустеет",
    "Ни таймер, ни отрисовка не выполнятся: цикл событий не выйдет из микрозадач",
    "Таймер не сработает и кадр не отрисуется: микрозадачи будут добавляться бесконечно",
)
STARVE_WRONG = (
    "Колбэк таймера выполнится примерно через {d} мс: таймеры идут параллельно с микрозадачами",
    "Браузер чередует очереди: между микрозадачами выполнит таймер и отрисует кадр",
    "Возникнет RangeError из-за переполнения стека, после этого выполнится таймер",
    "Страница останется отзывчивой: then и await уступают управление браузеру",
)


@family(code="fe.js.microtask_starvation", specialization="frontend", area="js", level=5, fmt="mcq",
        space_size=len(STARVE_CODES) * len(STARVE_FNS) * len(STARVE_COUNTERS) * len(STARVE_MESSAGES)
        * len(STARVE_DELAYS) * len(STARVE_CORRECT) * math.comb(len(STARVE_WRONG), 3) * 24,
        median_time_s=120)
def microtask_starvation(rng: random.Random) -> Generated:
    fn, c, d = rng.choice(STARVE_FNS), rng.choice(STARVE_COUNTERS), rng.choice(STARVE_DELAYS)
    body = STARVE_CODES[rng.choice(sorted(STARVE_CODES))]
    code = "\n".join([f"let {c} = 0;", f"setTimeout(() => console.log('{rng.choice(STARVE_MESSAGES)}'), {d});",
                      *(ln.format(fn=fn, c=c) for ln in body), f"{fn}();"])
    return mcq(rng, "Этот код запущен на странице в браузере. Что произойдёт с колбэком setTimeout и отрисовкой "
               "страницы?", rng.choice(STARVE_CORRECT), [w.format(d=d) for w in rng.sample(STARVE_WRONG, 3)],
               code=code, language="javascript")


# --- fe.js.ts_narrowing -------------------------------------------------------------
# порядок членов объединения — как TypeScript печатает тип: примитивы, объекты, затем null и undefined
TS_PRIMS = ("string", "number", "bigint", "boolean", "Date", "string[]", "null", "undefined")
TS_OBJECT_LIKE = frozenset({"Date", "string[]", "null"})  # typeof x === "object" истинно и для null
TS_TYPEOF_GUARDS = (  # (условие с ранним return, какие члены убирает; вес выбора)
    ('typeof {v} === "string"', frozenset({"string"}), 1), ('typeof {v} === "number"', frozenset({"number"}), 1),
    ('typeof {v} === "boolean"', frozenset({"boolean"}), 1), ('typeof {v} === "bigint"', frozenset({"bigint"}), 1),
    ("{v} === undefined", frozenset({"undefined"}), 1), ("{v} === null", frozenset({"null"}), 1),
    ('typeof {v} === "object"', TS_OBJECT_LIKE, 3), ("{v} instanceof Date", frozenset({"Date"}), 1),
    ("Array.isArray({v})", frozenset({"string[]"}), 1),
)
TS_KIND_SETS = (
    ("Shape", (("Circle", "circle", "r: number"), ("Square", "square", "side: number"),
               ("Rect", "rect", "w: number; h: number"), ("Triangle", "triangle", "a: number; h: number"))),
    ("Payment", (("Card", "card", "pan: string"), ("Cash", "cash", "amount: number"),
                 ("Crypto", "crypto", "wallet: string"), ("Invoice", "invoice", "due: string"))),
    ("State", (("Idle", "idle", "since: number"), ("Loading", "loading", "progress: number"),
               ("Success", "success", "data: string"), ("Failure", "failure", "error: string"))),
)
TS_IN_SETS = (
    ("Pet", (("Fish", "swim"), ("Bird", "fly"), ("Dog", "bark"), ("Cat", "meow"))),
    ("Device", (("Printer", "print"), ("Scanner", "scan"), ("Camera", "shoot"), ("Speaker", "play"))),
    ("Job", (("Mailer", "send"), ("Parser", "parse"), ("Exporter", "export"), ("Cleaner", "clean"))),
)
TS_VARS = ("value", "input", "x", "data", "raw", "arg")
TS_FNS = ("format", "handle", "render", "process", "show", "check")


def _ts_typeof(rng: random.Random, v: str) -> tuple[list[str], list[str], list[str], list[str]]:
    while True:
        picked = set(rng.sample(TS_PRIMS, rng.randint(4, 5)))
        members = [t for t in TS_PRIMS if t in picked]
        remaining, guards = list(members), []
        for _ in range(2):
            options = [(g, rm, w) for g, rm, w in TS_TYPEOF_GUARDS if rm & set(remaining) and g not in guards]
            g, rm, _ = rng.choices(options, weights=[w for *_, w in options])[0]
            guards.append(g)
            remaining = [t for t in remaining if t not in rm]
        if remaining:
            return members, [g.format(v=v) for g in guards], [f"{v}: {' | '.join(members)}"], remaining


def _ts_kind(rng: random.Random, v: str) -> tuple[list[str], list[str], list[str], list[str]]:
    alias, pool = rng.choice(TS_KIND_SETS)
    picked = set(rng.sample(pool, rng.randint(3, 4)))
    chosen = [m for m in pool if m in picked]
    members = [name for name, _, _ in chosen]
    decls = [f'type {name} = {{ kind: "{kind}"; {fields} }};' for name, kind, fields in chosen]
    decls.append(f"type {alias} = {' | '.join(members)};")
    if rng.random() < 0.3:  # «!==» с ранним return оставляет ровно один вариант
        kept = rng.choice(chosen)
        guards, remaining = [f'{v}.kind !== "{kept[1]}"'], [kept[0]]
    else:
        hit = rng.sample(chosen, rng.randint(1, len(chosen) - 1))
        guards = [f'{v}.kind === "{kind}"' for _, kind, _ in hit]
        remaining = [m for m in members if m not in {name for name, _, _ in hit}]
    return members, guards, [*decls, f"{v}: {alias}"], remaining


def _ts_in(rng: random.Random, v: str) -> tuple[list[str], list[str], list[str], list[str]]:
    alias, pool = rng.choice(TS_IN_SETS)
    picked = set(rng.sample(pool, rng.randint(3, 4)))
    chosen = [m for m in pool if m in picked]
    members = [name for name, _ in chosen]
    decls = [f"type {name} = {{ {method}(): void }};" for name, method in chosen]
    decls.append(f"type {alias} = {' | '.join(members)};")
    hit = rng.sample(chosen, rng.randint(1, len(chosen) - 1))
    guards = [f'"{method}" in {v}' for _, method in hit]
    remaining = [m for m in members if m not in {name for name, _ in hit}]
    return members, guards, [*decls, f"{v}: {alias}"], remaining


def _ts_distractors(rng: random.Random, members: list[str], remaining: list[str]) -> list[str]:
    removed = [t for t in members if t not in remaining]
    show = " | ".join
    back = rng.choice(removed)  # «забыли» одно условие: один убранный член возвращается
    cands = {show(members), show(removed), "never", show([t for t in members if t in remaining or t == back])}
    if len(remaining) >= 2:
        drop = rng.choice(remaining)
        cands.add(show([t for t in remaining if t != drop]))
    cands.discard(show(remaining))
    return sorted(cands)


@family(code="fe.js.ts_narrowing", specialization="frontend", area="js", level=5, fmt="mcq",
        # нижняя оценка: вид сужения × имена переменной и функции × выбор членов объединения × порядок вариантов
        space_size=3 * len(TS_VARS) * len(TS_FNS) * math.comb(len(TS_PRIMS), 4) * 24, median_time_s=130)
def ts_narrowing(rng: random.Random) -> Generated:
    v, fn = rng.choice(TS_VARS), rng.choice(TS_FNS)
    members, guards, head, remaining = rng.choice((_ts_typeof, _ts_kind, _ts_in))(rng, v)
    decls, param = head[:-1], head[-1]
    cands = _ts_distractors(rng, members, remaining)
    correct = " | ".join(remaining)
    while True:  # три дистрактора не начинаются одним словом, отличным от первого слова ключа
        wrong = rng.sample(cands, 3)
        firsts = {w.split()[0] for w in wrong}
        if len(firsts) > 1 or correct.split()[0] in firsts:
            break
    code = "\n".join([*decls, *([""] if decls else []), f"function {fn}({param}): void {{",
                      *(f"  if ({g}) return;" for g in guards),
                      f"  console.log({v}); // ← какой тип у {v} в этой строке?", "}"])
    return mcq(rng, "Какой тип будет у переменной в отмеченной строке с точки зрения TypeScript?", correct, wrong,
               code=code, language="typescript")
