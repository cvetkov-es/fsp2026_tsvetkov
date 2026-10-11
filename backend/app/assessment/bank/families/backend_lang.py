import random

from app.assessment.bank.base import SHUFFLES, Generated, Prompt, family, mcq
from app.assessment.bank.pysnippet import run_python_snippet

VARS = ("items", "nums", "data", "values", "queue", "stack", "buf", "acc")
COPY_KINDS = ("{a}[:]", "{a}.copy()", "list({a})", "{a}")  # последнее — псевдоним, не копия


@family(code="be.lang.list_alias_copy", specialization="backend", area="lang", level=2,
        fmt="output", space_size=8 * 7 * 6 * 4 * 3 * 90**5, median_time_s=45)
def list_alias_copy(rng: random.Random) -> Generated:
    a, b, c = rng.sample(VARS, 3)
    n = rng.randint(3, 5)
    xs = [rng.randint(1, 90) for _ in range(n + 2)]
    init = ", ".join(str(x) for x in xs[:n])
    copy_expr = rng.choice(COPY_KINDS).format(a=a)
    code = (f"{a} = [{init}]\n"
            f"{b} = {a}\n"
            f"{b}.append({xs[n]})\n"
            f"{c} = {copy_expr}\n"
            f"{c}.append({xs[n + 1]})\n"
            f"print(len({a}), len({c}), {a}[-1])")
    return Generated(
        "text",
        Prompt(text="Что выведет программа?", code=code, language="python",
               answer_hint="Ровно то, что напечатает print, например: 1 2 3"),
        run_python_snippet(code), ("alias_vs_copy", code.count("\n") + 1),
    )


# ---------------------------------------------------------------------------
# План 03b: наполнение области lang
# ---------------------------------------------------------------------------
INT_NAMES = ("a", "b", "x", "y", "n", "m", "total", "step", "count", "size", "width", "base")


@family(code="be.lang.int_division_output", specialization="backend", area="lang", level=1,
        fmt="output", space_size=12 * 11 * 9990 * 96, median_time_s=35)
def int_division_output(rng: random.Random) -> Generated:
    a, b = rng.sample(INT_NAMES, 2)
    code = f"{a} = {rng.randint(10, 9999)}\n{b} = {rng.randint(2, 97)}\nprint({a} // {b}, {a} % {b})"
    return Generated(
        "text",
        Prompt(text="Что выведет программа?", code=code, language="python",
               answer_hint="Ровно то, что напечатает print: два числа через пробел"),
        run_python_snippet(code), ("int_division",),
    )


DICT_NAMES = ("config", "settings", "limits", "prices", "stock", "scores")
DICT_KEYS = ("timeout", "retries", "port", "workers", "limit", "pool", "ttl", "batch",
             "depth", "quota", "burst", "window", "delay", "level", "shards", "backlog")


def _dict_get_space() -> int:
    from math import perm
    return len(DICT_NAMES) * 900 * sum(perm(len(DICT_KEYS), n + 1) * 99**n for n in (3, 4, 5)) * SHUFFLES


@family(code="be.lang.dict_get_default", specialization="backend", area="lang", level=1,
        fmt="mcq", space_size=_dict_get_space(), median_time_s=40)
def dict_get_default(rng: random.Random) -> Generated:
    name = rng.choice(DICT_NAMES)
    n = rng.randint(3, 5)
    keys = rng.sample(DICT_KEYS, n + 1)
    present, missing = keys[:n], keys[n]
    values = [rng.randint(1, 99) for _ in present]
    default = rng.randint(100, 999)  # заведомо не совпадает со значениями словаря
    body = ", ".join(f'"{k}": {v}' for k, v in zip(present, values, strict=True))
    code = f'{name} = {{{body}}}\nprint({name}.get("{missing}", {default}))'
    return mcq(rng, "Что выведет программа?", str(default),
               ("None", "KeyError (программа завершится с исключением)", str(values[0])),
               code=code, language="python")


