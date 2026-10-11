"""«Работа с ИИ»: вердикты по решениям на Python (область python). Каталог — план 07a3, задача 5.

Каждое семейство: требование, эталон, 2–4 дефекта (замена ровно одной строки эталона) с классом-целью, представители
классов ломающего входа и 4 уточнения, на которые требование отвечает прямо. Какие классы ломают показанное решение,
считает python_verdict исполнением эталона и решения на представителях.
"""
import random

from app.assessment.bank.base import Generated
from app.assessment.bank.verdicts import Mutation, Reps, ai_family, python_verdict

NOUNS = ("оплат", "баллов", "заказов", "просмотров", "бонусов", "ставок", "платежей", "откликов",
         "рейтингов", "переводов")
ACC = ("total", "acc", "result")
VAR = ("x", "v", "item")


@ai_family(code="ai.py.sum_above", area="python", space_size=27_000, median_time_s=50)
def sum_above(rng: random.Random, flawed: bool) -> Generated:
    t, noun, acc, v = rng.randint(1, 60), rng.choice(NOUNS), rng.choice(ACC), rng.choice(VAR)
    reference = (f"def solve(xs):\n"
                 f"    {acc} = 0\n"
                 f"    for {v} in xs:\n"
                 f"        if {v} is not None and {v} > {t}:\n"
                 f"            {acc} += {v}\n"
                 f"    return {acc}")
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve(xs) возвращает сумму {noun} из списка xs, которые строго больше {t}. "
              f"Значения None пропускаются. Для пустого списка — 0."),
        reference=reference,
        mutations=(Mutation(4, f"        if {v} > {t}:", cls="none"),
                   Mutation(4, f"        if {v} is not None and {v} >= {t}:", cls="boundary"),
                   Mutation(4, f"        if {v} is not None and abs({v}) > {t}:", cls="negative"),
                   Mutation(5, f"            {acc} = {v}", cls="dup")),
        cases={"empty": [], "none": [None, t + 2], "dup": [t + 1, t + 1], "negative": [-(t + 5), t + 1],
               "boundary": [t, t + 1]},
        clarify=(f"Включать ли значения, равные {t}?", "Что вернуть для пустого списка?",
                 "Как поступать с None в списке?", "Учитывать ли отрицательные значения?"))


# --- ai.py.average_capped -------------------------------------------------------------------
@ai_family(code="ai.py.average_capped", area="python", space_size=900 * 3 * len(NOUNS) * 24, median_time_s=60)
def average_capped(rng: random.Random, flawed: bool) -> Generated:
    cap, d, noun = rng.randint(100, 999), rng.randint(1, 3), rng.choice(NOUNS)
    a = cap // 2 + 1
    reference = (f"def solve(xs):\n"
                 f"    vals = [x for x in xs if x is not None and x <= {cap}]\n"
                 f"    if not vals:\n"
                 f"        return 0.0\n"
                 f"    return round(sum(vals) / len(vals), {d})")
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve(xs) возвращает среднее всех {noun} из xs, не больших {cap} (отрицательные тоже "
              f"учитываются). Значения None пропускаются. Результат округляется до {d} знаков после запятой. "
              f"Если таких значений нет — 0.0."),
        reference=reference,
        mutations=(Mutation(5, f"    return round(sum(vals) / len(xs), {d})", cls="none"),
                   Mutation(2, f"    vals = [x for x in xs if x is not None and x < {cap}]", cls="boundary"),
                   Mutation(3, "    if vals is None:", cls="empty")),
        cases={"empty": [], "none": [None, a], "dup": [a, a], "negative": [-a, a + 3], "boundary": [cap, 1]},
        clarify=(f"Включать ли значения, равные {cap}?", "Что вернуть, если подходящих значений нет?",
                 "Как поступать с None в списке?", "Учитывать ли отрицательные значения?"))


# --- ai.py.dedupe_first_k -------------------------------------------------------------------
ITEMS = ("тегов", "городов", "артикулов", "логинов", "кодов", "названий", "категорий", "ссылок")


