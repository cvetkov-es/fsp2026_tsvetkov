"""Семейства Data/Analytics · SQL и модели данных.

Ключ — результат run_query на сгенерированных данных (диалект SQLite, совместимый с PostgreSQL); где важен
порядок строк, ORDER BY идёт по уникальному ключу.
"""
import random

from app.assessment.bank.base import Generated, Prompt, Table, family
from app.assessment.bank.sqlite_sandbox import run_query, setup_sql

EVENT_TYPES = ("view", "click", "purchase", "refund", "signup")
CATEGORIES = ("books", "games", "music", "toys", "food", "sport", "garden")
PAGES = ("/home", "/catalog", "/cart", "/profile", "/help", "/search")


def _sql_number(text: str, query: str, tables: tuple[Table, ...], radicals: tuple, hint: str = "Целое число",
                digits: int | None = None) -> Generated:
    ((value,),) = run_query(setup_sql(*tables), query)
    answer = value if digits is None else round(value, digits)
    return Generated("number", Prompt(text=text, code=query, language="sql", tables=tables, answer_hint=hint),
                     answer, radicals)


def _fraction_ok(x: float, digits: int) -> bool:
    """Значение далеко от границы округления до digits знаков: ответ не зависит от способа округления."""
    frac = (x * 10**digits) % 1
    return abs(frac - 0.5) > 0.01


# --- da.sql.where_count -------------------------------------------------------------
@family(code="da.sql.where_count", specialization="data", area="sql", level=1, fmt="sql", space_size=10**8,
        median_time_s=40)
def where_count(rng: random.Random) -> Generated:
    while True:
        n = rng.randint(8, 12)
        rows = [(i + 1, rng.randint(100, 120), rng.choice(EVENT_TYPES), rng.randrange(0, 501, 10)) for i in range(n)]
        kind = rng.choice([r[2] for r in rows])
        op = rng.choice((">", ">=", "<", "<="))
        t = rng.choice([r[3] for r in rows if r[2] == kind])  # граница совпадает со значением в таблице
        table = Table("events", ("id", "user_id", "type", "amount"), tuple(rows))
        query = f"SELECT COUNT(*)\nFROM events\nWHERE type = '{kind}' AND amount {op} {t};"
        ((count,),) = run_query(setup_sql(table), query)
        if 0 < count < sum(r[2] == kind for r in rows) or rng.random() < 0.2:
            break
    return _sql_number("Какое число вернёт запрос?", query, (table,), ("where_and",))


# --- da.sql.distinct_count -------------------------------------------------------------
@family(code="da.sql.distinct_count", specialization="data", area="sql", level=1, fmt="sql", space_size=10**8,
        median_time_s=40)
def distinct_count(rng: random.Random) -> Generated:
    n = rng.randint(8, 14)
    users = rng.sample(range(100, 1000), rng.randint(3, 7))
    rows = [(i + 1, rng.choice(users), rng.choice(PAGES)) for i in range(n)]
    table = Table("visits", ("id", "user_id", "page"), tuple(rows))
    col = rng.choice(("user_id", "page"))
    query = f"SELECT COUNT(DISTINCT {col})\nFROM visits;"
    return _sql_number("Какое число вернёт запрос?", query, (table,), ("count_distinct",))


# --- da.sql.group_avg_value --------------------------------------------------------------
@family(code="da.sql.group_avg_value", specialization="data", area="sql", level=2, fmt="sql", space_size=10**8,
        median_time_s=55)
def group_avg_value(rng: random.Random) -> Generated:
    while True:
        cats = rng.sample(CATEGORIES, rng.randint(3, 4))
        rows = [(i + 1, rng.choice(cats), rng.randrange(100, 5001, 10)) for i in range(rng.randint(8, 12))]
        counts = {c: sum(r[1] == c for r in rows) for c in cats}
        asked = [c for c, k in counts.items() if k >= 2]
        if not asked:
            continue
        cat = rng.choice(asked)
        mean = sum(r[2] for r in rows if r[1] == cat) / counts[cat]
        if _fraction_ok(mean, 2):
            break
    table = Table("orders", ("id", "category", "amount"), tuple(rows))
    query = ("SELECT category, AVG(amount) AS avg_amount\nFROM orders\nGROUP BY category\nORDER BY category;")
    value = dict(run_query(setup_sql(table), query))[cat]  # строка показанного запроса для этой категории
    return Generated("number", Prompt(text=f"Какое значение avg_amount вернёт запрос для категории «{cat}»? "
                                           "Округлите до двух знаков после запятой.",
                                      code=query, language="sql", tables=(table,),
                                      answer_hint="Число с двумя знаками после запятой, например 1234.57"),
                     round(value, 2), ("group_by_avg",))


