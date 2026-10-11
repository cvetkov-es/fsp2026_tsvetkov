"""Семейства Data/Analytics · качество данных и пайплайны."""
import datetime
import random
from collections import Counter

from app.assessment.bank.base import Generated, Prompt, Table, family, mcq
from app.assessment.bank.sqlite_sandbox import run_query, setup_sql

SOURCES = ("crm", "shop", "app", "billing", "erp")


def _far(x: float, digits: int) -> bool:
    return abs((x * 10**digits) % 1 - 0.5) > 0.01


# --- da.quality.duplicate_keys -------------------------------------------------------------
@family(code="da.quality.duplicate_keys", specialization="data", area="quality", level=1, fmt="sql",
        space_size=10**8, median_time_s=40)
def duplicate_keys(rng: random.Random) -> Generated:
    key = rng.choice(("order_id", "external_id"))
    while True:
        ids = rng.sample(range(1000, 9999), rng.randint(5, 9))
        rows = [(i + 1, rng.choice(ids), rng.choice(SOURCES), rng.randrange(100, 5001, 50))
                for i in range(rng.randint(8, 13))]
        counts = Counter(r[1] for r in rows)
        if any(c > 1 for c in counts.values()):
            break
    table = Table("raw_orders", ("row_id", key, "source", "amount"), tuple(rows))
    if rng.random() < 0.5:
        query = (f"SELECT COUNT(*)\nFROM (\n  SELECT {key}\n  FROM raw_orders\n  GROUP BY {key}\n"
                 "  HAVING COUNT(*) > 1\n) t;")
    else:
        query = f"SELECT COUNT(*) - COUNT(DISTINCT {key})\nFROM raw_orders;"
    ((value,),) = run_query(setup_sql(table), query)
    return Generated("number", Prompt(text="Какое число вернёт запрос?", code=query, language="sql", tables=(table,),
                                      answer_hint="Целое число"), value, ("duplicate_keys",))


# --- da.quality.null_share ---------------------------------------------------------------------
NULL_COLUMNS = ("email", "phone", "city", "birth_date", "referrer")


@family(code="da.quality.null_share", specialization="data", area="quality", level=1, fmt="calc",
        space_size=10**8, median_time_s=40)
def null_share(rng: random.Random) -> Generated:
    col = rng.choice(NULL_COLUMNS)
    while True:
        n = rng.randint(6, 14)
        nulls = rng.randint(1, n - 1)
        share = nulls / n * 100
        if _far(share, 1):
            break
    flags = [True] * nulls + [False] * (n - nulls)
    rng.shuffle(flags)
    rows = tuple((i + 1, None if f else f"{col[:2]}{rng.randint(100, 999)}", rng.choice(SOURCES))
                 for i, f in enumerate(flags))
    table = Table("customers", ("id", col, "source"), rows)
    text = f"Какова доля пропусков (NULL) в колонке {col}, %?"
    return Generated("number", Prompt(text=text, tables=(table,), answer_hint="Процент с одним знаком после запятой"),
                     round(share, 1), ("null_share",))


# --- da.quality.orphans --------------------------------------------------------------------------
@family(code="da.quality.orphans", specialization="data", area="quality", level=2, fmt="sql",
        space_size=10**8, median_time_s=55)