@ai_family(code="ai.py.dedupe_first_k", area="python", space_size=28 * len(ITEMS) * 24 * 3, median_time_s=55)
def dedupe_first_k(rng: random.Random, flawed: bool) -> Generated:
    k, noun = rng.randint(3, 30), rng.choice(ITEMS)
    base = rng.randint(10, 90)
    reference = (f"def solve(xs):\n"
                 f"    seen = set()\n"
                 f"    out = []\n"
                 f"    for x in xs:\n"
                 f"        if x not in seen:\n"
                 f"            seen.add(x)\n"
                 f"            out.append(x)\n"
                 f"            if len(out) == {k}:\n"
                 f"                break\n"
                 f"    return out")
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve(xs) возвращает различные значения {noun} из xs в порядке первого появления, не больше "
              f"{k} штук. None считается обычным значением. Для пустого списка — []."),
        reference=reference,
        mutations=(Mutation(5, "        if x not in out[-1:]:", cls="dup"),
                   Mutation(8, f"            if len(out) > {k}:", cls="boundary")),
        cases={"empty": [], "none": [None, base, None], "dup": [base, base + 1, base, base + 2],
               "boundary": list(range(base, base + k + 1))},
        clarify=(f"Сколько значений вернуть самое большее — {k}?", "В каком порядке вернуть значения?",
                 "Что вернуть для пустого списка?", "Как быть с None в списке?"))


# --- ai.py.normalize_login ------------------------------------------------------------------
PREFIXES = ("u_", "dev_", "id-", "usr", "acc_", "team-", "ext_", "ru_", "hr-", "op_", "qa_", "pm-", "ci_", "bot_",
            "tmp_", "new-", "gst_", "adm_", "x_", "st-")


@ai_family(code="ai.py.normalize_login", area="python", space_size=len(PREFIXES) * 21 * 24 * 3, median_time_s=50)
def normalize_login(rng: random.Random, flawed: bool) -> Generated:
    prefix, length = rng.choice(PREFIXES), rng.randint(12, 32)
    reference = (f"def solve(s):\n"
                 f"    if s is None:\n"
                 f"        return \"\"\n"
                 f"    return (\"{prefix}\" + s.strip().lower())[:{length}]")
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve(s) нормализует логин: убирает пробелы по краям, делает все буквы (включая кириллицу) "
              f"строчными, добавляет в начало «{prefix}» и обрезает результат до {length} символов. "
              f"Для None — пустая строка."),
        reference=reference,
        mutations=(Mutation(4, f"    return (\"{prefix}\" + s.strip())[:{length}]", cls="unicode"),
                   Mutation(4, f"    return (\"{prefix}\" + s.strip().lower())[:{length - 1}]", cls="boundary"),
                   Mutation(2, "    if s == \"\":", cls="none")),
        cases={"empty": "", "none": None, "unicode": "  ЁЖ Иванов ", "boundary": "a" * length},
        clarify=(f"До скольких символов обрезать — {length}?", "Что вернуть для None?",
                 "Приводить ли кириллицу к строчным буквам?", "Убирать ли пробелы по краям?"))


# --- ai.py.count_words_len ------------------------------------------------------------------
WORD_NOUNS = (("слов", "Слова"), ("тегов", "Теги"), ("токенов", "Токены"), ("терминов", "Термины"))


TEXT_ARGS = ("s", "text", "line", "raw")
WORD_VARS = ("w", "word", "tok", "part")


@ai_family(code="ai.py.count_words_len", area="python",
           space_size=8 * len(WORD_NOUNS) * len(TEXT_ARGS) * len(WORD_VARS) * 24 * 3, median_time_s=45)
