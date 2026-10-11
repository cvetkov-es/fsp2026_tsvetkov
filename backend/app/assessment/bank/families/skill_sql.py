"""Навык SQL: области query и model.

Ключ — результат run_query на сгенерированных данных или наш сценарий в отдельной SQLite в памяти (вставки, транзакции:
песочница run_query разрешает только чтение). Диалект — общий для SQLite и PostgreSQL.
"""
import math
import random
import sqlite3

from app.assessment.bank.base import SHUFFLES, Generated, Prompt, Table, family, mcq
from app.assessment.bank.sqlite_sandbox import run_query, setup_sql
from app.assessment.phrases import ru_plural

SPEC = "skill:sql"
PRODUCTS = ("чайник", "лампа", "кресло", "рюкзак", "термос", "наушники", "плед", "зонт", "кружка", "фонарь",
            "блокнот", "коврик", "часы", "сумка", "колонка", "чехол")
CATEGORIES = ("books", "games", "music", "toys", "food", "sport", "garden", "tools")
STORES = ("msk-1", "msk-2", "spb-1", "kzn-1", "ekb-1", "nsk-1")
NAMES = ("Анна", "Борис", "Вера", "Глеб", "Дина", "Егор", "Жанна", "Захар", "Ирина", "Кирилл", "Лада", "Марк",
         "Нина", "Олег", "Полина", "Роман")


def _number(text: str, query: str, tables: tuple[Table, ...], radicals: tuple, hint: str = "Целое число",
            answer=None) -> Generated:
    if answer is None:
        ((answer,),) = run_query(setup_sql(*tables), query)
    return Generated("number", Prompt(text=text, code=query, language="sql", tables=tables, answer_hint=hint),
                     answer, radicals)


def _fraction_ok(x: float, digits: int) -> bool:
    """Значение далеко от границы округления: ответ не зависит от способа округления."""
    return abs((x * 10**digits) % 1 - 0.5) > 0.01


# --- sk.sql.between_inclusive_count ---------------------------------------------------------
PRICES = range(100, 5001, 50)


@family(code="sk.sql.between_inclusive_count", specialization=SPEC, area="query", level=1, fmt="sql",
        # цены 8 строк (нижняя оценка) × выбор границ
        space_size=len(PRICES) ** 8, median_time_s=40)
def between_inclusive_count(rng: random.Random) -> Generated:
    n = rng.randint(8, 14)
    prices = [rng.choice(PRICES) for _ in range(n)]
    a, b = sorted(rng.sample(sorted(set(prices)), 2))  # границы — значения из таблицы: проверяется включение
    names = rng.sample(PRODUCTS, n)
    table = Table("products", ("id", "name", "price"), tuple((i + 1, names[i], p) for i, p in enumerate(prices)))
    query = f"SELECT COUNT(*)\nFROM products\nWHERE price BETWEEN {a} AND {b};"
    return _number("Какое число вернёт запрос?", query, (table,), ("between_inclusive",))


# --- sk.sql.like_pattern_count --------------------------------------------------------------
SURNAMES = (
    "Иванов", "Петров", "Сидоров", "Смирнов", "Кузнецов", "Попов", "Васильев", "Соколов", "Михайлов", "Новиков",
    "Фёдоров", "Морозов", "Волков", "Алексеев", "Лебедев", "Семёнов", "Егоров", "Павлов", "Козлов", "Степанов",
    "Николаев", "Орлов", "Андреев", "Макаров", "Никитин", "Захаров", "Зайцев", "Соловьёв", "Борисов", "Яковлев",
    "Григорьев", "Романов", "Воробьёв", "Сергеев", "Кириллов", "Фролов", "Александров", "Дмитриев", "Королёв",
    "Гусев", "Киселёв", "Ильин", "Максимов", "Поляков", "Сорокин", "Виноградов", "Ковалёв", "Белов", "Медведев",
    "Антонов", "Тарасов", "Жуков", "Баранов", "Филиппов", "Комаров", "Давыдов", "Беляев", "Герасимов", "Богданов",
    "Осипов",
)
FIRST_LETTERS = tuple(sorted({s[0] for s in SURNAMES}))
ENDINGS = ("ов", "ин", "ев", "ёв", "ков", "ров")
SECOND_LETTERS = tuple(sorted({s[1] for s in SURNAMES}))
INNER = ("ов", "ар", "ол", "ер", "ан", "ил", "ор", "ик")