SLICE_VARS = ("word", "text", "name", "token", "label", "tag", "code", "title")
SYLLABLES = tuple(c + v for c in "bdfgklmnprstvz" for v in "aeiou")


@family(code="be.lang.string_slicing_output", specialization="backend", area="lang", level=2,
        fmt="output", space_size=len(SYLLABLES) ** 3 * len(SLICE_VARS) * 6 * 3, median_time_s=50)
def string_slicing_output(rng: random.Random) -> Generated:
    var = rng.choice(SLICE_VARS)
    word = "".join(rng.choice(SYLLABLES) for _ in range(rng.randint(3, 6)))  # длина 6..12
    a = rng.randint(0, len(word) - 3)
    b = rng.randint(a + 2, len(word))
    slices = [f"{var}[{a}:{b}]", f"{var}[-{rng.randint(2, 4)}:]", f"{var}[::-1]"]
    rng.shuffle(slices)
    code = f'{var} = "{word}"\nprint({", ".join(slices)})'
    return Generated(
        "text",
        Prompt(text="Что выведет программа?", code=code, language="python",
               answer_hint="Ровно то, что напечатает print: три строки через пробел"),
        run_python_snippet(code), ("slicing", 3),
    )


SET_PAIRS = (("a", "b"), ("xs", "ys"), ("left", "right"), ("first", "second"), ("p", "q"),
             ("old", "new"), ("u", "v"))
SET_NAMES = (("sa", "sb"), ("s1", "s2"), ("ua", "ub"), ("setx", "sety"))
SET_OPS = ("|", "&", "-")


@family(code="be.lang.set_ops_len", specialization="backend", area="lang", level=2,
        fmt="output", space_size=len(SET_PAIRS) * len(SET_NAMES) * len(SET_OPS) * 30**16,
        median_time_s=55)
def set_ops_len(rng: random.Random) -> Generated:
    xs, ys = rng.choice(SET_PAIRS)
    sx, sy = rng.choice(SET_NAMES)
    op = rng.choice(SET_OPS)
    first = [rng.randint(1, 30) for _ in range(rng.randint(8, 12))]
    second = [rng.randint(1, 30) for _ in range(rng.randint(8, 12))]
    code = (f"{xs} = {first}\n{ys} = {second}\n{sx} = set({xs})\n{sy} = set({ys})\n"
            f"print(len({sx} {op} {sy}))")
    return Generated(
        "number",
        Prompt(text="Какое число выведет программа?", code=code, language="python",
               answer_hint="Целое число"),
        int(run_python_snippet(code)), ("set_ops", 2),
    )


LIST_HINT = "Ровно то, что напечатает print, например: [1, 2, 3]"
MD_FUNCS = ("add_item", "collect", "push_value", "remember", "track", "register")
MD_ACC = ("acc", "bucket", "seen", "result")


@family(code="be.lang.mutable_default_output", specialization="backend", area="lang", level=3,
        fmt="output", space_size=len(MD_FUNCS) * len(MD_ACC) * 2 * 99**3 * 3, median_time_s=75)
def mutable_default_output(rng: random.Random) -> Generated:
    fn, acc = rng.choice(MD_FUNCS), rng.choice(MD_ACC)
    n_calls = rng.randint(2, 3)  # вызовов до итогового print
    explicit = rng.randrange(n_calls)
    calls = [f"{fn}({rng.randint(1, 99)}, [])" if i == explicit else f"{fn}({rng.randint(1, 99)})"
             for i in range(n_calls)]
    last = f"{fn}({rng.randint(1, 99)})"
    final = f"print({last})"
    code = "\n".join([f"def {fn}(x, {acc}=[]):", f"    {acc}.append(x)", f"    return {acc}",
                      *calls, final])
    return Generated(
        "text",
        Prompt(text="Что выведет программа?", code=code, language="python",
               answer_hint=LIST_HINT),
        run_python_snippet(code), ("mutable_default",),
    )