def orphans(rng: random.Random) -> Generated:
    parent_name, child_name, fk = rng.choice((("customers", "orders", "customer_id"), ("products", "order_items",
                                                                                         "product_id"),
                                              ("accounts", "payments", "account_id")))
    while True:
        ids = sorted(rng.sample(range(1, 60), rng.randint(4, 7)))
        pool = ids + rng.sample([x for x in range(1, 60) if x not in ids], 3)  # часть ссылок — на удалённых
        children = [(i + 1, rng.choice(pool), rng.randrange(100, 5001, 50)) for i in range(rng.randint(6, 12))]
        if any(c[1] not in ids for c in children):
            break
    parents = Table(parent_name, ("id", "name"), tuple((i, f"{parent_name[:-1]}_{i}") for i in ids))
    child = Table(child_name, ("id", fk, "amount"), tuple(children))
    query = (f"SELECT COUNT(*)\nFROM {child_name} c\nLEFT JOIN {parent_name} p ON p.id = c.{fk}\nWHERE p.id IS NULL;")
    ((value,),) = run_query(setup_sql(parents, child), query)
    return Generated("number", Prompt(text="Сколько «осиротевших» записей найдёт запрос?", code=query, language="sql",
                                      tables=(parents, child), answer_hint="Целое число"), value, ("orphans",))


# --- da.quality.iqr_outliers ----------------------------------------------------------------------
def _percentile_linear(xs: list[int], q: float) -> float:
    """Перцентиль с линейной интерполяцией (как numpy.percentile по умолчанию): позиция (n − 1)·q."""
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


IQR_CONTEXTS = ("время ответа API, мс", "сумма заказа, руб.", "длительность сессии, с", "вес посылки, г",
                "число товаров в заказе")


@family(code="da.quality.iqr_outliers", specialization="data", area="quality", level=2, fmt="calc",
        space_size=len(IQR_CONTEXTS) * 61**9, median_time_s=60)
def iqr_outliers(rng: random.Random) -> Generated:
    while True:
        xs = [rng.randint(40, 100) for _ in range(rng.randint(8, 12))]
        xs += [rng.choice((rng.randint(150, 400), rng.randint(0, 10))) for _ in range(rng.randint(1, 3))]
        rng.shuffle(xs)
        q1, q3 = _percentile_linear(xs, 0.25), _percentile_linear(xs, 0.75)
        lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        count = sum(x < lo or x > hi for x in xs)
        if count >= 1 and all(abs(x - lo) > 0.5 and abs(x - hi) > 0.5 for x in xs):
            break
    context = rng.choice(IQR_CONTEXTS)
    text = (f"{context[0].upper() + context[1:]}: значения в коде. Сколько значений — выбросы по правилу 1.5·IQR "
            "(меньше Q1 − 1.5·IQR или больше Q3 + 1.5·IQR)? Квартили считайте линейной интерполяцией, как "
            "numpy.percentile по умолчанию: позиция (n − 1)·q в отсортированном ряду.")
    return Generated("number", Prompt(text=text, code=f"values = [{', '.join(map(str, xs))}]", language="python",
                                      answer_hint="Целое число"), count, ("iqr_outliers",))


# --- da.quality.type_coercion -------------------------------------------------------------------------
COERCION_CODES = {  # выражение → исход (pandas 2.x и новее)
    "pd.to_numeric(s, errors='coerce')": "float_nan",
    "s.astype(int)": "error",
    "pd.to_numeric(s, errors='coerce').astype('Int64')": "int64_na",
}
COERCION_OPTIONS = {
    "float_nan": "Тип float64, а значение-заглушка превратится в NaN",
    "error": "Ошибка ValueError: заглушку нельзя привести к числу",
    "int64_na": "Int64 с поддержкой пропусков, на месте заглушки <NA>",
    "zero": "int64, а значение-заглушка превратится в ноль (0)",
    "object": "Тип останется object, а значения — прежними строками",
}
MISSING_MARKERS = ("n/a", "-", "unknown", "нет данных")


@family(code="da.quality.type_coercion", specialization="data", area="quality", level=2, fmt="mcq",
        space_size=len(COERCION_CODES) * len(MISSING_MARKERS) * 99**3 * 4 * 24, median_time_s=55)