def _like_pattern(rng: random.Random) -> str:
    shape = rng.randrange(4)
    if shape == 0:
        return f"{rng.choice(FIRST_LETTERS)}%"
    if shape == 1:
        return f"%{rng.choice(ENDINGS)}"
    if shape == 2:
        return f"_{rng.choice(SECOND_LETTERS)}%"
    return f"%{rng.choice(INNER)}%"


@family(code="sk.sql.like_pattern_count", specialization=SPEC, area="query", level=1, fmt="sql",
        # набор из 8 фамилий (нижняя оценка) × шаблон
        space_size=math.comb(len(SURNAMES), 8) * 4, median_time_s=45)
def like_pattern_count(rng: random.Random) -> Generated:
    staff = rng.sample(SURNAMES, rng.randint(8, 12))
    table = Table("staff", ("id", "surname"), tuple((i + 1, s) for i, s in enumerate(staff)))
    query = f"SELECT COUNT(*)\nFROM staff\nWHERE surname LIKE '{_like_pattern(rng)}';"
    return _number("Какое число вернёт запрос? В LIKE знак % — любая последовательность символов, _ — ровно один "
                   "символ; регистр букв учитывается.", query, (table,), ("like_pattern",))


# --- sk.sql.sum_by_category -----------------------------------------------------------------
@family(code="sk.sql.sum_by_category", specialization=SPEC, area="query", level=2, fmt="sql",
        space_size=math.comb(len(CATEGORIES), 3) * 491**10, median_time_s=55)
def sum_by_category(rng: random.Random) -> Generated:
    cats = rng.sample(CATEGORIES, rng.randint(3, 4))
    data = [(i + 1, rng.choice(cats), rng.randrange(100, 5001, 10)) for i in range(rng.randint(10, 16))]
    present = sorted({r[1] for r in data})
    cat = rng.choice(present)
    table = Table("sales", ("id", "category", "amount"), tuple(data))
    query = "SELECT category, SUM(amount) AS total\nFROM sales\nGROUP BY category\nORDER BY category;"
    total = dict(run_query(setup_sql(table), query))[cat]
    return _number(f"Какое значение total вернёт запрос для категории «{cat}»?", query, (table,), ("group_by_sum",),
                   answer=total)


# --- sk.sql.join_two_keys_rows --------------------------------------------------------------
DAYS = tuple(f"2026-03-{d:02d}" for d in range(1, 8))


@family(code="sk.sql.join_two_keys_rows", specialization=SPEC, area="query", level=2, fmt="sql",
        space_size=math.comb(len(STORES) * len(DAYS), 4) * 10**4, median_time_s=70)
def join_two_keys_rows(rng: random.Random) -> Generated:
    pairs = [(s, d) for s in STORES for d in DAYS]
    planned = rng.sample(pairs, rng.randint(4, 6))
    facts = []
    for _ in range(rng.randint(5, 8)):
        r = rng.random()
        if r < 0.5:
            s, d = rng.choice(planned)  # совпадает пара — может повториться (кратность)
        elif r < 0.8:
            s = rng.choice(planned)[0]  # тот же магазин, другой день: ловушка «соединил по одному ключу»
            d = rng.choice([x for x in DAYS if (s, x) not in planned] or DAYS)
        else:
            s, d = rng.choice(pairs)
        facts.append((s, d, rng.randrange(10, 1000, 5)))
    plans = Table("plans", ("store", "day", "target"), tuple((s, d, rng.randrange(100, 2000, 50)) for s, d in planned))
    fact_t = Table("facts", ("store", "day", "value"), tuple(facts))
    query = ("SELECT p.store, p.day, p.target, f.value\nFROM plans p\nJOIN facts f\n"
             "  ON p.store = f.store AND p.day = f.day;")
    n = len(run_query(setup_sql(plans, fact_t), query))
    return _number("Сколько строк вернёт запрос?", query, (plans, fact_t), ("join_composite_key",), answer=n)


# --- sk.sql.null_avg ------------------------------------------------------------------------
@family(code="sk.sql.null_avg", specialization=SPEC, area="query", level=2, fmt="sql",
        space_size=191**4 * math.comb(6, 2) * 2, median_time_s=60)
def null_avg(rng: random.Random) -> Generated:
    coalesce = rng.random() < 0.5
    while True:
        n = rng.randint(6, 9)
        nulls = set(rng.sample(range(n), rng.randint(2, 4)))
        amounts = [None if i in nulls else rng.randrange(1000, 20001, 100) for i in range(n)]
        known = [a for a in amounts if a is not None]
        value = sum(known) / (n if coalesce else len(known))
        if _fraction_ok(value, 2):
            break
    table = Table("bonus", ("id", "amount"), tuple((i + 1, a) for i, a in enumerate(amounts)))
    expr = "COALESCE(amount, 0)" if coalesce else "amount"
    query = f"SELECT ROUND(AVG({expr}), 2)\nFROM bonus;"
    return _number("Какое число вернёт запрос?", query, (table,), ("null_in_aggregate",),
                   hint="Число, например 1234.57")


