import datetime
import math
import random
from collections import Counter

from app.assessment.bank.base import SHUFFLES, Generated, Prompt, Table, family, mcq
from app.assessment.bank.families._vocab import CITIES, DEPTS, NAMES
from app.assessment.bank.sqlite_sandbox import run_query, setup_sql


@family(code="be.db.left_join_no_orders", specialization="backend", area="db", level=2,
        fmt="sql", space_size=10**6, median_time_s=60)
def left_join_no_orders(rng: random.Random) -> Generated:
    n_c = rng.randint(4, 7)
    names = rng.sample(NAMES, n_c)
    customers = Table("customers", ("id", "name", "city"),
                      tuple((i + 1, names[i], rng.choice(CITIES)) for i in range(n_c)))
    orders = Table("orders", ("id", "customer_id", "amount"),
                   tuple((i + 1, rng.randint(1, n_c), rng.randrange(100, 1000, 10))
                         for i in range(rng.randint(3, 8))))
    query = ("SELECT c.name\nFROM customers c\nLEFT JOIN orders o ON o.customer_id = c.id\n"
             "WHERE o.id IS NULL;")
    rows = run_query(setup_sql(customers, orders), query)
    return Generated(
        "number",
        Prompt(text="Сколько строк вернёт запрос?", code=query, language="sql",
               tables=(customers, orders), answer_hint="Целое число"),
        len(rows), ("left_join", "is_null_filter", len((customers, orders))),
    )


@family(code="be.db.avg_ignores_null", specialization="backend", area="db", level=3,
        fmt="sql", space_size=10**6, median_time_s=75)
def avg_ignores_null(rng: random.Random) -> Generated:
    n = rng.randint(6, 9)
    names = rng.sample(NAMES, n)
    dept = rng.choice(DEPTS)
    rows = []
    for i in range(n):
        d = dept if i < 4 else rng.choice(DEPTS)
        bonus = None if i in (1, 3) else rng.randrange(1000, 10000, 500)
        rows.append((i + 1, names[i], d, bonus))
    rng.shuffle(rows)
    t = Table("employees", ("id", "name", "dept", "bonus"), tuple(rows))
    query = f"SELECT AVG(bonus)\nFROM employees\nWHERE dept = '{dept}';"
    ((value,),) = run_query(setup_sql(t), query)
    return Generated(
        "number",
        Prompt(text="Какое значение вернёт запрос? Округлите до двух знаков после запятой.",
               code=query, language="sql", tables=(t,), answer_hint="Число, например 1234.5"),
        round(value, 2),
        ("avg", "nulls_in_group" if any(r[2] == dept and r[3] is None for r in rows) else "no_nulls"),
    )


# ---------------------------------------------------------------------------
# План 03b: наполнение области db
# ---------------------------------------------------------------------------
PRODUCTS = ("Ноутбук", "Мышь", "Клавиатура", "Монитор", "Наушники", "Чайник", "Блендер", "Пылесос",
            "Футболка", "Куртка", "Кроссовки", "Рюкзак", "Книга", "Блокнот", "Ручка", "Лампа")


# --- be.db.where_and_or_count ----------------------------------------------------
# категория -> товары этой категории (имя и категория берутся парой)
CATALOG = {
    "электроника": ("Ноутбук", "Мышь", "Клавиатура", "Монитор", "Наушники", "Веб-камера"),
    "одежда": ("Футболка", "Куртка", "Джинсы", "Свитер", "Шапка", "Перчатки"),
    "дом": ("Чайник", "Блендер", "Пылесос", "Лампа", "Тостер", "Подушка"),
    "книги": ("Роман", "Справочник", "Сказки", "Детектив", "Атлас", "Учебник"),
    "спорт": ("Кроссовки", "Мяч", "Гантели", "Скакалка", "Лыжи", "Коврик"),
    "канцелярия": ("Блокнот", "Ручка", "Маркер", "Степлер", "Папка", "Линейка"),
}
WHERE_PRICE_THRESHOLDS = tuple(range(300, 1500, 100))
WHERE_PRICES = tuple(range(100, 1900, 50))
WHERE_MIN_ROWS = 8
WHERE_TARGET_MIN = 3  # в целевой категории не меньше трёх товаров