@family(code="be.lang.negative_floor_div_output", specialization="backend", area="lang", level=3,
        fmt="output", space_size=12 * 11 * 993 * 18, median_time_s=70)
def negative_floor_div_output(rng: random.Random) -> Generated:
    a, b = rng.sample(INT_NAMES, 2)
    while True:
        x, y = rng.randint(7, 999), rng.randint(2, 19)
        if x % y:
            break
    code = f"{a} = {x}\n{b} = {y}\nprint(-{a} // {b}, -{a} % {b}, int(-{a} / {b}))"
    return Generated(
        "text",
        Prompt(text="Что выведет программа?", code=code, language="python",
               answer_hint="Ровно то, что напечатает print: три числа через пробел"),
        run_python_snippet(code), ("negative_floor_div",),
    )


CL_LISTS = ("handlers", "callbacks", "funcs", "getters", "tasks", "hooks", "actions", "fs",
            "makers", "steps", "ops", "jobs", "calls", "fns", "readers", "checks")
CL_LOOP = ("i", "n", "idx", "j", "step", "pos", "num", "t")
CL_CALL = ("f", "fn", "h", "cb", "g", "job", "t0", "op")


@family(code="be.lang.closure_late_binding_output", specialization="backend", area="lang", level=3,
        fmt="output", space_size=len(CL_LISTS) * len(CL_LOOP) * len(CL_CALL) * 4 * 8 * 2,
        median_time_s=80)
def closure_late_binding_output(rng: random.Random) -> Generated:
    fs, i = rng.choice(CL_LISTS), rng.choice(CL_LOOP)
    f = rng.choice([c for c in CL_CALL if c != i])
    n, k = rng.randint(3, 6), rng.randint(2, 9)
    mul = f"{i} * {k}" if rng.random() < 0.5 else f"{k} * {i}"
    code = f"{fs} = [lambda: {mul} for {i} in range({n})]\nprint([{f}() for {f} in {fs}])"
    return Generated(
        "text",
        Prompt(text="Что выведет программа?", code=code, language="python",
               answer_hint=LIST_HINT),
        run_python_snippet(code), ("late_binding",),
    )


GEN_NAMES = ("g", "gen", "stream", "pipe", "squares", "feed", "values", "chunk", "source", "it")
GEN_VARS = ("x", "n", "v", "item", "k", "e")
GEN_FIRST = ("sum", "max", "min")
GEN_EXPRS = ("{x} * {k}", "{x} + {k}", "{x} * {x} + {k}")


@family(code="be.lang.generator_exhaustion_output", specialization="backend", area="lang", level=4,
        fmt="output", space_size=len(GEN_NAMES) * len(GEN_VARS) * len(GEN_FIRST) * len(GEN_EXPRS) * 7 * 8 * 2,
        median_time_s=95)
def generator_exhaustion_output(rng: random.Random) -> Generated:
    g, x = rng.choice(GEN_NAMES), rng.choice(GEN_VARS)
    expr = rng.choice(GEN_EXPRS).format(x=x, k=rng.randint(2, 9))
    n = rng.randint(3, 9)
    tail = f"list({g})" if rng.random() < 0.5 else f"len(list({g}))"
    code = (f"{g} = ({expr} for {x} in range(1, {n + 1}))\n"
            f"print({rng.choice(GEN_FIRST)}({g}), sum({g}), {tail})")
    return Generated(
        "text",
        Prompt(text="Что выведет программа?", code=code, language="python",
               answer_hint="Ровно то, что напечатает print: три значения через пробел; "
                           "список — как его печатает Python, например [1, 2]"),
        run_python_snippet(code), ("generator_exhaustion",),
    )


ASYNC_ENTS = ("order", "invoice", "booking", "payment", "ticket", "cart", "refund", "claim",
              "subscription", "shipment")
ASYNC_HOSTS = ("pay.example.com", "billing.internal", "gate.example.org", "bank.example.net",
               "psp.internal", "cards.example.com")