NAMES = ("Анна", "Борис", "Вера", "Глеб", "Дина", "Егор", "Жанна", "Захар", "Ирина", "Кирилл", "Лада", "Марк")


# --- da.sql.left_join_count --------------------------------------------------------------
@family(code="da.sql.left_join_count", specialization="data", area="sql", level=2, fmt="sql", space_size=10**8,
        median_time_s=60)
def left_join_count(rng: random.Random) -> Generated:
    n_users = rng.randint(4, 7)
    names = rng.sample(NAMES, n_users)
    users = Table("users", ("id", "name"), tuple((i + 1, names[i]) for i in range(n_users)))
    active = rng.sample(range(1, n_users + 1), rng.randint(2, n_users - 1))  # у остальных сессий нет
    sessions = Table("sessions", ("id", "user_id", "duration_s"),
                     tuple((i + 1, rng.choice(active), rng.randrange(30, 3601, 30)) for i in range(rng.randint(3, 10))))
    query = "SELECT u.name, s.id\nFROM users u\nLEFT JOIN sessions s ON s.user_id = u.id;"
    rows = run_query(setup_sql(users, sessions), query)
    return Generated("number", Prompt(text="Сколько строк вернёт запрос?", code=query, language="sql",
                                      tables=(users, sessions), answer_hint="Целое число"),
                     len(rows), ("left_join_rows",))


# --- da.sql.case_when_count ----------------------------------------------------------------
@family(code="da.sql.case_when_count", specialization="data", area="sql", level=2, fmt="sql", space_size=10**8,
        median_time_s=60)
def case_when_count(rng: random.Random) -> Generated:
    rows = [(i + 1, rng.randint(100, 120), rng.randrange(100, 10001, 100)) for i in range(rng.randint(8, 12))]
    amounts = sorted({r[2] for r in rows})
    lo, hi = sorted(rng.sample(amounts, 2))  # пороги совпадают со значениями в таблице
    table = Table("orders", ("id", "user_id", "amount"), tuple(rows))
    query = (f"SELECT SUM(CASE WHEN amount >= {hi} THEN 1 ELSE 0 END) AS big,\n"
             f"       SUM(CASE WHEN amount < {lo} THEN 1 ELSE 0 END) AS small\nFROM orders;")
    ((big, small),) = run_query(setup_sql(table), query)
    alias, value = rng.choice((("big", big), ("small", small)))
    return Generated("number", Prompt(text=f"Какое значение {alias} вернёт запрос?", code=query, language="sql",
                                      tables=(table,), answer_hint="Целое число"),
                     value, ("case_when_segments",))


# --- da.sql.count_distinct_nulls -------------------------------------------------------------
COUPONS = ("SALE10", "WELCOME", "VIP", "BF2026", "SPRING", "FREESHIP")


@family(code="da.sql.count_distinct_nulls", specialization="data", area="sql", level=3, fmt="sql", space_size=10**8,
        median_time_s=70)
def count_distinct_nulls(rng: random.Random) -> Generated:
    while True:
        codes = rng.sample(COUPONS, rng.randint(2, 4))
        rows = [(i + 1, rng.randint(100, 999), rng.choice((*codes, None, None))) for i in range(rng.randint(8, 12))]
        values = [r[2] for r in rows]
        present = [v for v in values if v is not None]
        if values.count(None) >= 2 and len(present) > len(set(present)):  # и NULL, и повторы
            break
    table = Table("orders", ("id", "user_id", "coupon"), tuple(rows))
    query = "SELECT COUNT(DISTINCT coupon)\nFROM orders;"
    return _sql_number("Какое число вернёт запрос?", query, (table,), ("count_distinct_null",))