def count_words_len(rng: random.Random, flawed: bool) -> Generated:
    m, (noun, plural) = rng.randint(2, 9), rng.choice(WORD_NOUNS)
    s, w = rng.choice(TEXT_ARGS), rng.choice(WORD_VARS)
    word = "к" * m
    reference = f"def solve({s}):\n    return sum(1 for {w} in {s}.split() if len({w}) >= {m})"
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve({s}) считает {noun} длиной не меньше {m} символов. {plural} разделены любыми пробельными "
              f"символами, включая неразрывный пробел. Для пустой строки — 0."),
        reference=reference,
        mutations=(Mutation(2, f"    return sum(1 for {w} in {s}.split(\" \") if len({w}) >= {m})", cls="unicode"),
                   Mutation(2, f"    return sum(1 for {w} in {s}.split() if len({w}) > {m})", cls="boundary")),
        cases={"empty": "", "dup": f"{word}д {word}д", "unicode": f"{word} {word}",
               "boundary": f"{'a' * m} {'b' * (m - 1)}"},
        clarify=(f"Считать ли {noun} ровно из {m} символов?", "Что вернуть для пустой строки?",
                 "Считать ли неразрывный пробел разделителем?", "Считать ли повторяющиеся значения отдельно?"))


# --- ai.py.max_or_default -------------------------------------------------------------------
DEFAULTS = tuple(range(-100, 0)) + tuple(range(1, 101))


@ai_family(code="ai.py.max_or_default", area="python", space_size=len(DEFAULTS) * len(NOUNS) * 24, median_time_s=45)
def max_or_default(rng: random.Random, flawed: bool) -> Generated:
    default, noun = rng.choice(DEFAULTS), rng.choice(NOUNS)
    a = rng.randint(5, 50)
    reference = (f"def solve(xs):\n"
                 f"    best = None\n"
                 f"    for x in xs:\n"
                 f"        if x is not None and (best is None or x > best):\n"
                 f"            best = x\n"
                 f"    return {default} if best is None else best")
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve(xs) возвращает наибольшее значение {noun} в xs; значения None пропускаются, отрицательные "
              f"учитываются. Если чисел нет — {default}."),
        reference=reference,
        mutations=(Mutation(2, "    best = 0", cls="negative"),
                   Mutation(6, "    return best", cls="empty")),
        cases={"empty": [], "none": [None, a], "dup": [a, a], "negative": [-(a + 3), -a]},
        clarify=("Что вернуть, если чисел нет?", "Как поступать с None?", "Учитывать ли отрицательные значения?",
                 "Что вернуть при нескольких одинаковых максимумах?"))


# --- ai.py.parse_ints -----------------------------------------------------------------------
SEPARATORS = (",", ";", "|", "/")


PART_VARS = ("p", "part", "chunk")


@ai_family(code="ai.py.parse_ints", area="python",
           space_size=len(SEPARATORS) * 19 * len(TEXT_ARGS) * len(PART_VARS) * 24 * 4, median_time_s=55)
def parse_ints(rng: random.Random, flawed: bool) -> Generated:
    sep, n = rng.choice(SEPARATORS), rng.randint(2, 20)
    s, p = rng.choice(TEXT_ARGS), rng.choice(PART_VARS)
    reference = (f"def solve({s}):\n"
                 f"    if not {s}.strip():\n"
                 f"        return []\n"
                 f"    return [int({p}) for {p} in {s}.split(\"{sep}\")][:{n}]")
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve({s}) превращает строку целых чисел через «{sep}» в список int и возвращает не больше "
              f"{n} первых. Пробелы вокруг чисел и отрицательные числа допустимы. Для строки из одних пробелов — []."),
        reference=reference,
        mutations=(Mutation(2, f"    if not {s}:", cls="empty"),
                   Mutation(4, f"    return [int({p}) for {p} in {s}.split(\"{sep}\") if {p}.strip().isdigit()][:{n}]",
                            cls="negative"),
                   Mutation(4, f"    return [int({p}) for {p} in {s}.split(\"{sep}\")][:{n - 1}]", cls="boundary")),
        cases={"empty": "   ", "dup": f"3{sep}3", "negative": f"1{sep} -2", "boundary": sep.join(map(str, range(1, n + 1)))},
        clarify=(f"Сколько чисел вернуть самое большее — {n}?", "Допустимы ли отрицательные числа?",
                 "Что вернуть для строки из одних пробелов?", "Допустимы ли пробелы вокруг чисел?"))


