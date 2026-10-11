"""«Работа с ИИ»: вердикты по SQL-решениям (область sql). Ломающий вход — данные, которые вводит кандидат.

Каталог — план 07a3, задача 6. Запросы — на SQL, общем для SQLite и PostgreSQL; даты — строки 'YYYY-MM-DD'; слова для
поиска — латиницей (LOWER в SQLite без ICU не знает кириллицы). У каждого дефекта — данные-свидетель, на которых эталон
и дефект расходятся: sql_verdict проверяет это при генерации.
"""
import random
from datetime import date, datetime, timedelta

from app.assessment.bank.base import Generated, Table
from app.assessment.bank.families._vocab import NAMES
from app.assessment.bank.verdicts import Mutation, ai_family, sql_verdict

ORDERS = ("id", "customer_id", "amount")


@ai_family(code="ai.sql.distinct_buyers", area="sql", space_size=10**6, median_time_s=60)
def distinct_buyers(rng: random.Random, flawed: bool) -> Generated:
    n = rng.randrange(500, 5001, 100)
    sample = tuple((i, rng.randint(1, 6), rng.randrange(100, 9001, 50)) for i in range(1, rng.randint(5, 8)))
    reference = ("SELECT COUNT(DISTINCT customer_id)\n"
                 "FROM orders\n"
                 f"WHERE amount >= {n}")
    dup = (Table("orders", ORDERS, ((1, 7, n + 100), (2, 7, n + 300))),)  # один клиент — два заказа
    edge = (Table("orders", ORDERS, ((1, 3, n),)),)  # заказ ровно на n
    return sql_verdict(
        rng, flawed,
        text=f"Сколько различных клиентов сделали хотя бы один заказ на сумму не меньше {n} ₽?",
        tables=(Table("orders", ORDERS, sample),),
        reference=reference,
        mutations=(Mutation(1, "SELECT COUNT(customer_id)", witness=dup),
                   Mutation(1, "SELECT COUNT(*)", witness=dup),
                   Mutation(3, f"WHERE amount > {n}", witness=edge)),
        clarify=(f"Считать ли заказ ровно на {n} ₽?", "Считать клиента один раз или по числу заказов?",
                 "Нужно ли вывести имена клиентов?", f"Учитывать ли заказы дешевле {n} ₽?"))


# --- ai.sql.avg_rating_null -----------------------------------------------------------------
REVIEWS = ("id", "product_id", "score")


@ai_family(code="ai.sql.avg_rating_null", area="sql", space_size=10**6, median_time_s=55)
def avg_rating_null(rng: random.Random, flawed: bool) -> Generated:
    p = rng.randint(1, 50)
    sample = tuple((i, rng.choice((p, p, rng.randint(1, 50))), rng.choice((None, 1, 2, 3, 4, 5)))
                   for i in range(1, rng.randint(5, 9)))
    witness = (Table("reviews", REVIEWS, ((1, p, 5), (2, p, None))),)
    return sql_verdict(
        rng, flawed,
        text=f"Какова средняя оценка товара {p}, округлённая до 2 знаков? Отзывы без оценки (score = NULL) не учитываются.",
        tables=(Table("reviews", REVIEWS, sample),),
        reference=f"SELECT ROUND(AVG(score), 2)\nFROM reviews\nWHERE product_id = {p}",
        mutations=(Mutation(1, "SELECT ROUND(AVG(COALESCE(score, 0)), 2)", witness=witness),
                   Mutation(1, "SELECT ROUND(SUM(score) * 1.0 / COUNT(*), 2)", witness=witness)),
        clarify=("Учитывать ли отзывы без оценки?", "Сколько знаков после запятой оставить?",
                 "Для какого товара считать?", "Вернуть одно число или по каждому товару?"))


# --- ai.sql.dept_headcount ------------------------------------------------------------------
DEPARTMENTS = ("Sales", "HR", "IT", "Finance", "Legal", "Support", "Marketing", "Ops", "Design", "Security")