# --- da.sql.join_fanout_sum ------------------------------------------------------------------
PRODUCTS = ("book", "mug", "pen", "lamp", "cable", "case", "bag", "card")


@family(code="da.sql.join_fanout_sum", specialization="data", area="sql", level=3, fmt="sql", space_size=10**8,
        median_time_s=80)
def join_fanout_sum(rng: random.Random) -> Generated:
    while True:
        n_orders = rng.randint(3, 5)
        orders = [(i + 1, rng.randint(100, 120), rng.randrange(500, 10001, 100)) for i in range(n_orders)]
        items = [(i + 1, rng.randint(1, n_orders), rng.choice(PRODUCTS)) for i in range(rng.randint(4, 9))]
        per = [sum(it[1] == o[0] for it in items) for o in orders]
        if max(per) >= 2:  # хотя бы один заказ размножается
            break
    t_orders = Table("orders", ("id", "user_id", "amount"), tuple(orders))
    t_items = Table("order_items", ("id", "order_id", "product"), tuple(items))
    query = "SELECT SUM(o.amount)\nFROM orders o\nJOIN order_items i ON i.order_id = o.id;"
    return _sql_number("Аналитик хотел посчитать выручку по заказам, у которых есть позиции. Какое число вернёт "
                       "запрос?", query, (t_orders, t_items), ("join_fanout",))


# --- da.sql.month_group_count -------------------------------------------------------------------
def _date(rng: random.Random, year: int, month: int) -> str:
    days = 30 if month in (4, 6, 9, 11) else 28 if month == 2 else 31
    day = rng.choice((1, 2, days - 1, days, rng.randint(3, days - 2)))  # чаще у границ месяца
    return f"{year}-{month:02d}-{day:02d}"


@family(code="da.sql.month_group_count", specialization="data", area="sql", level=3, fmt="sql", space_size=10**8,
        median_time_s=70)
def month_group_count(rng: random.Random) -> Generated:
    year = rng.randint(2023, 2026)
    first = rng.randint(1, 9)
    months = list(range(first, first + rng.randint(3, 4)))
    rows = [(i + 1, rng.randint(100, 999), _date(rng, year, rng.choice(months))) for i in range(rng.randint(8, 14))]
    table = Table("events", ("id", "user_id", "created_at"), tuple(rows))
    query = ("SELECT substr(created_at, 1, 7) AS month, COUNT(*) AS events\nFROM events\nGROUP BY month\n"
             "ORDER BY month;")
    result = dict(run_query(setup_sql(table), query))
    month = rng.choice(sorted(result))
    text = (f"Какое значение events вернёт запрос для месяца {month}? Выражение substr(created_at, 1, 7) здесь "
            "делает то же, что date_trunc('month', created_at) в PostgreSQL.")
    return Generated("number", Prompt(text=text, code=query, language="sql", tables=(table,), answer_hint="Целое число"),
                     result[month], ("group_by_month",))


# --- da.sql.running_total --------------------------------------------------------------------------
@family(code="da.sql.running_total", specialization="data", area="sql", level=4, fmt="sql", space_size=10**8,
        median_time_s=100)
def running_total(rng: random.Random) -> Generated:
    users = rng.sample(range(100, 1000), rng.randint(2, 3))
    rows = []
    for u in users:
        for day in sorted(rng.sample(range(1, 29), rng.randint(3, 5))):  # даты внутри пользователя уникальны
            rows.append([u, f"2026-{rng.randint(1, 12):02d}-{day:02d}", rng.randrange(100, 5001, 50)])
    rng.shuffle(rows)  # id не совпадает с порядком дат
    table = Table("payments", ("id", "user_id", "paid_at", "amount"),
                  tuple((i + 1, *r) for i, r in enumerate(rows)))
    query = ("SELECT id, user_id, paid_at, amount,\n       SUM(amount) OVER (PARTITION BY user_id ORDER BY paid_at) "
             "AS running\nFROM payments\nORDER BY id;")
    result = {r[0]: r[4] for r in run_query(setup_sql(table), query)}
    target = rng.choice(sorted(result))
    return Generated("number", Prompt(text=f"Какое значение running будет в строке с id = {target}?", code=query,
                                      language="sql", tables=(table,), answer_hint="Целое число"),
                     result[target], ("window_running_sum",))