def type_coercion(rng: random.Random) -> Generated:
    expr = rng.choice(sorted(COERCION_CODES))
    outcome = COERCION_CODES[expr]
    marker = rng.choice(MISSING_MARKERS)
    values = [str(rng.randint(1, 99)) for _ in range(3)]
    values.insert(rng.randint(0, 3), marker)
    code = f"s = pd.Series({values})\nresult = {expr}"
    text = (f"Колонка количества пришла из CSV строками, пропуски обозначены как «{marker}». Каким будет результат "
            "(pandas 2.x и новее)?")
    wrong = rng.sample([v for k, v in COERCION_OPTIONS.items() if k != outcome], 3)
    return mcq(rng, text, COERCION_OPTIONS[outcome], wrong, code=code, language="python")


# --- da.quality.idempotent_load -------------------------------------------------------------------------
LOAD_TABLES = (("fact_sales", "stg_sales"), ("fact_orders", "stg_orders"), ("fact_events", "stg_events"),
               ("fact_payments", "stg_payments"))
IDEMPOTENT_CORRECT = (
    "Сделать загрузку идемпотентной: перезапись партиции дня (DELETE + INSERT) или MERGE по ключу",
    "Повторный запуск должен давать тот же результат: INSERT OVERWRITE партиции или UPSERT по ключу",
)
IDEMPOTENT_WRONG = (
    "Запускать задачу реже — раз в неделю: тогда повторных запусков станет меньше, и дублей тоже",
    "Добавить DISTINCT во все отчёты поверх этой таблицы, а саму загрузку оставить без изменений",
    "Добавить в таблицу автоинкрементный id: тогда каждая строка станет уникальной и дублей не будет",
    "Включить автоматические ретраи с экспоненциальной задержкой при каждом падении этой задачи",
)


@family(code="da.quality.idempotent_load", specialization="data", area="quality", level=3, fmt="mcq",
        space_size=len(LOAD_TABLES) * 3 * 24 * len(IDEMPOTENT_CORRECT) * 4 * 24 * 4, median_time_s=70)
def idempotent_load(rng: random.Random) -> Generated:
    fact, stg = rng.choice(LOAD_TABLES)
    hour = rng.randint(0, 23)
    code = "\n".join([f"-- ежедневно в {hour:02d}:00, параметр :day — дата загрузки",
                      f"INSERT INTO {fact}", "SELECT *", f"FROM {stg}", "WHERE day = :day;"])
    text = (f"Ежедневная загрузка в {fact} (код ниже) иногда падает и перезапускается вручную, а иногда оркестратор "
            f"сам повторяет её {rng.choice(('дважды', 'трижды', 'несколько раз'))}. После повторов в отчётах появляются "
            "дубли. Как правильно исправить?")
    return mcq(rng, text, rng.choice(IDEMPOTENT_CORRECT), rng.sample(IDEMPOTENT_WRONG, 3), code=code, language="sql")


# --- da.quality.late_data ----------------------------------------------------------------------------------------
LATE_SOURCES = ("мобильное приложение", "умные счётчики", "кассы магазинов", "IoT-датчики склада")
LATE_METRICS = ("число заказов", "выручка", "активные устройства", "число событий")
LATE_CORRECT = (
    "Пересчитывать последние дни с окном не меньше максимальной задержки или ждать watermark",
    "Считать день окончательным только после допустимой задержки, а до этого пересчитывать окно",
)
LATE_WRONG = (
    "Отбрасывать опоздавшие события: они приходят позже расчёта и только искажают статистику",
    "Группировать по времени поступления события в хранилище, а не по времени самого события",
    "Пересчитывать агрегат каждый час, но по-прежнему только за последний закрытый день, без расширения окна",
    "Перенести ежедневный расчёт на полночь по UTC, чтобы все опоздавшие события точно успели прийти",
)


@family(code="da.quality.late_data", specialization="data", area="quality", level=3, fmt="mcq",
        space_size=len(LATE_SOURCES) * len(LATE_METRICS) * 2 * 6 * 4 * len(LATE_CORRECT) * 4 * 24, median_time_s=70)