@family(code="be.db.where_and_or_count", specialization="backend", area="db", level=1,
        fmt="sql",
        # нижняя граница (8 строк): целевая категория × порог × цены; названия и остальное не считаем
        space_size=len(CATALOG) * len(WHERE_PRICE_THRESHOLDS) * len(WHERE_PRICES) ** WHERE_MIN_ROWS,
        median_time_s=40)
def where_and_or_count(rng: random.Random) -> Generated:
    n = rng.randint(WHERE_MIN_ROWS, 12)
    cats = rng.sample(tuple(CATALOG), 4)
    target = rng.choice(cats)
    counts = dict.fromkeys(cats, 0)
    counts[target] = WHERE_TARGET_MIN
    for _ in range(n - WHERE_TARGET_MIN):
        counts[rng.choice([c for c in cats if counts[c] < len(CATALOG[c])])] += 1
    pairs = [(name, c) for c in cats for name in rng.sample(CATALOG[c], counts[c])]
    rng.shuffle(pairs)
    rows = tuple((i + 1, name, c, rng.choice(WHERE_PRICES), rng.randint(0, 1))
                 for i, (name, c) in enumerate(pairs))
    t = Table("products", ("id", "name", "category", "price", "in_stock"), rows)
    threshold = rng.choice(WHERE_PRICE_THRESHOLDS)
    query = (f"SELECT name\nFROM products\n"
             f"WHERE category = '{target}' AND (price > {threshold} OR in_stock = 1);")
    result = run_query(setup_sql(t), query)
    return Generated(
        "number",
        Prompt(text="Сколько строк вернёт запрос?", code=query, language="sql", tables=(t,),
               answer_hint="Целое число"),
        len(result), ("where", "and_or_parens"),
    )


# --- be.db.order_limit_value -----------------------------------------------------
# (таблица, колонка с именем, колонка сортировки, пул имён, значения сортируемой колонки)
ORDER_CONTEXTS = (
    ("employees", "name", "salary", NAMES, tuple(range(60_000, 200_000, 5_000))),
    ("products", "title", "price", PRODUCTS, tuple(range(100, 5_000, 50))),
    ("students", "name", "score", NAMES, tuple(range(40, 100))),
    ("athletes", "name", "result", NAMES, tuple(range(100, 400))),
)


def _order_space() -> int:
    total = 0
    for _, _, _, pool, values in ORDER_CONTEXTS:
        for n in range(6, 10):
            total += math.perm(len(pool), n) * math.perm(len(values), n)
    return total


@family(code="be.db.order_limit_value", specialization="backend", area="db", level=1,
        fmt="sql", space_size=_order_space(), median_time_s=35)
def order_limit_value(rng: random.Random) -> Generated:
    tname, name_col, val_col, pool, values = rng.choice(ORDER_CONTEXTS)
    n = rng.randint(6, 9)
    names = rng.sample(pool, n)
    vals = rng.sample(values, n)  # значения сортируемой колонки уникальны
    t = Table(tname, ("id", name_col, val_col), tuple((i + 1, names[i], vals[i]) for i in range(n)))
    query = f"SELECT {name_col}\nFROM {tname}\nORDER BY {val_col} DESC\nLIMIT 1;"
    ((answer,),) = run_query(setup_sql(t), query)
    return Generated(
        "text",
        Prompt(text="Какое значение вернёт запрос?", code=query, language="sql", tables=(t,),
               # текстовый ответ сравнивается с учётом регистра (у канонизации нет правил по семействам)
               answer_hint=f"Значение колонки {name_col} — в точности как в таблице, с учётом регистра"),
        answer, ("order_by_desc", "limit_1"),
    )


# --- be.db.group_having_count ----------------------------------------------------
HAVING_AMOUNTS = tuple(range(100, 1000, 10))  # 90 значений


@family(code="be.db.group_having_count", specialization="backend", area="db", level=2,
        fmt="sql",
        # нижняя граница: порог × набор из 4 клиентов × выбор клиента в каждой из 10 строк (суммы не считаем)
        space_size=3 * math.comb(len(NAMES), 4) * 4 ** 10,
        median_time_s=55)