# --- sk.sql.in_subquery_count ---------------------------------------------------------------
@family(code="sk.sql.in_subquery_count", specialization=SPEC, area="query", level=2, fmt="sql",
        space_size=math.comb(len(NAMES), 5) * 100**6, median_time_s=60)
def in_subquery_count(rng: random.Random) -> Generated:
    users = rng.sample(NAMES, rng.randint(5, 8))
    user_t = Table("users", ("id", "name"), tuple((i + 1, u) for i, u in enumerate(users)))
    orders = [(k + 1, rng.randint(1, len(users)), rng.randrange(500, 50001, 500)) for k in range(rng.randint(6, 12))]
    order_t = Table("orders", ("id", "user_id", "total"), tuple(orders))
    x = rng.choice([o[2] for o in orders])  # порог совпадает с суммой заказа: проверяется строгое «больше»
    query = f"SELECT COUNT(*)\nFROM users\nWHERE id IN (\n  SELECT user_id FROM orders WHERE total > {x}\n);"
    return _number("Какое число вернёт запрос?", query, (user_t, order_t), ("in_subquery",))


# --- sk.sql.fk_side_choice ------------------------------------------------------------------
# (одна сторона, её сущность в ед. числе, многие, их сущность в ед. числе, описание связи)
ONE_TO_MANY = (
    ("authors", "author", "books", "book", "у автора может быть много книг, у книги — один автор"),
    ("customers", "customer", "orders", "order", "у клиента много заказов, заказ принадлежит одному клиенту"),
    ("departments", "department", "employees", "employee", "в отделе много сотрудников, сотрудник — в одном отделе"),
    ("courses", "course", "lessons", "lesson", "в курсе много уроков, урок относится к одному курсу"),
    ("projects", "project", "tasks", "task", "в проекте много задач, задача — в одном проекте"),
    ("users", "user", "sessions", "session", "у пользователя много сессий, сессия — одного пользователя"),
    ("teams", "team", "players", "player", "в команде много игроков, игрок — в одной команде"),
    ("warehouses", "warehouse", "shelves", "shelf", "на складе много стеллажей, стеллаж — на одном складе"),
    ("posts", "post", "comments", "comment", "у поста много комментариев, комментарий — к одному посту"),
    ("cities", "city", "stores", "store", "в городе много магазинов, магазин — в одном городе"),
    ("invoices", "invoice", "lines", "line", "в счёте много строк, строка — в одном счёте"),
    ("albums", "album", "tracks", "track", "в альбоме много треков, трек — в одном альбоме"),
)
MAX_ROWS = 999


def _rows(n: int) -> str:
    return f"{n} {ru_plural(n, 'строка', 'строки', 'строк')}"


@family(code="sk.sql.fk_side_choice", specialization=SPEC, area="model", level=3, fmt="mcq",
        space_size=len(ONE_TO_MANY) * (MAX_ROWS - 9) ** 2 * SHUFFLES, median_time_s=50)
def fk_side_choice(rng: random.Random) -> Generated:
    one, one_s, many, many_s, relation = rng.choice(ONE_TO_MANY)
    n_one = rng.randint(10, MAX_ROWS)
    n_many = rng.randint(10, MAX_ROWS)
    text = (f"Таблицы {one} ({_rows(n_one)}) и {many} ({_rows(n_many)}): {relation}. "
            "Как принято хранить связь один-ко-многим?")
    return mcq(rng, text, f"{many}.{one_s}_id → {one}.id", (
        f"{one}.{many_s}_id → {many}.id",
        f"таблица {one}_{many} ({one_s}_id, {many_s}_id)",
        f"{one}.{many_s}_id и {many}.{one_s}_id",
    ))


# --- sk.sql.unique_violations ---------------------------------------------------------------
LOGINS = ("anna", "boris", "vera", "gleb", "dina", "egor", "zhanna", "irina", "kirill", "lada", "mark", "nina")
DOMAINS = ("mail.ru", "yandex.ru", "corp.ru", "example.com")