ASYNC_ACTS = ("charge", "confirm", "capture", "approve", "settle", "authorize")
ASYNC_FILES = ("rates", "tariffs", "limits", "blacklist", "catalog", "regions")
ASYNC_SLEEPS = ("0.5", "1", "2", "3")
# 3 вида блокирующей строки: sleep, requests.get, чтение файла
ASYNC_BLOCKING_VARIANTS = len(ASYNC_SLEEPS) + len(ASYNC_HOSTS) + len(ASYNC_FILES)


@family(code="be.lang.async_blocking_bug", specialization="backend", area="lang", level=4,
        fmt="bug",
        space_size=len(ASYNC_ENTS) * len(ASYNC_HOSTS) * 90 * ASYNC_BLOCKING_VARIANTS * sum(
            (len(ASYNC_ACTS) if audit else 1) * (29 if retries else 1) * (9 + audit + retries)
            for audit in (0, 1) for retries in (0, 1)),
        median_time_s=110)
def async_blocking_bug(rng: random.Random) -> Generated:
    ent = rng.choice(ASYNC_ENTS)
    host = rng.choice(ASYNC_HOSTS)
    blocks = [
        [f"    {ent} = await db.fetch_{ent}(request.{ent}_id)"],
        [f"    limit = {rng.randint(10, 99)}"],
        ['    rates = await cache.get("rates")'],
        [f"    total = {ent}.price * request.count"],
        ['    payload = {"total": total, "rate": rates}'],
        ["    if total > limit:", '        return {"status": "rejected"}'],
        [f'    url = "https://{host}/v1/charge"'],
        ["    reply = await client.post(url, json=payload)"],
    ]
    if rng.random() < 0.5:
        blocks.append([f'    await audit.write(request.user_id, "{rng.choice(ASYNC_ACTS)}")'])
    if rng.random() < 0.5:
        blocks.append([f"    retries = {rng.randint(2, 30)}"])
    kind = rng.choice(("sleep", "get", "read"))
    if kind == "sleep":
        bad = f"    time.sleep({rng.choice(ASYNC_SLEEPS)})"
    elif kind == "get":
        bad = f'    fresh = requests.get("https://{rng.choice(ASYNC_HOSTS)}/rates")'
    else:
        bad = f'    local = open("/var/data/{rng.choice(ASYNC_FILES)}.csv").read()'
    slot = rng.randint(0, len(blocks))  # вставка между блоками, не внутри if
    lines = [f"async def handle_{ent}(request):"]
    for i, b in enumerate(blocks):
        if i == slot:
            lines.append(bad)
        lines.extend(b)
    if slot == len(blocks):
        lines.append(bad)
    lines.append(f'    return {{"status": "ok", "id": {ent}.id}}')
    line_no = lines.index(bad) + 1
    code = "\n".join(lines)
    numbered = "\n".join(f"{n:>2}| {ln}" for n, ln in enumerate(lines, start=1))
    return Generated(
        "line",
        Prompt(text="Эта асинхронная функция-обработчик под нагрузкой мешает остальным запросам: "
                    "пока она выполняется, сервер не отвечает другим клиентам. "
                    "В какой строке причина?",
               code=code, language="python", answer_hint=f"Номер строки:\n{numbered}"),
        line_no, ("async_blocking",),
    )


CPU_SERVICES = ("Отчёты", "Скоринг", "Каталог", "Аналитика", "Биллинг", "Рендер", "Поиск",
                "Импорт", "Прогноз", "Архив")