# --- ai.py.pages_count ----------------------------------------------------------------------
ARGS = ("n", "count", "total", "rows", "items")
RECORDS = ("записей", "товаров", "заказов", "комментариев")


@ai_family(code="ai.py.pages_count", area="python", space_size=99 * len(ARGS) * len(RECORDS) * 24 * 3,
           median_time_s=40)
def pages_count(rng: random.Random, flawed: bool) -> Generated:
    k, arg, records = rng.randint(2, 100), rng.choice(ARGS), rng.choice(RECORDS)
    reference = f"def solve({arg}):\n    return ({arg} + {k} - 1) // {k}"
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve({arg}) возвращает, сколько страниц нужно, чтобы показать {arg} {records} по {k} на "
              f"странице ({arg} ≥ 0). Неполная страница тоже считается. Для 0 {records} — 0 страниц."),
        reference=reference,
        mutations=(Mutation(2, f"    return {arg} // {k}", cls="boundary"),
                   Mutation(2, f"    return {arg} // {k} + 1", cls="empty")),
        cases={"empty": 0, "boundary": Reps((k, k + 1))},  # обе стороны границы: ровно k и k + 1
        clarify=(f"Что вернуть для 0 {records}?", f"Сколько {records} на странице?",
                 "Считать ли неполную страницу?", f"Может ли {arg} быть отрицательным?"))


# --- ai.py.merge_counts ---------------------------------------------------------------------
COUNTED = ("просмотров", "кликов", "покупок", "ошибок", "лайков", "заказов")


PAIRS = (("k", "v"), ("key", "n"), ("name", "cnt"))
OUTS = ("out", "res", "merged")


@ai_family(code="ai.py.merge_counts", area="python", space_size=20 * len(COUNTED) * len(PAIRS) * len(OUTS) * 24 * 3,
           median_time_s=60)
def merge_counts(rng: random.Random, flawed: bool) -> Generated:
    m, noun = rng.randint(1, 20), rng.choice(COUNTED)
    (k, v), out = rng.choice(PAIRS), rng.choice(OUTS)
    reference = (f"def solve(args):\n"
                 f"    a, b = args\n"
                 f"    {out} = dict(a)\n"
                 f"    for {k}, {v} in b.items():\n"
                 f"        {out}[{k}] = {out}.get({k}, 0) + {v}\n"
                 f"    return {{{k}: {v} for {k}, {v} in {out}.items() if {v} >= {m}}}")
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve(args) получает пару словарей-счётчиков {noun} (a, b) и складывает их: для общего ключа "
              f"значения суммируются, ключи сравниваются как есть. В результате остаются ключи с итогом не меньше {m}."),
        reference=reference,
        mutations=(Mutation(5, f"        {out}[{k}] = {v}", cls="dup"),
                   Mutation(6, f"    return {{{k}: {v} for {k}, {v} in {out}.items() if {v} > {m}}}", cls="boundary")),
        cases={"empty": ({}, {}), "dup": ({"x": m}, {"x": m}), "negative": ({"x": m + 5}, {"x": -3}),
               "boundary": ({"x": m}, {})},
        clarify=("Что делать с ключом, который есть в обоих словарях?", f"Оставлять ли ключи с итогом ровно {m}?",
                 "Приводить ли ключи к одному регистру?", "Что вернуть для двух пустых словарей?"))


# --- ai.py.chunk_k --------------------------------------------------------------------------
LISTS = ("xs", "items", "rows", "ids")


INDEXES = ("i", "j", "start")


@ai_family(code="ai.py.chunk_k", area="python", space_size=8 * len(NOUNS) * len(LISTS) * len(INDEXES) * 24 * 3,
           median_time_s=45)