def _failed_inserts(statements: list[str]) -> int:
    """Наш сценарий в отдельной базе: каждая команда — отдельно (автокоммит), ошибка UNIQUE не прерывает остальные."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE)")
        failed = 0
        for st in statements:
            try:
                conn.execute(st)
            except sqlite3.IntegrityError:
                failed += 1
        return failed
    finally:
        conn.close()


@family(code="sk.sql.unique_violations", specialization=SPEC, area="model", level=3, fmt="sql",
        space_size=(len(LOGINS) * len(DOMAINS)) ** 6, median_time_s=55)
def unique_violations(rng: random.Random) -> Generated:
    pool = [f"{lg}@{d}" for lg in rng.sample(LOGINS, 4) for d in rng.sample(DOMAINS, 2)]  # похожие, но разные адреса
    emails = [rng.choice(pool) for _ in range(rng.randint(6, 9))]
    statements = [f"INSERT INTO users (email) VALUES ('{e}');" for e in emails]
    code = "CREATE TABLE users (\n  id INTEGER PRIMARY KEY,\n  email TEXT UNIQUE\n);\n" + "\n".join(statements)
    return Generated("number", Prompt(
        text="Команды выполняются по одной, каждая в своей транзакции. Сколько вставок завершится ошибкой?",
        code=code, language="sql", answer_hint="Целое число"), _failed_inserts(statements), ("unique_constraint",))


# --- sk.sql.junction_rows -------------------------------------------------------------------
COURSES = ("SQL", "Python", "Docker", "Git", "Linux", "Kafka", "Go", "React", "Java", "Spark")


@family(code="sk.sql.junction_rows", specialization=SPEC, area="model", level=3, fmt="sql",
        space_size=math.comb(len(NAMES), 5) * math.comb(len(COURSES), 3) * 2**10, median_time_s=65)
def junction_rows(rng: random.Random) -> Generated:
    students = rng.sample(NAMES, rng.randint(5, 7))
    courses = rng.sample(COURSES, rng.randint(3, 4))
    pairs = [(s + 1, c + 1) for s in range(len(students)) for c in range(len(courses))]
    enrolled = sorted(rng.sample(pairs, rng.randint(6, min(12, len(pairs)))))
    st = Table("students", ("id", "name"), tuple((i + 1, n) for i, n in enumerate(students)))
    ct = Table("courses", ("id", "title"), tuple((i + 1, t) for i, t in enumerate(courses)))
    et = Table("enrollments", ("student_id", "course_id"), tuple(enrolled))
    title = courses[rng.randrange(len(courses))]
    query = ("SELECT s.name\nFROM students s\nJOIN enrollments e ON e.student_id = s.id\n"
             f"JOIN courses c ON c.id = e.course_id\nWHERE c.title = '{title}';")
    n = len(run_query(setup_sql(st, ct, et), query))
    return _number("Сколько строк вернёт запрос?", query, (st, ct, et), ("many_to_many",), answer=n)


# --- sk.sql.savepoint_value -----------------------------------------------------------------
def _signed(rng: random.Random) -> tuple[str, int]:
    return rng.choice(("+", "-")), rng.randrange(10, 1001, 10)


@family(code="sk.sql.savepoint_value", specialization=SPEC, area="model", level=4, fmt="sql",
        space_size=801 * (2 * 100) ** 3, median_time_s=90)
def savepoint_value(rng: random.Random) -> Generated:
    start = rng.randrange(2000, 10001, 10)
    other = rng.randrange(2000, 10001, 10)
    (s1, a1), (s2, a2), (s3, a3) = _signed(rng), _signed(rng), _signed(rng)
    script = [
        "BEGIN;",
        f"UPDATE account SET balance = balance {s1} {a1} WHERE id = 1;",
        "SAVEPOINT s;",
        f"UPDATE account SET balance = balance {s2} {a2} WHERE id = 1;",
        "ROLLBACK TO SAVEPOINT s;",
        f"UPDATE account SET balance = balance {s3} {a3} WHERE id = 1;",
        "COMMIT;",
    ]
    table = Table("account", ("id", "balance"), ((1, start), (2, other)))
    conn = sqlite3.connect(":memory:", isolation_level=None)  # сценарий сам управляет транзакцией
    try:
        conn.executescript(setup_sql(table) + "\n" + "\n".join(script))
        ((balance,),) = conn.execute("SELECT balance FROM account WHERE id = 1").fetchall()
    finally:
        conn.close()
    return Generated("number", Prompt(text="Каким станет balance счёта с id = 1 после сценария?",
                                      code="\n".join(script), language="sql", tables=(table,),
                                      answer_hint="Целое число"), balance, ("savepoint",))