CPU_TASKS = (
    "подсчёт скоринга для миллиона независимых клиентов циклом",
    "построение превью для тысяч независимых изображений попиксельной обработкой",
    "симуляция Монте-Карло: миллионы независимых испытаний",
    "расчёт рейтинга для каждого из сотен тысяч товаров собственной формулой",
    "разбор тысяч независимых файлов бинарного формата собственным парсером",
    "проверка на простоту каждого числа из большого списка перебором",
    "расчёт расстояния редактирования для каждой из миллиона пар строк",
    "оценка тысяч независимых финансовых сценариев собственной моделью",
    "рендер тысяч независимых тайлов карты",
    "нормализация каждой из тысяч независимых таблиц собственным алгоритмом",
    "расчёт контрольных сумм собственной реализацией CRC для тысяч независимых блоков",
    "подбор параметров для каждого из тысяч независимых заказов перебором",
)
# таблица сценариев: (правильный ответ, три дистрактора из типовых ошибок);
# длина правильного варианта в каждой строке — между длинами дистракторов
CPU_ROWS = (
    ("Раздать работу процессам через multiprocessing или ProcessPoolExecutor",
     ("Запустить больше потоков через ThreadPoolExecutor по числу ядер процессора",
      "Переписать код на asyncio и запустить много параллельных корутин",
      "Повысить приоритет потоков, чтобы GIL доставался им как можно чаще")),
    ("Вынести вычисления в пул процессов: у каждого процесса свой интерпретатор и GIL",
     ("Увеличить пул потоков до числа ядер: GIL не мешает потокам работать параллельно",
      "Заменить потоки на корутины asyncio: они выполняются параллельно на разных ядрах",
      "Повысить приоритет ОС для потока, в котором идёт расчёт, и дать ему больше ядер")),
    ("Взять ProcessPoolExecutor с числом воркеров по числу ядер и раздать им части задачи",
     ("Взять ThreadPoolExecutor с числом воркеров по числу ядер CPU и раздать им части задачи",
      "Запустить все части задачи одновременно через asyncio.gather на одном потоке",
      "Запустить threading.Thread с максимальным приоритетом для каждой части задачи")),
)
CPU_MAX_CORES = 64


@family(code="be.lang.cpu_bound_parallelism", specialization="backend", area="lang", level=4,
        fmt="mcq",
        space_size=len(CPU_ROWS) * len(CPU_TASKS) * len(CPU_SERVICES) * (CPU_MAX_CORES - 1) * SHUFFLES,
        median_time_s=100)
def cpu_bound_parallelism(rng: random.Random) -> Generated:
    correct, distractors = rng.choice(CPU_ROWS)
    n = rng.randint(2, CPU_MAX_CORES)
    text = (f"Сервис «{rng.choice(CPU_SERVICES)}» работает под CPython. Число ядер CPU на машине: {n}. "
            f"Его узкое место — {rng.choice(CPU_TASKS)}. Это чисто вычислительная работа на Python "
            "без ввода-вывода, которая загружает одно ядро на 100%. "
            "Как лучше всего ускорить её, задействовав все ядра?")
    return mcq(rng, text, correct, distractors)


LOCK_PAIRS = (("счёт", "журнал"), ("кэш", "индекс"), ("очередь", "реестр"), ("склад", "резерв"),
              ("сессии", "права"), ("заказы", "остатки"), ("профиль", "баланс"),
              ("каталог", "цены"), ("файл", "метаданные"), ("корзина", "купоны"))
LOCK_CTX = ("учёта заказов", "платёжного шлюза", "рассылки уведомлений", "складского учёта",
            "обработки заявок", "аналитики событий", "личного кабинета", "импорта каталога")
# таблица сценариев: (правильный ответ, три дистрактора из типовых ошибок)
LOCK_ROWS = (
    ("Взаимоблокировка: потоки ждут друг друга по кругу; брать блокировки в едином порядке",
     ("Гонка данных: потоки одновременно меняют ресурс; заменить Lock на RLock в обоих потоках",
      "Голодание потока: один поток не получает блокировку; увеличить таймаут ожидания",
      "Утечка потоков: зависшие потоки не завершаются; сделать потоки daemon-потоками")),
    ("Дедлок: каждый поток держит одну блокировку и ждёт вторую; единый порядок захвата",
     ("Гонка данных: два потока пишут в ресурс одновременно; заменить Lock на RLock в обоих",
      "Голодание: поток слишком долго ждёт своей очереди; увеличить таймаут в acquire",
      "Утечка потоков: зависшие потоки накапливаются; пометить все потоки как daemon")),
)