def late_data(rng: random.Random) -> Generated:
    source = rng.choice(LATE_SOURCES)
    delay, hour = rng.choice((48, 72)), rng.randint(0, 5)  # при 24 ч «ежечасный пересчёт дня» почти верен
    text = (f"Источник «{source}» иногда присылает события с опозданием до {delay} ч (устройства без сети). "
            f"Дневной агрегат «{rng.choice(LATE_METRICS)}» за вчера считается в {hour:02d}:{rng.choice((0, 15, 30, 45)):02d} "
            "и больше не пересчитывается, поэтому цифры за "
            "последние дни занижены. Как исправить?")
    return mcq(rng, text, rng.choice(LATE_CORRECT), rng.sample(LATE_WRONG, 3))


# --- da.quality.scd2_rows --------------------------------------------------------------------------------------------
SCD_CITIES = ("Казань", "Пермь", "Томск", "Самара", "Омск")
SCD_SEGMENTS = ("mass", "premium", "vip")


@family(code="da.quality.scd2_rows", specialization="data", area="quality", level=3, fmt="calc",
        space_size=10**9, median_time_s=90)
def scd2_rows(rng: random.Random) -> Generated:
    while True:
        m = rng.randint(3, 5)
        customers = [[i + 1, rng.choice(SCD_CITIES), rng.choice(SCD_SEGMENTS), f"2026-01-{rng.randint(1, 28):02d}"]
                     for i in range(m)]
        current = {c[0]: {"city": c[1], "segment": c[2], "last_login": c[3]} for c in customers}
        log, rows, skipped = [], m, 0
        for k in range(rng.randint(4, 8)):
            cid = rng.randint(1, m)
            attr = rng.choice(("city", "city", "segment", "segment", "last_login"))
            if attr == "last_login":
                value = f"2026-02-{k + 1:02d}"
                skipped += 1  # не версионируется: перезапись без новой строки
            else:
                pool = SCD_CITIES if attr == "city" else SCD_SEGMENTS
                value = current[cid][attr] if rng.random() < 0.25 else rng.choice(pool)
                if value == current[cid][attr]:
                    skipped += 1  # значение то же — новой версии нет
                else:
                    rows += 1
            current[cid][attr] = value
            log.append((f"2026-02-{k + 1:02d}", cid, attr, value))
        if skipped >= 1:
            break
    initial = Table("dim_customer", ("id", "city", "segment", "last_login"), tuple(tuple(c) for c in customers))
    changes = Table("changes", ("changed_at", "customer_id", "attribute", "new_value"), tuple(log))
    text = ("Измерение dim_customer ведётся как SCD Type 2 по атрибутам city и segment: каждое изменение их значения "
            "добавляет новую версию строки; last_login перезаписывается без новой версии. Изначально у каждого "
            "клиента одна строка (первая таблица). Сколько строк будет в dim_customer после применения журнала "
            "изменений (вторая таблица)?")
    return Generated("number", Prompt(text=text, tables=(initial, changes), answer_hint="Целое число"), rows,
                     ("scd2_versions",))


# --- da.quality.dag_order -----------------------------------------------------------------------------------------------
PIPELINES = (
    ("extract_orders", "clean_orders", "join_customers", "build_sales_mart", "validate_mart", "publish_dashboard"),
    ("load_events", "dedupe_events", "sessionize", "build_funnel", "check_counts", "export_report"),
    ("pull_payments", "convert_currency", "match_invoices", "build_ledger", "reconcile", "notify_finance"),
)


@family(code="da.quality.dag_order", specialization="data", area="quality", level=4, fmt="calc",
        # конвейер × длина × лишние транзитивные рёбра × порядок строк зависимостей × порядок показа шагов
        space_size=len(PIPELINES) * 2 * 10 * 120 * 119, median_time_s=90)