def group_having_count(rng: random.Random) -> Generated:
    n_c = rng.randint(4, 6)
    clients = rng.sample(NAMES, n_c)
    n = rng.randint(10, 16)
    rows = tuple((i + 1, rng.choice(clients), rng.choice(HAVING_AMOUNTS)) for i in range(n))
    t = Table("orders", ("id", "customer", "amount"), rows)
    k = rng.randint(1, 3)
    query = f"SELECT customer\nFROM orders\nGROUP BY customer\nHAVING COUNT(*) > {k};"
    result = run_query(setup_sql(t), query)
    return Generated(
        "number",
        Prompt(text="Сколько строк вернёт запрос?", code=query, language="sql", tables=(t,),
               answer_hint="Целое число"),
        len(result), ("group_by", "having_count"),
    )


# --- be.db.inner_join_rows -------------------------------------------------------
@family(code="be.db.inner_join_rows", specialization="backend", area="db", level=2,
        fmt="sql",
        # нижняя граница: имена 4 клиентов × связи 6 заказов (минимум 6 вариантов клиента на заказ)
        space_size=math.perm(len(NAMES), 4) * 6 ** 6,
        median_time_s=60)
def inner_join_rows(rng: random.Random) -> Generated:
    while True:
        n_c = rng.randint(4, 6)
        n_o = rng.randint(6, 10)
        # номера сверх n_c — заказы без клиента (нет пары)
        links = [rng.randint(1, n_c + 2) for _ in range(n_o)]
        per = [links.count(i) for i in range(1, n_c + 1)]
        if min(per) == 0 and max(per) >= 2 and max(links) > n_c:
            break
    names = rng.sample(NAMES, n_c)
    customers = Table("customers", ("id", "name"), tuple((i + 1, names[i]) for i in range(n_c)))
    orders = Table("orders", ("id", "customer_id", "amount"),
                   tuple((i + 1, links[i], rng.randrange(100, 1000, 10)) for i in range(n_o)))
    query = ("SELECT c.name, o.id\nFROM customers c\n"
             "INNER JOIN orders o ON o.customer_id = c.id;")
    result = run_query(setup_sql(customers, orders), query)
    return Generated(
        "number",
        Prompt(text="Сколько строк вернёт запрос?", code=query, language="sql",
               tables=(customers, orders), answer_hint="Целое число"),
        len(result), ("inner_join", "one_to_many"),
    )


# --- be.db.count_variants_nulls --------------------------------------------------
COUNT_TICKETS = tuple(f"TCK-{i}" for i in range(101, 141))
COUNT_SHIPMENTS = tuple(f"SHP-{i}" for i in range(201, 241))
# (таблица, колонка с повторами и NULL, значения колонки, подписи строк)
COUNT_CONTEXTS = (
    ("tickets", "assignee", NAMES, COUNT_TICKETS),
    ("customers", "city", CITIES + ("Уфа", "Сочи", "Рязань"), NAMES),
    ("employees", "dept", DEPTS + ("qa", "fin", "legal"), NAMES),
    ("shipments", "carrier", ("DHL", "СДЭК", "Почта", "Boxberry", "ПЭК", "Деловые линии"),
     COUNT_SHIPMENTS),
)
COUNT_ROWS = range(10, 15)
COUNT_DISTINCT = range(2, 7)
COUNT_NULLS = range(2, 4)


def _count_space() -> int:
    total = 0
    for _, _, pool, labels in COUNT_CONTEXTS:
        for n in COUNT_ROWS:
            for k in COUNT_DISTINCT:
                for nulls in COUNT_NULLS:
                    # нижняя граница: набор значений × позиции NULL × подписи строк
                    total += math.comb(len(pool), k) * math.comb(n, nulls) * math.perm(len(labels), n)
    return total


@family(code="be.db.count_variants_nulls", specialization="backend", area="db", level=3,
        fmt="sql", space_size=_count_space(), median_time_s=70)