@family(code="be.lang.lock_order_deadlock", specialization="backend", area="lang", level=5,
        fmt="mcq",
        space_size=len(LOCK_PAIRS) * 2 * len(LOCK_CTX) * 99 * len(LOCK_ROWS) * SHUFFLES,
        median_time_s=135)
def lock_order_deadlock(rng: random.Random) -> Generated:
    a, b = rng.choice(LOCK_PAIRS)
    if rng.random() < 0.5:
        a, b = b, a
    correct, distractors = rng.choice(LOCK_ROWS)
    text = (f"В многопоточном сервисе {rng.choice(LOCK_CTX)} два потока работают с общими ресурсами "
            f"«{a}» и «{b}», у каждого ресурса свой threading.Lock. Поток 1 захватывает сначала "
            f"блокировку «{a}», затем «{b}». Поток 2 захватывает сначала «{b}», затем «{a}». "
            f"Сервис намертво зависает примерно раз на {rng.randint(1, 99) * 1000} запросов, "
            "при этом загрузка CPU падает до нуля. Что происходит и как это исправить?")
    return mcq(rng, text, correct, distractors)


HASH_CLASSES = ("Invoice", "Account", "Ticket", "Coupon", "Booking", "Product")
HASH_FIELDS = ("number", "code", "key", "ident", "serial", "label_id")
HASH_VARS = (("obj", "seen"), ("item", "known"), ("entity", "registry"), ("row", "cache"))
# таблица сценариев: (правильный ответ, три дистрактора из типовых ошибок)
HASH_ROWS = (
    ("Объект лежит в корзине по старому хэшу, а поиск идёт по новому, и запись не находится",
     ("set хранит копию объекта, поэтому изменение исходного объекта на множество не влияет",
      "Для множества метод __eq__ не вызывается, поэтому сравнение по полю не работает",
      "Python кэширует результат оператора in и не пересчитывает его после изменения объекта")),
    ("Хэш изменился после добавления, поэтому поиск смотрит не в ту корзину, где лежит объект",
     ("При изменении поля множество само удаляет объект из своих элементов и ничего не находит",
      "Оператор in сравнивает объекты по id, а не по __eq__ и __hash__, поэтому ищет не то",
      "set пересобирается при каждом обращении и поэтому теряет изменённые объекты множества")),
)


@family(code="be.lang.mutable_hash_key", specialization="backend", area="lang", level=5,
        fmt="mcq",
        space_size=len(HASH_CLASSES) * len(HASH_FIELDS) * len(HASH_VARS) * 9999 * 9998
        * len(HASH_ROWS) * SHUFFLES,
        median_time_s=145)
def mutable_hash_key(rng: random.Random) -> Generated:
    cls, fld = rng.choice(HASH_CLASSES), rng.choice(HASH_FIELDS)
    obj, st = rng.choice(HASH_VARS)
    v1, v2 = rng.sample(range(1, 10_000), 2)  # хэш int = само число: хэши различаются
    code = (f"class {cls}:\n"
            f"    def __init__(self, {fld}):\n"
            f"        self.{fld} = {fld}\n"
            f"    def __eq__(self, other):\n"
            f"        return self.{fld} == other.{fld}\n"
            f"    def __hash__(self):\n"
            f"        return hash(self.{fld})\n"
            f"\n"
            f"{obj} = {cls}({v1})\n"
            f"{st} = set()\n"
            f"{st}.add({obj})\n"
            f"{obj}.{fld} = {v2}\n"
            f"print({obj} in {st})")
    out = run_python_snippet(code)
    correct, distractors = rng.choice(HASH_ROWS)
    text = (f"Объект {obj} добавили в множество {st}, а затем изменили его поле {fld}. "
            f"Программа печатает {out}, хотя в множество объект добавлен. Почему?")
    return mcq(rng, text, correct, distractors, code=code, language="python")