@ai_family(code="ai.sql.dept_headcount", area="sql", space_size=10**6, median_time_s=60)
def dept_headcount(rng: random.Random, flawed: bool) -> Generated:
    names = rng.sample(DEPARTMENTS, rng.randint(3, 5))
    depts = tuple((i + 1, n) for i, n in enumerate(names))
    emps = tuple((j, rng.randint(1, len(names) - 1)) for j in range(1, rng.randint(4, 9)))  # последний отдел пуст
    a, b = rng.sample(DEPARTMENTS, 2)
    witness = (Table("departments", ("id", "name"), ((1, a), (2, b))), Table("employees", ("id", "dept_id"), ((1, 1),)))
    return sql_verdict(
        rng, flawed,
        text=("Сколько сотрудников в каждом отделе? Нужны все отделы, включая отделы без сотрудников (с числом 0); "
              "вывести название отдела и число сотрудников. Названия отделов уникальны."),
        tables=(Table("departments", ("id", "name"), depts), Table("employees", ("id", "dept_id"), emps)),
        reference=("SELECT d.name, COUNT(e.id)\nFROM departments d\nLEFT JOIN employees e ON e.dept_id = d.id\n"
                   "GROUP BY d.name"),
        mutations=(Mutation(3, "JOIN employees e ON e.dept_id = d.id", witness=witness),
                   Mutation(1, "SELECT d.name, COUNT(*)", witness=witness)),
        clarify=("Показывать ли отделы без сотрудников?", "Что вывести для каждого отдела?",
                 "Могут ли у двух отделов совпасть названия?", "Какое число показать для пустого отдела?"))


# --- ai.sql.orders_in_period ----------------------------------------------------------------
@ai_family(code="ai.sql.orders_in_period", area="sql", space_size=365 * 58 * 10**3, median_time_s=55)
def orders_in_period(rng: random.Random, flawed: bool) -> Generated:
    d1 = date(2025, 1, 1) + timedelta(days=rng.randrange(300))
    d2 = d1 + timedelta(days=rng.randint(3, 60))
    sample = tuple((i, (d1 + timedelta(days=rng.randint(-5, (d2 - d1).days + 5))).isoformat())
                   for i in range(1, rng.randint(5, 9)))
    s1, s2 = d1.isoformat(), d2.isoformat()
    return sql_verdict(
        rng, flawed,
        text=f"Сколько заказов создано с {s1} по {s2} включительно? Даты хранятся строками ГГГГ-ММ-ДД.",
        tables=(Table("orders", ("id", "created_at"), sample),),
        reference=f"SELECT COUNT(*)\nFROM orders\nWHERE created_at BETWEEN '{s1}' AND '{s2}'",
        mutations=(Mutation(3, f"WHERE created_at > '{s1}' AND created_at < '{s2}'",
                            witness=(Table("orders", ("id", "created_at"), ((1, s1),)),)),
                   Mutation(3, f"WHERE created_at >= '{s1}' AND created_at < '{s2}'",
                            witness=(Table("orders", ("id", "created_at"), ((1, s2),)),))),
        clarify=(f"Включать ли заказы, созданные {s1}?", f"Включать ли заказы, созданные {s2}?",
                 "В каком формате хранятся даты?", "Вернуть число заказов или сами заказы?"))


# --- ai.sql.big_spenders --------------------------------------------------------------------
@ai_family(code="ai.sql.big_spenders", area="sql", space_size=81 * 10**5, median_time_s=60)
def big_spenders(rng: random.Random, flawed: bool) -> Generated:
    n = rng.randrange(1000, 9001, 100)
    sample = tuple((i, rng.randint(1, 5), rng.randrange(100, n + 1, 50)) for i in range(1, rng.randint(5, 9)))
    half = n // 2 + 1
    return sql_verdict(
        rng, flawed,
        text=f"Какие клиенты (customer_id) потратили в сумме по всем заказам не меньше {n} ₽?",
        tables=(Table("orders", ORDERS, sample),),
        reference=f"SELECT customer_id\nFROM orders\nGROUP BY customer_id\nHAVING SUM(amount) >= {n}",
        mutations=(Mutation(4, f"HAVING SUM(amount) > {n}", witness=(Table("orders", ORDERS, ((1, 5, n),)),)),
                   Mutation(4, f"HAVING MAX(amount) >= {n}",
                            witness=(Table("orders", ORDERS, ((1, 5, half), (2, 5, half))),))),
        clarify=(f"Включать ли клиента с суммой ровно {n} ₽?", "Считать сумму всех заказов или самый крупный заказ?",
                 "Что вывести для каждого клиента?", "Учитывать ли все заказы клиента?"))