def count_variants_nulls(rng: random.Random) -> Generated:
    tname, col, pool, label_pool = rng.choice(COUNT_CONTEXTS)
    n = rng.choice(COUNT_ROWS)
    k = rng.choice(COUNT_DISTINCT)
    nulls = rng.choice(COUNT_NULLS)
    distinct = rng.sample(pool, k)
    # n - nulls - k >= 1: хотя бы один повтор; COUNT(*), COUNT(col), COUNT(DISTINCT col) различны
    vals = [*distinct, *(rng.choice(distinct) for _ in range(n - nulls - k)), *([None] * nulls)]
    rng.shuffle(vals)
    labels = rng.sample(label_pool, n)
    t = Table(tname, ("id", "label", col), tuple((i + 1, labels[i], vals[i]) for i in range(n)))
    query = f"SELECT COUNT(DISTINCT {col})\nFROM {tname};"
    ((answer,),) = run_query(setup_sql(t), query)
    return Generated(
        "number",
        Prompt(text="Какое значение вернёт запрос?", code=query, language="sql", tables=(t,),
               answer_hint="Целое число"),
        answer, ("count_distinct", "nulls_and_repeats"),
    )


# --- be.db.not_in_null_trap ------------------------------------------------------
# (основная таблица, колонка названия, пул названий, таблица подзапроса, её колонка)
NOT_IN_CONTEXTS = (
    ("users", "name", NAMES, "bans", "user_id"),
    ("products", "title", PRODUCTS, "discontinued", "product_id"),
    ("employees", "name", NAMES, "dismissals", "employee_id"),
)


NOT_IN_ROWS = range(6, 10)
NOT_IN_K = range(2, 4)  # сколько обычных значений в подзапросе


def _not_in_space() -> int:
    total = 0
    for _, _, pool, _, _ in NOT_IN_CONTEXTS:
        for n in NOT_IN_ROWS:
            for k in NOT_IN_K:
                # названия × какие id в подзапросе × порядок строк подзапроса × порядок вариантов
                total += math.perm(len(pool), n) * math.comb(n, k) * (k + 1) * SHUFFLES
    return total


@family(code="be.db.not_in_null_trap", specialization="backend", area="db", level=3,
        fmt="sql", space_size=_not_in_space(), median_time_s=75)
def not_in_null_trap(rng: random.Random) -> Generated:
    mname, label_col, pool, sname, scol = rng.choice(NOT_IN_CONTEXTS)
    while True:
        n = rng.choice(NOT_IN_ROWS)
        k = rng.choice(NOT_IN_K)
        if n != 2 * k:  # иначе «читается как IN» (k) совпало бы с «читается как NOT EXISTS» (n - k)
            break
    names = rng.sample(pool, n)
    main = Table(mname, ("id", label_col), tuple((i + 1, names[i]) for i in range(n)))
    sub_vals = [*rng.sample(range(1, n + 1), k), *([None] * rng.randint(1, 2))]
    rng.shuffle(sub_vals)
    sub = Table(sname, (scol,), tuple((v,) for v in sub_vals))
    setup = setup_sql(main, sub)
    query = f"SELECT {label_col}\nFROM {mname}\nWHERE id NOT IN (SELECT {scol} FROM {sname});"
    actual = len(run_query(setup, query))
    # «как если бы NULL не было» (NOT EXISTS) и «строки, попавшие в подзапрос» (IN)
    not_exists = len(run_query(
        setup, f"SELECT 1 FROM {mname} m WHERE NOT EXISTS (SELECT 1 FROM {sname} s WHERE s.{scol} = m.id)"))
    in_reading = len(run_query(setup, f"SELECT 1 FROM {mname} WHERE id IN (SELECT {scol} FROM {sname})"))
    assert actual == 0 and len({actual, not_exists, in_reading, n}) == 4
    return mcq(rng, "Сколько строк вернёт запрос?", str(actual),
               (str(not_exists), str(in_reading), str(n)), code=query, language="sql",
               tables=(main, sub))


# --- be.db.window_rank -----------------------------------------------------------
@family(code="be.db.window_rank", specialization="backend", area="db", level=4,
        fmt="sql",
        # нижняя граница: имена 6 из 16 × 4 различных балла из 50 × вопрос про одну строку
        space_size=math.perm(len(NAMES), 6) * math.comb(50, 4),
        median_time_s=100)