# --- da.sql.lag_diff ---------------------------------------------------------------------------------
@family(code="da.sql.lag_diff", specialization="data", area="sql", level=4, fmt="sql", space_size=10**8,
        median_time_s=95)
def lag_diff(rng: random.Random) -> Generated:
    month, start = rng.randint(1, 12), rng.randint(1, 18)
    days = [f"2026-{month:02d}-{start + k:02d}" for k in range(rng.randint(6, 9))]
    rows = [[d, rng.randint(50, 500)] for d in days]
    while [r[0] for r in rows] == days:  # строки таблицы не по порядку дат
        rng.shuffle(rows)
    table = Table("daily_metrics", ("id", "day", "value"), tuple((i + 1, *r) for i, r in enumerate(rows)))
    query = ("SELECT day, value,\n       value - LAG(value) OVER (ORDER BY day) AS diff\nFROM daily_metrics\n"
             "ORDER BY day;")
    result = {d: diff for d, _, diff in run_query(setup_sql(table), query)}
    day = rng.choice(days[1:])
    return Generated("number", Prompt(text=f"Какое значение diff вернёт запрос для дня {day}?", code=query,
                                      language="sql", tables=(table,), answer_hint="Целое число (может быть отрицательным)"),
                     result[day], ("window_lag",))


# --- da.sql.dedupe_row_number ------------------------------------------------------------------------
STATUSES = ("active", "paused", "cancelled")


@family(code="da.sql.dedupe_row_number", specialization="data", area="sql", level=4, fmt="sql", space_size=10**8,
        median_time_s=110)
def dedupe_row_number(rng: random.Random) -> Generated:
    status = rng.choice(STATUSES)
    query = ("WITH ranked AS (\n  SELECT account_id, status,\n         ROW_NUMBER() OVER (PARTITION BY account_id "
             "ORDER BY updated_at DESC) AS rn\n  FROM subscriptions\n)\nSELECT COUNT(*)\nFROM ranked\n"
             f"WHERE rn = 1 AND status = '{status}';")
    while True:
        accounts = rng.sample(range(100, 1000), rng.randint(3, 6))
        rows = []
        for a in accounts:
            for ts in rng.sample(range(1, 29), rng.randint(1, 4)):  # моменты внутри аккаунта уникальны
                rows.append([a, rng.choice(STATUSES), f"2026-05-{ts:02d} {rng.randint(8, 20):02d}:00"])
        rng.shuffle(rows)
        table = Table("subscriptions", ("id", "account_id", "status", "updated_at"),
                      tuple((i + 1, *r) for i, r in enumerate(rows)))
        ((count,),) = run_query(setup_sql(table), query)
        naive_rows = sum(r[1] == status for r in rows)
        naive_any = len({r[0] for r in rows if r[1] == status})
        # ключ 0 оставляем редким (≈10%): иначе «0» угадывается в четверти заданий
        if count not in (naive_rows, naive_any) and len(rows) <= 14 and (count > 0 or rng.random() < 0.3):
            break
    return Generated("number", Prompt(text="Сколько аккаунтов насчитает запрос?", code=query, language="sql",
                                      tables=(table,), answer_hint="Целое число"),
                     count, ("row_number_latest",))


# --- da.sql.range_vs_rows ---------------------------------------------------------------------------------
@family(code="da.sql.range_vs_rows", specialization="data", area="sql", level=5, fmt="sql", space_size=10**8,
        median_time_s=140)