# --- ai.sql.customers_without_orders --------------------------------------------------------
@ai_family(code="ai.sql.customers_without_orders", area="sql", space_size=10**6, median_time_s=65)
def customers_without_orders(rng: random.Random, flawed: bool) -> Generated:
    names = rng.sample(NAMES, rng.randint(3, 6))
    customers = tuple((i + 1, n) for i, n in enumerate(names))
    orders = tuple((j, rng.choice((None, *range(1, len(names))))) for j in range(1, rng.randint(3, 7)))
    witness_null = (Table("customers", ("id", "name"), ((1, "A"), (2, "B"))),
                    Table("orders", ("id", "customer_id"), ((1, None),)))
    witness_ne = (Table("customers", ("id", "name"), ((1, "A"), (2, "B"))), Table("orders", ("id", "customer_id"), ((1, 1),)))
    return sql_verdict(
        rng, flawed,
        text=("Какие клиенты (id) не сделали ни одного заказа? В orders бывают заказы без клиента "
              "(customer_id = NULL) — их не относить ни к кому."),
        tables=(Table("customers", ("id", "name"), customers), Table("orders", ("id", "customer_id"), orders)),
        reference=("SELECT c.id\nFROM customers c\n"
                   "WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)"),
        mutations=(Mutation(3, "WHERE c.id NOT IN (SELECT customer_id FROM orders)", witness=witness_null),
                   Mutation(3, "WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id <> c.id)",
                            witness=witness_ne)),
        clarify=("Как быть с заказами без клиента?", "Что вывести — id или имена клиентов?",
                 "Считать ли клиента, у которого есть хотя бы один заказ?", "Откуда брать список клиентов?"))


# --- ai.sql.product_search ------------------------------------------------------------------
WORDS = ("tea", "coffee", "milk", "bread", "juice", "soap", "lamp", "chair", "phone", "cable", "mouse", "book",
         "pen", "bag", "shoe", "cap", "mug", "sock", "wax", "ink")
EXTRA = ("box", "set", "mini", "pro", "pack", "kit", "max", "eco")


@ai_family(code="ai.sql.product_search", area="sql", space_size=len(WORDS) * 10**5, median_time_s=50)
def product_search(rng: random.Random, flawed: bool) -> Generated:
    w = rng.choice(WORDS)
    other = [x for x in WORDS if w not in x and x not in w]

    def name() -> str:
        core = w if rng.random() < 0.5 else rng.choice(other)
        core = rng.choice((core, core.upper(), core.capitalize()))
        return f"{rng.choice(EXTRA).capitalize()} {core} {rng.choice(EXTRA)}"

    sample = tuple((i, name()) for i in range(1, rng.randint(5, 8)))
    return sql_verdict(
        rng, flawed,
        text=f"Какие товары (id) содержат в названии «{w}» в любом регистре (как часть названия)? Названия — латиницей.",
        tables=(Table("products", ("id", "name"), sample),),
        reference=f"SELECT id\nFROM products\nWHERE LOWER(name) LIKE '%{w}%'",
        mutations=(Mutation(3, f"WHERE LOWER(name) = '{w}'",
                            witness=(Table("products", ("id", "name"), ((1, f"Big {w.upper()} pack"),)),)),
                   Mutation(3, f"WHERE LOWER(name) LIKE '{w}%'",
                            witness=(Table("products", ("id", "name"), ((1, f"Iced {w}"),)),))),
        clarify=("Учитывать ли регистр букв?", f"Может ли «{w}» стоять в середине названия?",
                 "На каком языке названия товаров?", "Что вывести для найденных товаров?"))