def window_rank(rng: random.Random) -> Generated:
    n = rng.randint(6, 9)
    d = rng.randint(1, 2)  # сколько баллов повторено
    k = n - d
    base = sorted(rng.sample(range(50, 100), k), reverse=True)
    # повторяем не самый низкий балл: ниже группы равных всегда есть строка с RANK <> DENSE_RANK
    dup_idx = rng.sample(range(k - 1), d)  # включая верхнюю группу равных
    scores = base + [base[i] for i in dup_idx]
    names = rng.sample(NAMES, n)
    rows = [(names[i], scores[i]) for i in range(n)]
    rng.shuffle(rows)
    t = Table("results", ("id", "name", "score"), tuple((i + 1, *r) for i, r in enumerate(rows)))
    setup = setup_sql(t)
    inner = "SELECT name, RANK() OVER (ORDER BY score DESC) AS rnk\nFROM results"
    both = run_query(setup, "SELECT name, RANK() OVER (ORDER BY score DESC), "
                            "DENSE_RANK() OVER (ORDER BY score DESC) FROM results")
    lowest = min(scores)
    tied = Counter(scores)
    by_name = dict(rows)
    # спрашиваем строку внутри группы равных или сразу после неё; самую низкую по баллу — никогда
    candidates = sorted(nm for nm, r, dr in both
                        if by_name[nm] != lowest and (r != dr or tied[by_name[nm]] > 1))
    who = rng.choice(candidates)
    ((answer,),) = run_query(setup, f"SELECT rnk FROM (\n{inner}\n) AS q WHERE name = '{who}'")
    return Generated(
        "number",
        Prompt(text=f"Какое значение rnk получит строка, где name = '{who}'?",
               code=inner + ";", language="sql", tables=(t,), answer_hint="Целое число"),
        answer, ("rank", "ties", "order_by_desc"),
    )


# --- be.db.composite_index_order -------------------------------------------------
# таблица -> (колонки для равенства, для диапазона, для сортировки)
INDEX_TABLES = {
    "orders": (("status", "channel", "city"), ("created_at", "total", "weight"),
               ("amount", "priority", "number")),
    "tickets": (("status", "category", "queue"), ("created_at", "deadline", "estimate"),
                ("severity", "priority", "title")),
    "events": (("user_id", "event_type", "source"), ("created_at", "duration", "size"),
               ("level", "region", "latency")),
    "payments": (("account_id", "currency", "method"), ("paid_at", "amount", "fee"),
                 ("status", "reference", "bank")),
    "products": (("category_id", "brand", "country"), ("price", "rating", "created_at"),
                 ("stock", "weight", "title")),
    "sessions": (("user_id", "device", "country"), ("started_at", "duration", "bytes"),
                 ("browser", "referrer", "status")),
}
INDEX_OPS = (">", ">=", "<", "<=")
INDEX_SELECTS = ("*", "id")
INDEX_DIRS = ("", " DESC")


def _index_space() -> int:
    combos = sum(len(e) * len(r) * len(o) for e, r, o in INDEX_TABLES.values())
    return combos * len(INDEX_OPS) * len(INDEX_SELECTS) * len(INDEX_DIRS) * SHUFFLES


@family(code="be.db.composite_index_order", specialization="backend", area="db", level=4,
        fmt="mcq", space_size=_index_space(), median_time_s=100)
def composite_index_order(rng: random.Random) -> Generated:
    t = rng.choice(tuple(INDEX_TABLES))
    eq_cols, range_cols, order_cols = INDEX_TABLES[t]
    a, b, c = rng.choice(eq_cols), rng.choice(range_cols), rng.choice(order_cols)
    query = (f"SELECT {rng.choice(INDEX_SELECTS)}\nFROM {t}\n"
             f"WHERE {a} = $1 AND {b} {rng.choice(INDEX_OPS)} $2\n"
             f"ORDER BY {c}{rng.choice(INDEX_DIRS)};")
    text = (f"Таблица {t} большая, запрос выполняется часто (PostgreSQL, индексы B-tree). "
            "Какой составной индекс лучше всего поддержит фильтрацию в WHERE этого запроса?")
    # четыре двухколоночных индекса: две пары с переставленными колонками
    return mcq(
        rng, text, f"индекс {t} ({a}, {b})",
        (f"индекс {t} ({b}, {a})", f"индекс {t} ({b}, {c})", f"индекс {t} ({c}, {b})"),
        code=query, language="sql",
    )