def dag_order(rng: random.Random) -> Generated:
    tasks = list(rng.choice(PIPELINES)[:rng.randint(5, 6)])
    edges = [(tasks[i + 1], tasks[i]) for i in range(len(tasks) - 1)]  # цепочка: порядок единственный
    extra = [(tasks[j], tasks[i]) for i in range(len(tasks)) for j in range(i + 2, len(tasks))]
    edges += rng.sample(extra, rng.randint(1, 3))  # транзитивные зависимости не меняют порядок
    rng.shuffle(edges)
    order = list(range(len(tasks)))
    while order == sorted(order):
        rng.shuffle(order)
    shown = tuple(tasks[i] for i in order)
    answer = tuple(shown.index(t) + 1 for t in tasks)
    code = "\n".join(f"{t} зависит от {d}" for t, d in edges)
    text = ("Зависимости задач DAG перечислены в коде. Задачи выполняются по одной. В каком порядке их можно "
            "выполнить? (Порядок единственный.)")
    return Generated("order", Prompt(text=text, code=code, language="text", steps=shown,
                                     answer_hint="Номера всех шагов через пробел, например: 2 1 3 …"),
                     answer, ("dag_topological_order",))


# --- da.quality.partition_pruning ------------------------------------------------------------------------------------
PRUNE_TABLES = (("events", "event_date", "event_ts"), ("orders", "order_date", "created_at"),
                ("logs", "log_date", "logged_at"), ("payments", "pay_date", "paid_at"))
PRUNE_AGGREGATES = {  # агрегат по колонкам, которые у таблицы действительно есть
    "events": ("COUNT(*)", "COUNT(DISTINCT user_id)"), "orders": ("COUNT(*)", "SUM(amount)"),
    "logs": ("COUNT(*)", "COUNT(DISTINCT host)"), "payments": ("SUM(amount)", "COUNT(DISTINCT user_id)"),
}


def _prune_options(col: str, ts: str, day: str, nxt: str, d: int) -> tuple[list[str], list[str]]:
    good = [f"{col} = DATE '{day}'", f"{col} BETWEEN DATE '{day}' AND DATE '{day}'", f"{col} IN (DATE '{day}')"]
    bad = [f"CAST({col} AS VARCHAR) = '{day}'", f"date_trunc('day', {ts}) = DATE '{day}'",
           f"{col} + INTERVAL '1' DAY = DATE '{nxt}'", f"EXTRACT(DAY FROM {col}) = {d}",
           f"to_char({col}, 'YYYY-MM-DD') = '{day}'", f"DATE({ts}) BETWEEN DATE '{day}' AND DATE '{day}'"]
    return good, bad


@family(code="da.quality.partition_pruning", specialization="data", area="quality", level=4, fmt="mcq",
        space_size=len(PRUNE_TABLES) * 365 * 3 * 2 * 20 * 24, median_time_s=90)
def partition_pruning(rng: random.Random) -> Generated:
    table, col, ts = rng.choice(PRUNE_TABLES)
    date = datetime.date(2026, 1, 1) + datetime.timedelta(days=rng.randrange(365))
    day, nxt = date.isoformat(), (date + datetime.timedelta(days=1)).isoformat()
    good, bad = _prune_options(col, ts, day, nxt, date.day)
    agg = rng.choice(PRUNE_AGGREGATES[table])
    while True:  # два равносильных преобразования колонки не встречаются вместе (урок 11)
        wrong = rng.sample(bad, 3)
        if sum(w.startswith(("CAST(", "to_char(")) for w in wrong) <= 1:
            break
    queries = [f"SELECT {agg} FROM {table} WHERE {c};" for c in [rng.choice(good), *wrong]]
    text = (f"Таблица {table} партиционирована по колонке {col} (тип DATE, одна партиция на день); {ts} — точное "
            f"время события. Какой запрос движок гарантированно выполнит, прочитав только партицию за {day}?")
    return mcq(rng, text, queries[0], queries[1:], radicals=("partition_pruning", 4))