# --- ai.sql.orders_by_month -----------------------------------------------------------------
@ai_family(code="ai.sql.orders_by_month", area="sql", space_size=10**6, median_time_s=60)
def orders_by_month(rng: random.Random, flawed: bool) -> Generated:
    sample = tuple((i, (date(2023, 1, 1) + timedelta(days=rng.randrange(3 * 365))).isoformat())
                   for i in range(1, rng.randint(5, 9)))
    m = rng.randint(1, 12)
    years = ((1, f"2024-{m:02d}-05"), (2, f"2025-{m:02d}-07"))
    days = ((1, f"2024-{m:02d}-05"), (2, f"2024-{m:02d}-20"))
    return sql_verdict(
        rng, flawed,
        text=("Сколько заказов в каждом месяце за всё время? Вывести месяц в формате ГГГГ-ММ и число заказов; "
              "одинаковые месяцы разных лет — разные строки."),
        tables=(Table("orders", ("id", "created_at"), sample),),
        reference="SELECT substr(created_at, 1, 7) AS month, COUNT(*)\nFROM orders\nGROUP BY month",
        mutations=(Mutation(1, "SELECT substr(created_at, 6, 2) AS month, COUNT(*)",
                            witness=(Table("orders", ("id", "created_at"), years),)),
                   Mutation(3, "GROUP BY created_at", witness=(Table("orders", ("id", "created_at"), days),))),
        clarify=("Разделять ли одинаковые месяцы разных лет?", "В каком формате вывести месяц?",
                 "За какой период считать?", "Что вывести рядом с месяцем?"))


# --- ai.sql.last_login ----------------------------------------------------------------------
LOGINS = ("id", "user_id", "at")


def _at(rng: random.Random) -> str:
    t = datetime(2025, 3, 1) + timedelta(minutes=rng.randrange(60 * 24 * 60))
    return f"{t:%Y-%m-%d %H:%M}"


@ai_family(code="ai.sql.last_login", area="sql", space_size=10**6, median_time_s=55)
def last_login(rng: random.Random, flawed: bool) -> Generated:
    sample = tuple((i, rng.randint(1, 4), _at(rng)) for i in range(1, rng.randint(5, 9)))
    u = rng.randint(1, 99)
    witness = (Table("logins", LOGINS, ((1, u, "2025-03-01 10:00"), (2, u, "2025-03-02 09:00"))),)
    return sql_verdict(
        rng, flawed,
        text=("Когда каждый пользователь входил в последний раз? Вывести user_id и время последнего входа "
              "(строка ГГГГ-ММ-ДД ЧЧ:ММ), по одной строке на пользователя."),
        tables=(Table("logins", LOGINS, sample),),
        reference="SELECT user_id, MAX(at)\nFROM logins\nGROUP BY user_id",
        mutations=(Mutation(1, "SELECT user_id, MIN(at)", witness=witness),
                   Mutation(3, "GROUP BY user_id, at", witness=witness)),
        clarify=("Нужен первый или последний вход?", "Сколько строк вывести на пользователя?",
                 "В каком формате хранится время?", "Что вывести рядом с user_id?"))


# --- ai.sql.paid_revenue --------------------------------------------------------------------
PAYMENTS = ("id", "amount", "status")
STATUSES = ("paid", "pending", "refunded", "failed")


@ai_family(code="ai.sql.paid_revenue", area="sql", space_size=10**6, median_time_s=50)
def paid_revenue(rng: random.Random, flawed: bool) -> Generated:
    sample = tuple((i, rng.randrange(100, 5001, 50), rng.choice(STATUSES)) for i in range(1, rng.randint(5, 9)))
    a = rng.randrange(100, 5001, 50)
    return sql_verdict(
        rng, flawed,
        text="Какова выручка — сумма всех оплаченных платежей (status = 'paid')? Платежи на одинаковую сумму — разные платежи.",
        tables=(Table("payments", PAYMENTS, sample),),
        reference="SELECT SUM(amount)\nFROM payments\nWHERE status = 'paid'",
        mutations=(Mutation(1, "SELECT SUM(DISTINCT amount)",
                            witness=(Table("payments", PAYMENTS, ((1, a, "paid"), (2, a, "paid"))),)),
                   Mutation(3, "WHERE status <> 'refunded'",
                            witness=(Table("payments", PAYMENTS, ((1, a, "paid"), (2, a + 50, "pending"))),))),
        clarify=("Какие платежи считать выручкой?", "Учитывать ли платежи на одинаковую сумму по отдельности?",
                 "Что вернуть — сумму или список платежей?", "Учитывать ли возвраты (refunded)?"))