def range_vs_rows(rng: random.Random) -> Generated:
    month = rng.randint(1, 12)
    days = sorted(rng.sample(range(1, 29), rng.randint(3, 5)))
    rows = [[f"2026-{month:02d}-{d:02d}", rng.randrange(100, 2001, 50)] for d in days]
    tied = rng.sample(range(len(days)), rng.randint(1, 2))
    for k in tied:  # намеренно равные даты: у строки есть peers
        rows += [[rows[k][0], rng.randrange(100, 2001, 50)] for _ in range(rng.randint(1, 2))]
    rng.shuffle(rows)
    table = Table("sales", ("id", "day", "amount"), tuple((i + 1, *r) for i, r in enumerate(rows)))
    query = ("SELECT id, day, amount,\n       SUM(amount) OVER (ORDER BY day\n"
             "                         RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum\n"
             "FROM sales\nORDER BY id;")
    result = {r[0]: r[3] for r in run_query(setup_sql(table), query)}
    tied_days = {rows[i][0] for i in range(len(rows)) if sum(r[0] == rows[i][0] for r in rows) >= 2}
    # спрашиваем строку из группы равных дат, но не последнюю по id — ROWS по id дал бы другое значение
    candidates = [i + 1 for i, r in enumerate(rows) if r[0] in tied_days
                  and any(j > i and rows[j][0] == r[0] for j in range(len(rows)))]
    target = rng.choice(candidates)
    return Generated("number", Prompt(text=f"Какое значение cum будет в строке с id = {target}?", code=query,
                                      language="sql", tables=(table,), answer_hint="Целое число"),
                     result[target], ("window_range_peers",))


# --- da.sql.cohort_retention ---------------------------------------------------------------------------------
COHORT_QUERY = """WITH cohort AS (
  SELECT id, substr(signup_date, 1, 7) AS cohort_month
  FROM users
),
next_month_active AS (
  SELECT DISTINCT c.id
  FROM cohort c
  JOIN activity a ON a.user_id = c.id
  WHERE substr(a.active_date, 1, 7) = strftime('%Y-%m', c.cohort_month || '-01', '+1 month')
)
SELECT c.cohort_month,
       ROUND(100.0 * COUNT(n.id) / COUNT(c.id), 1) AS retention_pct
FROM cohort c
LEFT JOIN next_month_active n ON n.id = c.id
GROUP BY c.cohort_month
ORDER BY c.cohort_month;"""


def _month(year: int, month: int, rng: random.Random, min_day: int = 1) -> str:
    y, m = year + (month - 1) // 12, (month - 1) % 12 + 1
    return f"{y}-{m:02d}-{rng.randint(min_day, 28):02d}"


@family(code="da.sql.cohort_retention", specialization="data", area="sql", level=5, fmt="sql", space_size=10**8,
        median_time_s=150)
def cohort_retention(rng: random.Random) -> Generated:
    year, first = 2026, rng.randint(1, 10)
    while True:
        users = [(i + 1, _month(year, first + rng.randint(0, 1), rng)) for i in range(rng.randint(6, 10))]
        activity = []
        for uid, signup in users:
            m0 = int(signup[5:7]) + 12 * (int(signup[:4]) - year)
            for _ in range(rng.randint(0, 3)):  # активность в том же месяце, в следующем или через месяц
                shift = rng.choice((0, 1, 1, 2))
                # в месяц регистрации — не раньше дня регистрации
                activity.append((uid, _month(year, m0 + shift, rng, int(signup[8:]) if shift == 0 else 1)))
        rng.shuffle(activity)
        t_users = Table("users", ("id", "signup_date"), tuple(users))
        t_act = Table("activity", ("user_id", "active_date"), tuple(activity))
        result = dict(run_query(setup_sql(t_users, t_act), COHORT_QUERY))
        month = rng.choice(sorted(result))
        value = result[month]
        if 0 < value < 100 and len(activity) <= 18:
            break
    text = (f"Какое значение retention_pct вернёт запрос для когорты {month}? strftime(…, '+1 month') даёт "
            "следующий месяц в формате ГГГГ-ММ (в PostgreSQL — to_char(дата + interval '1 month', 'YYYY-MM')).")
    return Generated("number", Prompt(text=text, code=COHORT_QUERY, language="sql", tables=(t_users, t_act),
                                      answer_hint="Число с одним знаком после запятой, например 33.3"),
                     value, ("cohort_next_month",))