# --- da.quality.backfill_order -----------------------------------------------------------------------------------------
BACKFILL_STEPS = (  # загрузки останавливаются до пересчёта: иначе он читает и подменяет «движущиеся» данные
    ("Приостановить инкрементальные загрузки, пишущие в {mart}", "Приостановить задачи ETL, которые пишут в {mart}"),
    ("Пересчитать партиции {mart} за {period} во временную таблицу", "Пересчитать данные {mart} за {period} в отдельной таблице"),
    ("Сверить число строк и контрольные суммы пересчитанных партиций", "Сверить контрольные суммы новых партиций с источником"),
    ("Атомарно подменить партиции {mart} пересчитанными", "Одной операцией подменить старые партиции {mart} новыми"),
    ("Возобновить загрузки и сообщить пользователям витрины", "Возобновить задачи ETL, пишущие в {mart}"),
)
BACKFILL_MARTS = ("mart_sales", "mart_retention", "mart_finance", "mart_marketing", "mart_logistics")
BACKFILL_PERIODS = ("март", "второй квартал", "последние 90 дней", "2025 год", "январь–февраль", "прошлую неделю")


@family(code="da.quality.backfill_order", specialization="data", area="quality", level=4, fmt="order",
        space_size=len(BACKFILL_MARTS) * len(BACKFILL_PERIODS) * 2**5 * 119, median_time_s=90)
def backfill_order(rng: random.Random) -> Generated:
    mart, period = rng.choice(BACKFILL_MARTS), rng.choice(BACKFILL_PERIODS)
    steps = [rng.choice(v).format(mart=mart, period=period) for v in BACKFILL_STEPS]
    order = list(range(5))
    while order == sorted(order):
        rng.shuffle(order)
    shown = tuple(steps[i] for i in order)
    answer = tuple(order.index(i) + 1 for i in range(5))
    text = (f"В витрине {mart} нашли ошибку расчёта за {period}. Нужно сделать backfill так, чтобы пересчёт не "
            "конфликтовал со свежими загрузками, а потребители не увидели ни частично пересчитанных, ни непроверенных "
            "данных. Расположите шаги в правильном порядке.")
    return Generated("order", Prompt(text=text, steps=shown, answer_hint="Номера всех шагов через пробел, например: 2 1 3 …"),
                     answer, ("safe_backfill", 5))


# --- da.quality.exactly_once_sink ----------------------------------------------------------------------------------------
EO_TOPICS = ("orders", "payments", "clicks", "shipments", "invoices")
EO_SINKS = (("PostgreSQL", "PostgreSQL"), ("хранилище", "хранилище"), ("таблицу фактов", "таблице фактов"),
            ("витрину", "витрине"))  # (куда пишет — винительный, где дубли — предложный)
EXACTLY_ONCE_CORRECT = (
    "Писать идемпотентно (upsert по ключу) и фиксировать offset в той же транзакции, что и запись",
    "Хранить offset в самом приёмнике и обновлять его атомарно вместе с данными; запись — upsert",
)
EXACTLY_ONCE_WRONG = (
    "Коммитить offset сразу после чтения, до обработки, — тогда сообщение точно не обработается дважды",
    "Увеличить число ретраев продюсера и таймаут подтверждения, чтобы ни одно сообщение не терялось",
    "Обрабатывать все сообщения в одном потоке: без параллелизма дублей при перезапуске не будет",
    "Включить сжатие сообщений в топике, чтобы консьюмер успевал обработать всё до перезапуска",
)


@family(code="da.quality.exactly_once_sink", specialization="data", area="quality", level=5, fmt="mcq",
        space_size=len(EO_TOPICS) * len(EO_SINKS) * 3 * 6 * len(EXACTLY_ONCE_CORRECT) * 4 * 24, median_time_s=120)