def chunk_k(rng: random.Random, flawed: bool) -> Generated:
    k, noun = rng.randint(2, 9), rng.choice(NOUNS)
    xs, i = rng.choice(LISTS), rng.choice(INDEXES)
    a = rng.randint(1, 99)
    reference = f"def solve({xs}):\n    return [{xs}[{i}:{i} + {k}] for {i} in range(0, len({xs}), {k})]"
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve({xs}) разбивает список {noun} на части по {k} подряд идущих элементов; последняя часть "
              "может быть короче. Для пустого списка — []."),
        reference=reference,
        mutations=(Mutation(2, f"    return [{xs}[{i}:{i} + {k}] for {i} in range(0, len({xs}) - {k} + 1, {k})]",
                            cls="boundary"),
                   Mutation(2, f"    return [{xs}[{i}:{i} + {k}] for {i} in range(1, len({xs}), {k})]", cls="dup")),
        cases={"empty": [], "dup": [a] * k, "negative": [-a, -a - 1], "boundary": list(range(1, k + 2))},
        clarify=(f"По сколько элементов делить — {k}?", "Может ли последняя часть быть короче?",
                 "Что вернуть для пустого списка?", "Сохранять ли порядок элементов?"))


# --- ai.py.unique_tags ----------------------------------------------------------------------
TAG_KINDS = (("tags", "тегов", "Теги"), ("labels", "меток", "Метки"), ("names", "названий", "Названия"),
             ("words", "ключевых слов", "Ключевые слова"))
TAG_VARS = ("t", "tag", "x")


@ai_family(code="ai.py.unique_tags", area="python", space_size=26 * len(TAG_KINDS) * len(TAG_VARS) * 24 * 4,
           median_time_s=50)
def unique_tags(rng: random.Random, flawed: bool) -> Generated:
    length = rng.randint(5, 30)
    (arg, noun, plural), t = rng.choice(TAG_KINDS), rng.choice(TAG_VARS)
    reference = f"def solve({arg}):\n    return len({{{t}.strip().lower() for {t} in {arg} if len({t}.strip()) <= {length}}})"
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve({arg}) возвращает число различных {noun} без учёта регистра (в том числе для кириллицы) "
              f"и пробелов по краям. {plural} длиннее {length} символов (после удаления пробелов) не учитываются."),
        reference=reference,
        mutations=(Mutation(2, f"    return len({{{t}.strip() for {t} in {arg} if len({t}.strip()) <= {length}}})",
                            cls="unicode"),
                   Mutation(2, f"    return len({arg})", cls="dup"),
                   Mutation(2, f"    return len({{{t}.strip().lower() for {t} in {arg} if len({t}.strip()) < {length}}})",
                            cls="boundary")),
        cases={"empty": [], "dup": ["go", "go"], "unicode": ["Ёлка", "ёлка"], "boundary": ["x" * length]},
        clarify=("Учитывать ли регистр букв?", f"Считать ли {noun} длиной ровно {length} символов?",
                 "Убирать ли пробелы по краям?", "Что вернуть для пустого списка?"))


# --- ai.py.in_range_count -------------------------------------------------------------------
@ai_family(code="ai.py.in_range_count", area="python", space_size=50 * 96 * len(NOUNS) * 24, median_time_s=45)
def in_range_count(rng: random.Random, flawed: bool) -> Generated:
    lo = rng.randint(1, 50)
    hi, noun = lo + rng.randint(5, 100), rng.choice(NOUNS)
    reference = f"def solve(xs):\n    return sum(1 for x in xs if x is not None and {lo} <= x <= {hi})"
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve(xs) считает, сколько значений {noun} в xs лежит в диапазоне от {lo} до {hi} "
              "включительно. Значения None пропускаются, отрицательные в диапазон не попадают."),
        reference=reference,
        mutations=(Mutation(2, f"    return sum(1 for x in xs if x is not None and {lo} < x <= {hi})", cls="boundary"),
                   Mutation(2, f"    return sum(1 for x in xs if {lo} <= x <= {hi})", cls="none"),
                   Mutation(2, f"    return sum(1 for x in xs if x is not None and {lo} <= abs(x) <= {hi})",
                            cls="negative")),
        cases={"empty": [], "none": [None, lo + 1], "dup": [lo + 1, lo + 1], "negative": [-lo, lo + 1],
               "boundary": [lo, hi]},
        clarify=(f"Входят ли границы {lo} и {hi} в диапазон?", "Как поступать с None?",
                 "Что вернуть для пустого списка?", "Учитывать ли отрицательные значения?"))