# --- be.db.n_plus_one_count ------------------------------------------------------
# (родитель, таблица, связь, потомок, таблица потомка, внешний ключ, атрибут потомка,
#  колонка фильтра, значения фильтра, колонки сортировки)
ORM_CONTEXTS = (
    ("Author", "authors", "books", "Book", "books", "author_id", "title", "country",
     ("Россия", "Франция", "Италия", "Испания", "Польша"), ("name", "surname", "birth_year")),
    ("Order", "orders", "items", "OrderItem", "order_items", "order_id", "sku", "status",
     ("new", "paid", "shipped", "canceled", "returned"), ("number", "created_at", "total")),
    ("Team", "teams", "members", "Member", "members", "team_id", "name", "department",
     ("backend", "frontend", "data", "mobile", "qa"), ("title", "created_at", "size")),
    ("Course", "courses", "lessons", "Lesson", "lessons", "course_id", "title", "level",
     ("intro", "basic", "middle", "advanced", "expert"), ("name", "created_at", "price")),
    ("Customer", "customers", "orders", "Order", "orders", "customer_id", "number", "city",
     CITIES, ("name", "created_at", "balance")),
    ("Project", "projects", "tasks", "Task", "tasks", "project_id", "title", "status",
     ("active", "paused", "closed", "draft", "review"), ("name", "deadline", "budget")),
    ("Album", "albums", "tracks", "Track", "tracks", "album_id", "title", "genre",
     ("rock", "jazz", "pop", "folk", "metal"), ("name", "released_at", "rating")),
    ("Department", "departments", "employees", "Employee", "employees", "department_id", "name",
     "city", CITIES, ("title", "founded_at", "budget")),
)
ORM_NUMERIC_COLUMNS = frozenset({"birth_year", "total", "size", "price", "balance", "budget", "rating"})
ORM_N = range(5, 41)
ORM_BODIES = 2
ORM_LOOP_VARS = ("obj", "row", "item", "entry", "rec")
ORM_LIST_VARS = ("rows", "parents", "result")


def _orm_type(column: str) -> str:
    """Тип колонки модели по смыслу имени: даты — DateTime, числа — Integer, остальное — String."""
    if column.endswith("_at") or column == "deadline":
        return "DateTime"
    return "Integer" if column in ORM_NUMERIC_COLUMNS else "String"


def _orm_space() -> int:
    per_ctx = sum(len(c[9]) * len(c[8]) for c in ORM_CONTEXTS)
    return per_ctx * len(ORM_N) * ORM_BODIES * len(ORM_LOOP_VARS) * len(ORM_LIST_VARS)


@family(code="be.db.n_plus_one_count", specialization="backend", area="db", level=4,
        fmt="output", space_size=_orm_space(), median_time_s=100)
def n_plus_one_count(rng: random.Random) -> Generated:
    (parent, table, rel, child, child_table, fk, attr, filter_col, filter_values,
     order_cols) = rng.choice(ORM_CONTEXTS)
    n = rng.choice(ORM_N)
    var = rng.choice(ORM_LOOP_VARS)
    lst = rng.choice(ORM_LIST_VARS)
    order = rng.choice(order_cols)
    value = rng.choice(filter_values)
    if rng.randrange(ORM_BODIES) == 0:
        body = f"    print({var}.id, len({var}.{rel}))"
    else:
        body = f"    print([x.{attr} for x in {var}.{rel}])"
    code = (f"class {parent}(Base):\n"
            f"    __tablename__ = \"{table}\"\n"
            f"    id = Column(Integer, primary_key=True)\n"
            f"    {filter_col} = Column({_orm_type(filter_col)})\n"
            f"    {order} = Column({_orm_type(order)})\n"
            f"    {rel} = relationship(\"{child}\")\n\n"
            f"class {child}(Base):\n"
            f"    __tablename__ = \"{child_table}\"\n"
            f"    id = Column(Integer, primary_key=True)\n"
            f"    {fk} = Column(Integer, ForeignKey(\"{table}.id\"))\n"
            f"    {attr} = Column({_orm_type(attr)})\n\n"
            f"{lst} = (session.query({parent})\n"
            f"        .filter({parent}.{filter_col} == \"{value}\")\n"
            f"        .order_by({parent}.{order})\n"
            f"        .limit({n})\n"
            f"        .all())\n"
            f"for {var} in {lst}:\n{body}")
    text = (f"Связь {parent}.{rel} загружается лениво (lazy loading, стратегия SQLAlchemy по умолчанию): "
            "без join, joinedload и selectinload. В базе заведомо больше подходящих записей, чем лимит, "
            "у каждой есть связанные записи, сессия новая. "
            "Сколько всего SELECT-запросов к базе выполнит этот код?")
    return Generated(
        "number",
        Prompt(text=text, code=code, language="python", answer_hint="Целое число"),
        n + 1, ("orm", "lazy_load"),
    )