def exactly_once_sink(rng: random.Random) -> Generated:
    topic, (sink, sink_where) = rng.choice(EO_TOPICS), rng.choice(EO_SINKS)
    every = rng.choice((100, 500, 1000, 5000, 10_000, 50_000))
    text = (f"Консьюмер читает топик {topic} и пишет результат в {sink}; offset коммитится автоматически каждые "
            f"{every} мс {rng.choice(('после записи', 'в фоне', 'по таймеру'))}. После падений и перезапусков в "
            f"{sink_where} появляются дубли. Как получить эффект exactly-once на стороне приёмника?")
    return mcq(rng, text, rng.choice(EXACTLY_ONCE_CORRECT), rng.sample(EXACTLY_ONCE_WRONG, 3))


# --- da.quality.contract_breaking ---------------------------------------------------------------------------------------------
CONTRACT_ENTITIES = (
    ("orders", (("order_id", "bigint"), ("customer_id", "int"), ("amount", "numeric"), ("status", "varchar"),
                ("created_at", "timestamp"))),
    ("users", (("user_id", "bigint"), ("age", "smallint"), ("email", "varchar"), ("city", "varchar"),
               ("signup_at", "timestamp"))),
    ("events", (("event_id", "bigint"), ("session_id", "int"), ("name", "varchar"), ("value", "real"),
                ("ts", "timestamp"))),
)
INCOMPATIBLE = {"bigint": "varchar", "int": "varchar", "smallint": "varchar", "numeric": "int", "varchar": "int",
                "timestamp": "varchar", "real": "int"}
RENAMES = {"order_id": "id", "customer_id": "client_id", "amount": "total", "status": "state", "created_at": "created",
           "user_id": "id", "age": "years", "email": "mail", "city": "town", "signup_at": "registered_at",
           "event_id": "id", "session_id": "sid", "name": "event_name", "value": "val", "ts": "event_time"}
NEW_FIELDS = ("source", "channel", "comment", "region", "tags")


@family(code="da.quality.contract_breaking", specialization="data", area="quality", level=5, fmt="mcq",
        # набор × вид поломки × поле × новое поле × поле комментария × версия (4 × 21) × порядок вариантов
        space_size=len(CONTRACT_ENTITIES) * 3 * 5 * len(NEW_FIELDS) * 5 * 84 * 24, median_time_s=120)
def contract_breaking(rng: random.Random) -> Generated:
    table, fields = rng.choice(CONTRACT_ENTITIES)
    names = [f for f, _ in fields]
    types = dict(fields)
    target = rng.choice(names)
    kind = rng.choice(("remove", "rename", "type"))
    correct = {"remove": f"Удалить поле {target} из контракта и из выгрузки",
               "rename": f"Переименовать поле {target} в {RENAMES[target]} в контракте",
               "type": f"Сменить тип поля {target} с {types[target]} на {INCOMPATIBLE[types[target]]}"}[kind]
    pool = [f"Добавить необязательное поле {rng.choice(NEW_FIELDS)} типа varchar",
            f"Расширить описание поля {rng.choice(names)} комментарием",
            f"Включить в контракт новую таблицу {table}_archive",
            # безопасные изменения с «разрушительными» глаголами: глагол не выдаёт ключ
            f"Удалить неиспользуемый индекс по полю {rng.choice(names)}",
            "Переименовать колонку в промежуточной таблице ETL"]
    version = f"{rng.randint(1, 4)}.{rng.randint(0, 20)}"
    schema = "\n".join([f"table: {table}", f"version: {version}", "fields:",
                        *(f"  - name: {f}\n    type: {t}" for f, t in fields)])
    text = (f"Контракт данных таблицы {table} (ниже) используют несколько команд; потребители читают поля по имени. "
            "Какое изменение ломает обратную совместимость?")
    return mcq(rng, text, correct, rng.sample(pool, 3), code=schema, language="yaml", radicals=("data_contract", 4))