# --- ai.py.password_ok ----------------------------------------------------------------------
SERVICES = ("банка", "почты", "CRM", "VPN", "магазина", "портала", "CI", "сервера", "кабинета", "склада")


@ai_family(code="ai.py.password_ok", area="python", space_size=len(SERVICES) * 15 * 3 * 24, median_time_s=45)
def password_ok(rng: random.Random, flawed: bool) -> Generated:
    service, length, n = rng.choice(SERVICES), rng.randint(6, 20), rng.randint(1, 3)
    reference = (f"def solve(s):\n"
                 f"    if s is None:\n"
                 f"        return False\n"
                 f"    return len(s) >= {length} and sum(ch in \"0123456789\" for ch in s) >= {n}")
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve(s) проверяет пароль для {service}: он подходит, если в нём не меньше {length} символов "
              f"и не меньше {n} цифр (0–9). None — не подходит."),
        reference=reference,
        mutations=(Mutation(4, f"    return len(s) > {length} and sum(ch in \"0123456789\" for ch in s) >= {n}",
                            cls="boundary"),
                   Mutation(2, "    if s == \"\":", cls="none")),
        cases={"empty": "", "none": None, "unicode": "Пароль" + "1" * max(n, length - 6),
               "boundary": "a" * (length - n) + "1" * n},
        clarify=(f"Подходит ли пароль ровно из {length} символов?", "Что вернуть для None?",
                 f"Сколько цифр нужно — {n}?", "Считать ли кириллические буквы символами пароля?"))


# --- ai.py.running_balance ------------------------------------------------------------------
BALANCES = ("balance", "bal", "cash", "total")
OPS = (("ops", "op"), ("moves", "m"), ("amounts", "x"))
ACCOUNTS = ("счёта", "кошелька", "карты")


@ai_family(code="ai.py.running_balance", area="python",
           space_size=99 * len(BALANCES) * len(OPS) * len(ACCOUNTS) * 24 * 3, median_time_s=55)
def running_balance(rng: random.Random, flawed: bool) -> Generated:
    start = rng.randrange(100, 5001, 50)
    step = rng.randrange(10, start // 2 + 1, 10)
    bal, (ops, op), account = rng.choice(BALANCES), rng.choice(OPS), rng.choice(ACCOUNTS)
    reference = (f"def solve({ops}):\n"
                 f"    {bal} = {start}\n"
                 f"    for {op} in {ops}:\n"
                 f"        if {bal} + {op} >= 0:\n"
                 f"            {bal} += {op}\n"
                 f"    return {bal}")
    return python_verdict(
        rng, flawed,
        text=(f"Функция solve({ops}) возвращает баланс {account} после операций {ops} при начальном балансе {start}. Пополнения — "
              "положительные числа, списания — отрицательные. Списание, после которого баланс стал бы отрицательным, "
              "отклоняется; баланс 0 допустим."),
        reference=reference,
        mutations=(Mutation(4, f"        if {bal} + {op} > 0:", cls="boundary"),
                   Mutation(5, f"            {bal} += abs({op})", cls="negative")),
        cases={"empty": [], "dup": [-step, -step], "negative": [-step], "boundary": [-start]},
        clarify=("Допустим ли нулевой баланс?", f"Какой начальный баланс — {start}?",
                 "Что делать со списанием, которое уводит баланс в минус?", "Чем отличаются пополнения от списаний?"))