# --- be.db.isolation_anomaly -----------------------------------------------------
ANOMALY_OPTIONS = {
    "lost": "Потерянное обновление (lost update)",
    "nonrep": "Неповторяющееся чтение (non-repeatable read)",
    "phantom": "Фантомное чтение (phantom read)",
    "skew": "Перекос записи (write skew)",
}
# (таблица, колонка, кто и что списывает — для комментария к расписанию потерянного обновления)
VALUE_CONTEXTS = (("accounts", "balance", "два платежа списывают деньги с одного счёта"),
                  ("wallets", "amount", "две покупки списывают деньги с одного кошелька"),
                  ("products", "stock", "два заказа списывают остаток одного товара"),
                  ("counters", "value", "два обработчика уменьшают один счётчик"))
ROW_IDS = range(1, 100)
BASE_VALUES = tuple(range(100, 900, 10))
DELTAS = tuple(range(5, 50, 5))
PHANTOM_COUNTS = range(2, 10)
PHANTOM_IDS = range(100, 1000)
PHANTOM_CONTEXTS = (("orders", "status", "'new'"), ("tasks", "state", "'open'"),
                    ("tickets", "status", "'new'"), ("bookings", "status", "'pending'"))
SKEW_CONTEXTS = (("doctors", "on_call", "врач"), ("engineers", "on_duty", "инженер"),
                 ("admins", "is_active", "администратор"))
SKEW_PAIRS = math.perm(len(NAMES), 2)


# Первая строка каждого расписания — комментарий о сценарии в одном стиле (кто что делает или какое
# правило действует): он не называет аномалию и сообщает не больше, чем видно из самих шагов.
def _lost(rng: random.Random) -> str:
    t, col, who = rng.choice(VALUE_CONTEXTS)
    rid, v = rng.choice(ROW_IDS), rng.choice(BASE_VALUES)
    d1, d2 = rng.sample(DELTAS, 2)
    sel = f"SELECT {col} FROM {t} WHERE id = {rid};"
    # T2 пишет только после COMMIT T1 (в PostgreSQL иначе она бы ждала), но значение считает от старого чтения
    return (f"-- {who}\nT1: BEGIN;\nT2: BEGIN;\n"
            f"T1: {sel}  -- {v}\nT2: {sel}  -- {v}\n"
            f"T1: UPDATE {t} SET {col} = {v - d1} WHERE id = {rid};\nT1: COMMIT;\n"
            f"T2: UPDATE {t} SET {col} = {v - d2} WHERE id = {rid};\nT2: COMMIT;")


def _nonrep(rng: random.Random) -> str:
    t, col, _ = rng.choice(VALUE_CONTEXTS)
    rid, v = rng.choice(ROW_IDS), rng.choice(BASE_VALUES)
    v2 = v - rng.choice(DELTAS)
    sel = f"SELECT {col} FROM {t} WHERE id = {rid};"
    return (f"-- отчёт читает значение дважды в одной транзакции\nT1: BEGIN;\nT1: {sel}  -- {v}\nT2: BEGIN;\n"
            f"T2: UPDATE {t} SET {col} = {v2} WHERE id = {rid};\nT2: COMMIT;\n"
            f"T1: {sel}  -- {v2}\nT1: COMMIT;")


def _phantom(rng: random.Random) -> str:
    t, col, val = rng.choice(PHANTOM_CONTEXTS)
    cnt, new_id = rng.choice(PHANTOM_COUNTS), rng.choice(PHANTOM_IDS)
    sel = f"SELECT COUNT(*) FROM {t} WHERE {col} = {val};"
    return (f"-- отчёт считает строки по условию дважды\nT1: BEGIN;\nT1: {sel}  -- {cnt}\nT2: BEGIN;\n"
            f"T2: INSERT INTO {t} (id, {col}) VALUES ({new_id}, {val});\nT2: COMMIT;\n"
            f"T1: {sel}  -- {cnt + 1}\nT1: COMMIT;")


def _skew(rng: random.Random) -> str:
    t, col, role = rng.choice(SKEW_CONTEXTS)
    n1, n2 = rng.sample(NAMES, 2)
    sel = f"SELECT COUNT(*) FROM {t} WHERE {col} = true;"
    return (f"-- правило: хотя бы один {role} должен оставаться {col} = true\nT1: BEGIN;\nT2: BEGIN;\n"
            f"T1: {sel}  -- 2\nT2: {sel}  -- 2\n"
            f"T1: UPDATE {t} SET {col} = false WHERE name = '{n1}';\n"
            f"T2: UPDATE {t} SET {col} = false WHERE name = '{n2}';\n"
            f"T1: COMMIT;\nT2: COMMIT;")


ANOMALY_TEMPLATES = (("lost", _lost), ("nonrep", _nonrep), ("phantom", _phantom), ("skew", _skew))


@family(code="be.db.isolation_anomaly", specialization="backend", area="db", level=5,
        fmt="mcq",
        # нижняя граница по шаблонам: потерянное обновление и неповторяющееся чтение
        # (контекст × id × значение × дельты), фантом (контекст × счётчик × id), перекос (контекст × пара)
        space_size=SHUFFLES * (
            len(VALUE_CONTEXTS) * len(ROW_IDS) * len(BASE_VALUES) * len(DELTAS) * (len(DELTAS) - 1)
            + len(VALUE_CONTEXTS) * len(ROW_IDS) * len(BASE_VALUES) * len(DELTAS)
            + len(PHANTOM_CONTEXTS) * len(PHANTOM_COUNTS) * len(PHANTOM_IDS)
            + len(SKEW_CONTEXTS) * SKEW_PAIRS),
        median_time_s=140)
def isolation_anomaly(rng: random.Random) -> Generated:
    key, make = rng.choice(ANOMALY_TEMPLATES)
    options = list(ANOMALY_OPTIONS.values())
    text = ("Ниже расписание двух параллельных транзакций при уровне изоляции READ COMMITTED. "
            "Первая строка — комментарий о сценарии, дальше шаги идут в порядке выполнения, "
            "а «--» в конце шага отделяет результат запроса. Какая аномалия изоляции в нём показана?")
    correct = ANOMALY_OPTIONS[key]
    return mcq(rng, text, correct, [o for o in options if o != correct],
               code=make(rng), language="sql")


# --- be.db.window_frame_sum ------------------------------------------------------
FRAME_START = datetime.date(2026, 1, 1)
FRAME_DAYS = 60
FRAME_AMOUNTS = tuple(range(20, 200, 5))  # 36; сумма двух >= 40 > 31, не совпадёт с частью даты


@family(code="be.db.window_frame_sum", specialization="backend", area="db", level=5,
        fmt="sql",
        # нижняя граница: даты 7 из 60 × суммы × выбор строки
        space_size=math.comb(FRAME_DAYS, 7) * len(FRAME_AMOUNTS) ** 7,
        median_time_s=130)
def window_frame_sum(rng: random.Random) -> Generated:
    n = rng.randint(7, 10)
    offsets = rng.sample(range(FRAME_DAYS), n)  # уникальные даты с пропусками
    days = [(FRAME_START + datetime.timedelta(days=o)).isoformat() for o in offsets]
    rows = [(d, rng.choice(FRAME_AMOUNTS)) for d in days]
    rng.shuffle(rows)
    t = Table("daily_sales", ("day", "amount"), tuple(rows))
    inner = ("SELECT day,\n"
             "       SUM(amount) OVER (ORDER BY day ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS s\n"
             "FROM daily_sales")
    day = rng.choice(sorted(days)[1:])  # не первая по порядку: у первой нет предыдущей
    ((answer,),) = run_query(setup_sql(t), f"SELECT s FROM (\n{inner}\n) AS q WHERE day = '{day}'")
    return Generated(
        "number",
        Prompt(text=f"Какое значение s вернёт запрос для строки, где day = '{day}'?",
               code=inner + ";", language="sql", tables=(t,), answer_hint="Целое число"),
        answer, ("window_sum", "rows_frame"),
    )
