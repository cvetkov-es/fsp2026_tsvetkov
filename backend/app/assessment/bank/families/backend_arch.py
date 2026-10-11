import math
import random
from datetime import datetime, timedelta

from app.assessment.bank.base import SHUFFLES, Generated, Prompt, family, mcq, rows_space

RENAMES = (
    ("orders", "customer_name", "client_name"), ("users", "phone", "phone_number"),
    ("payments", "sum", "amount"), ("products", "title", "name"), ("tickets", "state", "status"),
    ("invoices", "total", "total_amount"), ("employees", "dept", "department"),
    ("courses", "descr", "description"), ("devices", "sn", "serial_number"),
    ("bookings", "dt", "booked_at"), ("reviews", "txt", "body"), ("events", "ts", "occurred_at"),
    ("accounts", "login", "username"), ("shipments", "addr", "address"),
    ("messages", "msg", "content"), ("projects", "owner", "owner_id"),
)
SERVICES = ("billing", "crm", "catalog", "auth", "delivery", "analytics", "support", "booking")
STEPS = (
    "Добавить в таблицу {t} новую колонку {new}, допускающую NULL",
    "Выкатить версию приложения, которая пишет и в {old}, и в {new}",
    "Перенести исторические данные из {old} в {new} пакетами",
    "Переключить чтение в приложении на {new}",
    "Выкатить версию приложения, которая больше не обращается к {old}",
    "Удалить колонку {old}",
)


@family(code="be.arch.expand_contract_order", specialization="backend", area="arch", level=4,
        fmt="order", space_size=len(RENAMES) * len(SERVICES) * 720, median_time_s=90)
def expand_contract_order(rng: random.Random) -> Generated:
    t, old, new = rng.choice(RENAMES)
    svc = rng.choice(SERVICES)
    steps = [s.format(t=t, old=old, new=new) for s in STEPS]
    order = list(range(len(steps)))
    rng.shuffle(order)
    shown = tuple(steps[i] for i in order)
    answer = tuple(order.index(i) + 1 for i in range(len(steps)))
    return Generated(
        "order",
        Prompt(text=f"Нужно переименовать колонку {old} в {new} (таблица {t}, сервис {svc}) без простоя "
                    "сервиса. Расположите шаги в правильном порядке.",
               steps=shown, answer_hint="Номера всех шагов через пробел, например: 2 1 3 …"),
        answer, ("expand_contract", len(steps)),
    )


# ---------------------------------------------------------------------------
# План 03b: наполнение области arch
# ---------------------------------------------------------------------------
ID_COUNT = 9999  # идентификаторы 1..9999
SVCS = ("billing", "catalog", "orders", "auth", "search", "notifications", "payments", "reports",
        "profile", "delivery", "inventory", "pricing", "booking", "support", "analytics", "loyalty",
        "media", "checkout", "chat", "geo")
CACHES = ("sessions", "catalog", "profiles", "prices", "search", "feeds", "geo", "rates",
          "permissions", "carts", "reports", "tokens")
PERIODS = ("последний час", "последние сутки", "прошлая неделя", "текущая смена", "вчерашний день",
           "с последнего релиза")
KEYS = ("user:profile", "product:card", "feed:main", "catalog:top", "config:flags", "price:list",
        "rates:today", "page:home", "search:popular", "cart:summary", "news:latest", "geo:cities")
# только бесстеллажные (leaderless) хранилища в стиле Dynamo, где R/W-кворум — штатная настройка
STORES = ("Cassandra", "ScyllaDB", "Riak", "Voldemort")
OBJECTS = ("профиль", "настройки уведомлений", "адрес доставки", "аватар", "статус заказа",
           "список избранного", "комментарий", "способ оплаты")
RAM_PAIRS = ((8, 32), (16, 64), (32, 128), (16, 32), (8, 64), (64, 256))
PAIRS_SERVICES = tuple((a, b, c) for a in SVCS[:6] for b in SVCS[6:10] for c in SVCS[10:14])


def _pick3(rng: random.Random, pool) -> list[str]:
    return rng.sample(pool, 3)


def _picks(pool) -> int:
    """Число способов выбрать 3 дистрактора из пула."""
    return math.comb(len(pool), 3)


# --- be.arch.cache_hit_ratio ----------------------------------------------------
HITS_MIN, HITS_MAX = 10, 9999


@family(code="be.arch.cache_hit_ratio", specialization="backend", area="arch", level=1,
        fmt="calc", median_time_s=35,
        space_size=(HITS_MAX - HITS_MIN + 1) ** 2 * len(CACHES) * len(PERIODS))
def cache_hit_ratio(rng: random.Random) -> Generated:
    while True:
        h, m = rng.randint(HITS_MIN, HITS_MAX), rng.randint(HITS_MIN, HITS_MAX)
        # дробная часть ровно .5 (200·H/(H+M) — нечётное целое) — режим округления спорен: перебрасываем
        if not (200 * h % (h + m) == 0 and (200 * h // (h + m)) % 2 == 1):
            break
    answer = round(100 * h / (h + m))
    return Generated(
        "number",
        Prompt(text=f"Период наблюдения: {rng.choice(PERIODS)}. Кэш «{rng.choice(CACHES)}»: "
                    f"попаданий — {h}, промахов — {m}. Какой hit ratio в процентах? Округлите до целого.",
               answer_hint="Целое число, без знака %"),
        answer, ("hit_ratio",),
    )


# --- be.arch.scale_up_vs_out ----------------------------------------------------
HOR = "Горизонтальное масштабирование"
VER = "Вертикальное масштабирование"
SHARD = "Шардирование данных по ключу"
REPL = "Репликация данных между узлами"
CACHE_OPT = "Кэширование популярных ответов"
INSTANCES_MIN, INSTANCES_MAX = 2, 9
SCALE_TAIL = "Как называется такой подход?"
SCALE_ROWS = (
    ((f"Сервис «{{svc}}» не хранит состояние между запросами. Команда запускает дополнительные "
      f"одинаковые экземпляры за балансировщиком нагрузки (число добавленных: {{n}}). {SCALE_TAIL}",
      f"Для сервиса «{{svc}}» без состояния в пул за балансировщиком добавляют одинаковые серверы, "
      f"а не заменяют существующий на более мощный (число добавленных серверов: {{n}}). {SCALE_TAIL}",
      f"Нагрузка на «{{svc}}» выросла, сервис без состояния. Единственный сервер не усиливают, а "
      f"запросы раскидывают через балансировщик по нескольким одинаковым серверам (их число: {{n}}). "
      f"{SCALE_TAIL}"),
     HOR, (VER, SHARD, REPL, CACHE_OPT)),
    ((f"Единственный сервер сервиса «{{svc}}» не справляется. Его заменили на машину с бо́льшим "
      f"объёмом RAM ({{old}} → {{new}} ГБ) и более мощным процессором. {SCALE_TAIL}",
      f"Сервис «{{svc}}» работает на одном сервере, где CPU загружен на 100%. Команда переезжает на "
      f"сервер с большим числом ядер и объёмом RAM ({{old}} → {{new}} ГБ), оставив один экземпляр. "
      f"{SCALE_TAIL}",
      f"Единственный сервер БД сервиса «{{svc}}» упирается в память. Его перенесли на машину с "
      f"бо́льшим объёмом RAM ({{old}} → {{new}} ГБ), архитектура не изменилась. {SCALE_TAIL}",
      f"Для «{{svc}}» на единственном сервере увеличили объём RAM ({{old}} → {{new}} ГБ) и число ядер, "
      f"количество серверов не менялось. {SCALE_TAIL}"),
     VER, (HOR, SHARD, REPL, CACHE_OPT)),
)
_SCALE_SIZES = {"svc": len(SVCS), "n": INSTANCES_MAX - INSTANCES_MIN + 1, "old": len(RAM_PAIRS)}


@family(code="be.arch.scale_up_vs_out", specialization="backend", area="arch", level=1,
        fmt="mcq", median_time_s=30,
        space_size=rows_space(SCALE_ROWS, _SCALE_SIZES, extra=math.comb(len(SCALE_ROWS[0][2]) - 1, 2) * SHUFFLES,
                              dependent=frozenset({"new"})))  # new задан парой с old; 2 из 3 прочих
def scale_up_vs_out(rng: random.Random) -> Generated:
    templates, correct, pool = rng.choice(SCALE_ROWS)
    old, new = rng.choice(RAM_PAIRS)
    text = rng.choice(templates).format(svc=rng.choice(SVCS), n=rng.randint(INSTANCES_MIN, INSTANCES_MAX),
                                        old=old, new=new)
    # противоположное масштабирование всегда среди вариантов, остальные — две из трёх других
    return mcq(rng, text, correct, (pool[0], *rng.sample(pool[1:], 2)))


# --- be.arch.ttl_expiry ---------------------------------------------------------
SECONDS_PER_DAY = 86400
TTL_MIN, TTL_MAX = 30, SECONDS_PER_DAY - 1


@family(code="be.arch.ttl_expiry", specialization="backend", area="arch", level=2,
        fmt="calc", median_time_s=50,
        space_size=SECONDS_PER_DAY * (TTL_MAX - TTL_MIN + 1) * len(KEYS))
def ttl_expiry(rng: random.Random) -> Generated:
    start = datetime(2026, 1, 1) + timedelta(seconds=rng.randrange(SECONDS_PER_DAY))
    ttl = rng.randint(TTL_MIN, TTL_MAX)
    end = start + timedelta(seconds=ttl)
    return Generated(
        "text",
        Prompt(text=f"Значение по ключу «{rng.choice(KEYS)}» записали в кэш в {start:%H:%M:%S} (время "
                    f"суток). TTL: {ttl} с, ключ истекает ровно через столько секунд после записи. "
                    "В какой момент ключ перестанет быть доступным? Если это случится после полуночи, "
                    "укажите время следующих суток.",
               answer_hint="Время в формате ЧЧ:ММ:СС, например 07:05:09"),
        f"{end:%H:%M:%S}", ("ttl_time",),
    )


# --- be.arch.queue_vs_sync ------------------------------------------------------
SEC_MIN, SEC_MAX = 5, 300
QUEUE_TAIL = "Какое решение подходит лучше всего?"
QUEUE_POOL = ("Вызывать сервис синхронно в обработчике, повторяя при ошибке",
              "Увеличить таймаут клиента, чтобы дождаться завершения",
              "Закэшировать результат операции на стороне сервера",
              "Добавить реплику БД для разгрузки операций чтения")
QUEUE_ROWS = (
    ((f"После регистрации пользователя в сервисе «{{svc}}» нужно отправить приветственное письмо "
      f"(время отправки, с: {{sec}}). Требование: ответ на запрос регистрации не ждёт отправки. "
      f"{QUEUE_TAIL}",),
     "Поставить письмо в очередь, отправит фоновый воркер", QUEUE_POOL),
    ((f"Пользователь загрузил видео в «{{svc}}»; создание превью идёт долго (время, с: {{sec}}). "
      f"Требование: ответ на загрузку приходит сразу. {QUEUE_TAIL}",),
     "Передать задачу фоновому воркеру через очередь сообщений", QUEUE_POOL),
    ((f"Запрос на выгрузку отчёта в «{{svc}}» строит файл долго (время, с: {{sec}}). Требование: "
      f"пользователь получает ответ сразу, а файл скачивает позже. {QUEUE_TAIL}",),
     "Строить файл фоновой задачей и отдать клиенту ссылку позже", QUEUE_POOL),
    ((f"После оплаты заказа в «{{svc}}» нужно уведомить внешний сервис партнёра: он отвечает медленно "
      f"и временами недоступен (время ответа, с: {{sec}}). Требование: оплата не ждёт уведомления. {QUEUE_TAIL}",),
     "Положить уведомление в очередь, отправит воркер в фоне", QUEUE_POOL),
)
_QUEUE_SIZES = {"svc": len(SVCS), "sec": SEC_MAX - SEC_MIN + 1}


@family(code="be.arch.queue_vs_sync", specialization="backend", area="arch", level=2,
        fmt="mcq", median_time_s=45,
        space_size=rows_space(QUEUE_ROWS, _QUEUE_SIZES, extra=_picks(QUEUE_POOL) * SHUFFLES))
def queue_vs_sync(rng: random.Random) -> Generated:
    templates, correct, pool = rng.choice(QUEUE_ROWS)
    text = rng.choice(templates).format(svc=rng.choice(SVCS), sec=rng.randint(SEC_MIN, SEC_MAX))
    return mcq(rng, text, correct, _pick3(rng, pool))


# --- be.arch.read_your_writes ---------------------------------------------------
LAG_MIN, LAG_MAX = 50, 2000
RYW_TAIL = "Что нужно сделать?"
RYW_POOL = ("Увеличить число асинхронных реплик чтения в кластере БД",
            "Включить кэш ответов на уровне приложения для страницы",
            "Перезапускать реплику после каждой записи пользователя",
            "Расширить пул соединений приложения к реплике чтения")
RYW_ROWS = (
    ((f"Пользователь сохранил {{obj}} (запись идёт на primary) и сразу открыл страницу, данные для "
      f"которой читаются с асинхронной реплики, но видит старое значение. Лаг репликации обычно "
      f"{{lag}} мс. Требование: пользователь сразу видит собственные изменения. {RYW_TAIL}",
      f"В сервисе «{{svc}}» пользователь сохраняет {{obj}} на primary, а следующая страница читает "
      f"данные с асинхронной реплики и показывает старое. Лаг репликации обычно {{lag}} мс. "
      f"Требование: автор изменения сразу видит своё новое значение. {RYW_TAIL}"),
     "Читать собственные свежие записи пользователя с primary", RYW_POOL),
    ((f"Пользователь сохранил {{obj}} (запись идёт на primary) и сразу открыл страницу, данные для "
      f"которой читаются с асинхронной реплики, но видит старое значение. Лаг репликации обычно "
      f"{{lag}} мс. Требование: пользователь сразу видит собственные изменения, а чтение остаётся "
      f"на репликах. {RYW_TAIL}",
      f"В сервисе «{{svc}}» пользователь сохраняет {{obj}} на primary, а следующая страница читает "
      f"данные с асинхронной реплики и показывает старое. Лаг репликации обычно {{lag}} мс. "
      f"Требование: автор изменения сразу видит своё значение, читая с реплик. {RYW_TAIL}"),
     "Ждать перед чтением, пока реплика применит эту запись", RYW_POOL),
)
_RYW_SIZES = {"svc": len(SVCS), "obj": len(OBJECTS), "lag": LAG_MAX - LAG_MIN + 1}


@family(code="be.arch.read_your_writes", specialization="backend", area="arch", level=2,
        fmt="mcq", median_time_s=55,
        space_size=rows_space(RYW_ROWS, _RYW_SIZES, extra=_picks(RYW_POOL) * SHUFFLES))
def read_your_writes(rng: random.Random) -> Generated:
    templates, correct, pool = rng.choice(RYW_ROWS)
    text = rng.choice(templates).format(svc=rng.choice(SVCS), obj=rng.choice(OBJECTS),
                                        lag=rng.randint(LAG_MIN, LAG_MAX))
    return mcq(rng, text, correct, _pick3(rng, pool))


# --- be.arch.cache_stampede -----------------------------------------------------
RPS_MIN, RPS_MAX = 100, 10000
REBUILD_MS = tuple(range(50, 1001, 50))
STAMPEDE_TAIL = "Что нужно сделать?"
STAMPEDE_POOL = ("Уменьшить TTL ключа, чтобы значение обновлялось чаще",
                 "Добавить реплику БД, чтобы распределить запросы на чтение",
                 "Отключить кэширование ключа и всегда читать данные из БД",
                 "Увеличить пул соединений с БД, чтобы принять все запросы")
_STAMPEDE_BODY = ("Ключ «{key}» популярен: нагрузка на него, запросов/с: {rps}. Когда TTL истекает, "
                  "значение перестраивается запросом к БД (время перестройки, мс: {ms}), и пока оно "
                  "строится, каждый запрос к ключу идёт в БД, а она перегружается. Требование: ")
STAMPEDE_ROWS = (
    ((_STAMPEDE_BODY + f"при истечении TTL БД получает один запрос на перестройку, а не лавину. "
      f"{STAMPEDE_TAIL}",),
     "Перестраивать значение под блокировкой, остальные ждут", STAMPEDE_POOL),
    ((_STAMPEDE_BODY + f"клиенты не ждут перестройки, а БД не получает лавину запросов в момент "
      f"истечения TTL. {STAMPEDE_TAIL}",),
     "Обновлять значение заранее: шанс растёт ближе к концу TTL", STAMPEDE_POOL),
)
_STAMPEDE_SIZES = {"key": len(KEYS), "rps": RPS_MAX - RPS_MIN + 1, "ms": len(REBUILD_MS)}


@family(code="be.arch.cache_stampede", specialization="backend", area="arch", level=3,
        fmt="mcq", median_time_s=75,
        space_size=rows_space(STAMPEDE_ROWS, _STAMPEDE_SIZES, extra=_picks(STAMPEDE_POOL) * SHUFFLES))
def cache_stampede(rng: random.Random) -> Generated:
    templates, correct, pool = rng.choice(STAMPEDE_ROWS)
    text = rng.choice(templates).format(key=rng.choice(KEYS), rps=rng.randint(RPS_MIN, RPS_MAX),
                                        ms=rng.choice(REBUILD_MS))
    return mcq(rng, text, correct, _pick3(rng, pool))


# --- be.arch.at_least_once_consumer ---------------------------------------------
PARTS_MIN, PARTS_MAX = 3, 64
GROUP_MIN, GROUP_MAX = 2, 16
CONSUMER_TAIL = "Что нужно сделать?"
CONSUMERS = (
    ("billing", "PaymentReceived", "зачисляет деньги на счёт клиента"),
    ("loyalty", "OrderCompleted", "начисляет бонусные баллы"),
    ("warehouse", "OrderPaid", "списывает товар со склада"),
    ("notifications", "ShipmentSent", "отправляет клиенту SMS о доставке"),
    ("accounting", "InvoiceIssued", "создаёт проводку в учёте"),
    ("crm", "UserRegistered", "создаёт карточку клиента"),
    ("delivery", "OrderPacked", "создаёт заявку курьеру"),
    ("referral", "FriendJoined", "выплачивает реферальное вознаграждение"),
)
CONSUMER_POOL = ("Положиться на брокер: он гарантирует отсутствие дублей",
                 "Фиксировать offset до начала обработки события",
                 "Увеличить число партиций топика, чтобы дублей стало меньше",
                 "Брать блокировку на весь топик на время обработки")
_CONSUMER_BODY = ("Сервис «{svc}» читает события {event} из топика (число партиций: {parts}, "
                  "потребителей в группе: {group}) и для каждого {effect}. Брокер гарантирует доставку "
                  "at-least-once. Требование: ")
# потребителей в группе не больше партиций (иначе часть простаивает): пар (parts, group) считаем точно
_PARTS_GROUPS = sum(min(p, GROUP_MAX) - GROUP_MIN + 1 for p in range(PARTS_MIN, PARTS_MAX + 1))
_CONSUMER_SIZES = {"svc": len(CONSUMERS), "parts": _PARTS_GROUPS}
CONSUMER_ROWS = (
    ((_CONSUMER_BODY + f"событие не должно ни теряться, ни применяться дважды. {CONSUMER_TAIL}",),
     "Хранить id обработанных событий и пропускать повторы", CONSUMER_POOL),
    ((_CONSUMER_BODY + f"повторная доставка того же события не должна менять результат. {CONSUMER_TAIL}",),
     "Сделать обработку события идемпотентной по его id", CONSUMER_POOL),
)


@family(code="be.arch.at_least_once_consumer", specialization="backend", area="arch", level=3,
        fmt="mcq", median_time_s=75,
        space_size=rows_space(CONSUMER_ROWS, _CONSUMER_SIZES, extra=_picks(CONSUMER_POOL) * SHUFFLES,
                              dependent=frozenset({"event", "effect", "group"})))
def at_least_once_consumer(rng: random.Random) -> Generated:
    templates, correct, pool = rng.choice(CONSUMER_ROWS)
    svc, event, effect = rng.choice(CONSUMERS)
    parts = rng.randint(PARTS_MIN, PARTS_MAX)
    text = rng.choice(templates).format(svc=svc, event=event, effect=effect, parts=parts,
                                        group=rng.randint(GROUP_MIN, min(parts, GROUP_MAX)))
    return mcq(rng, text, correct, _pick3(rng, pool))


# --- be.arch.timeout_budget -----------------------------------------------------
TIMEOUTS_MS = tuple(range(100, 2001, 50))
RETRIES_MIN, RETRIES_MAX = 1, 5


@family(code="be.arch.timeout_budget", specialization="backend", area="arch", level=3,
        fmt="calc", median_time_s=80,
        space_size=len(TIMEOUTS_MS) ** 2 * (RETRIES_MAX - RETRIES_MIN + 1) ** 2 * len(PAIRS_SERVICES))
def timeout_budget(rng: random.Random) -> Generated:
    a, b, c = rng.choice(PAIRS_SERVICES)
    tb, tc = rng.choice(TIMEOUTS_MS), rng.choice(TIMEOUTS_MS)
    rb, rc = rng.randint(RETRIES_MIN, RETRIES_MAX), rng.randint(RETRIES_MIN, RETRIES_MAX)
    return Generated(
        "number",
        Prompt(text=f"Сервис «{a}» вызывает сервис «{b}», а после его ответа — сервис «{c}»; вызовы "
                    f"последовательные. Таймаут одной попытки, мс: «{b}» — {tb}, «{c}» — {tc}. При ошибке "
                    "или таймауте попытка повторяется без пауз между попытками. Число повторов после "
                    f"первой попытки: «{b}» — {rb}, «{c}» — {rc} (всего попыток на вызов: 1 + число "
                    "повторов). Худший случай: все повторы использованы, неудачные попытки длятся весь "
                    "таймаут, а последняя попытка каждого вызова успешна и отвечает в самый последний "
                    f"момент своего таймаута. Каково максимальное время ожидания сервиса «{a}», мс?",
               answer_hint="Целое число миллисекунд"),
        tb * (1 + rb) + tc * (1 + rc), ("timeout_budget",),
    )


# --- be.arch.circuit_breaker_state ----------------------------------------------
CB_F = (2, 3, 4, 5)
CB_W = tuple(range(10, 61))
CB_STATES = ("closed", "open", "half-open", "disabled")  # disabled — всегда дистрактор
CB_EVENTS_MIN, CB_EVENTS_MAX = 8, 12
CB_FAIL_SHARE = 0.6  # доля ошибок среди ответов сервиса
CB_SAME_MOMENT = 0.2  # доля вопросов «в момент последнего события» среди closed/open


def _cb_simulate(events, f: int, w: int, tq: int) -> tuple[str, int]:
    """(состояние в момент tq, число переходов в open)."""
    state, fails, opened_at, opens = "closed", 0, 0, 0
    for t, ok in events:
        if state == "open":
            if t < opened_at + w:
                continue  # отклонён без обращения к сервису
            if ok:
                state, fails = "closed", 0
            else:
                opened_at, opens = t, opens + 1  # пробный запрос не прошёл: отсчёт заново
            continue
        fails = 0 if ok else fails + 1
        if fails >= f:
            state, opened_at, fails, opens = "open", t, 0, opens + 1
    if state == "open" and tq >= opened_at + w:
        return "half-open", opens
    return state, opens


@family(code="be.arch.circuit_breaker_state", specialization="backend", area="arch", level=4,
        fmt="calc", median_time_s=110,
        # консервативная оценка снизу: порог × ожидание × исходы 8 событий × порядок вариантов
        space_size=len(CB_F) * len(CB_W) * 2 ** CB_EVENTS_MIN * SHUFFLES)
def circuit_breaker_state(rng: random.Random) -> Generated:
    f, w = rng.choice(CB_F), rng.choice(CB_W)
    target = rng.choice(CB_STATES[:3])  # каждое из трёх реальных состояний бывает ключом
    # Вопрос в момент последнего события — редкая ветка (CB_SAME_MOMENT) и только для closed/open;
    # в ней «поверхностное правило» (ответ последнего события) должно ошибаться в половине случаев
    same_moment = target != "half-open" and rng.random() < CB_SAME_MOMENT
    rule_must_be_right = rng.random() < 0.5
    for _ in range(5000):
        n = rng.randint(CB_EVENTS_MIN, CB_EVENTS_MAX)
        t = rng.randint(1, 10)
        events = []
        for _i in range(n):
            events.append((t, rng.random() >= CB_FAIL_SHARE))
            t += rng.randint(1, max(3, 2 * w // 3))
        tq = events[-1][0] + (0 if same_moment else rng.randint(1, 2 * w))
        state, opens = _cb_simulate(events, f, w, tq)
        if state != target or opens < 1:
            continue
        if same_moment and (("closed" if events[-1][1] else "open") == state) != rule_must_be_right:
            continue
        break
    else:  # pragma: no cover - вероятность пренебрежимо мала
        raise RuntimeError("не удалось построить сценарий breaker")
    lines = "\n".join(f"t={ts} с: запрос; при обращении сервис отвечает {'успешно' if ok else 'ошибкой'}"
                      for ts, ok in events)
    svc = rng.choice(SVCS)
    text = (
        f"Circuit breaker стоит перед вызовами сервиса «{svc}». Порог (число ошибок подряд): {f}. "
        f"Время ожидания в open, с: {w}. Модель работы: в closed запросы идут в сервис; успех обнуляет "
        "счётчик ошибок подряд, а когда счётчик достигает порога, breaker переходит в open в момент "
        "этой ошибки. В open запросы отклоняются без обращения к сервису и ничего не меняют. Когда "
        "с момента перехода в open прошло не меньше времени ожидания, breaker сам становится "
        "half-open. Первый запрос в half-open — пробный: он идёт в сервис, успех переводит в closed "
        "(счётчик обнулён), ошибка — снова в open, а отсчёт ожидания начинается заново с момента этой "
        f"ошибки. События:\n{lines}\n"
        # один шаблон вопроса для обеих ветвей (момент последнего события и позже): точен в обеих
        f"Какое состояние у breaker в момент t={tq} с, если все перечисленные события, включая "
        "пришедшие в этот момент, уже обработаны и других запросов не было?"
    )
    return mcq(rng, text, state, [x for x in CB_STATES if x != state],
               radicals=("circuit_breaker", len(CB_STATES)))


# --- be.arch.backpressure -------------------------------------------------------
RATE_C_MIN, RATE_C_MAX = 50, 900
RATE_FACTORS = tuple(range(13, 33))  # продюсер = консьюмер × k / 10, т.е. быстрее на 30%..220%
BACKPRESSURE_TAIL = "Что нужно сделать?"
BACKPRESSURE_POOL = ("Увеличить объём памяти узла, на котором хранится очередь",
                     "Включить автоматические повторные отправки у продюсера при сбоях",
                     "Сбрасывать очередь на диск, когда оперативная память заполнится",
                     "Сжимать сообщения, чтобы очередь занимала меньше памяти",
                     "Перевести продюсера на пакетную отправку сообщений по сети")
_BP_BODY = ("Сервис «{prod}» публикует сообщения в очередь быстрее, чем сервис «{cons}» их разбирает: "
            "продюсер — {p} сообщ./с, консьюмер — {c} сообщ./с. Очередь хранится в памяти брокера и "
            "растёт, пока память не закончится. Требование: ")
BACKPRESSURE_ROWS = (
    ((_BP_BODY + f"очередь не должна исчерпать память брокера, а продюсер подстраивается под скорость "
      f"консьюмера. {BACKPRESSURE_TAIL}",),
     "Ограничить очередь и замедлять продюсера, когда она полна", BACKPRESSURE_POOL),
    ((_BP_BODY + f"очередь не должна исчерпать память брокера, а продюсер сразу узнаёт, что сообщение "
      f"не принято. {BACKPRESSURE_TAIL}",),
     "Ограничить очередь и не принимать сообщения, пока она полна", BACKPRESSURE_POOL),
)
_BP_PAIRS = tuple((a, b) for a in SVCS[:10] for b in SVCS[10:])
_BP_SIZES = {"prod": len(_BP_PAIRS), "c": RATE_C_MAX - RATE_C_MIN + 1}


@family(code="be.arch.backpressure", specialization="backend", area="arch", level=4,
        fmt="mcq", median_time_s=100,
        # cons — вторая половина пары, p задан c и множителем (множитель — в extra)
        space_size=rows_space(BACKPRESSURE_ROWS, _BP_SIZES,
                              extra=len(RATE_FACTORS) * _picks(BACKPRESSURE_POOL) * SHUFFLES,
                              dependent=frozenset({"cons", "p"})))
def backpressure(rng: random.Random) -> Generated:
    templates, correct, pool = rng.choice(BACKPRESSURE_ROWS)
    prod, cons = rng.choice(_BP_PAIRS)
    c = rng.randint(RATE_C_MIN, RATE_C_MAX)
    p = c * rng.choice(RATE_FACTORS) // 10  # при c >= 50 разные множители дают разные p
    text = rng.choice(templates).format(prod=prod, cons=cons, p=p, c=c)
    return mcq(rng, text, correct, _pick3(rng, pool))


# --- be.arch.saga_compensation_order --------------------------------------------
# (название, ((действие, компенсация) × 6)); все 12 текстов в саге различны
SAGAS = (
    ("Оформление заказа", (
        ("Создать заказ в статусе «новый»", "Отменить заказ"),
        ("Зарезервировать товар на складе", "Снять резерв товара на складе"),
        ("Списать деньги с карты клиента", "Вернуть деньги на карту клиента"),
        ("Создать заявку на доставку", "Отменить заявку на доставку"),
        ("Начислить клиенту бонусные баллы", "Списать начисленные бонусные баллы"),
        ("Отправить клиенту подтверждение", "Отправить клиенту уведомление об отмене"))),
    ("Бронирование поездки", (
        ("Забронировать авиабилет", "Отменить бронь авиабилета"),
        ("Забронировать номер в отеле", "Отменить бронь номера в отеле"),
        ("Арендовать автомобиль", "Отменить аренду автомобиля"),
        ("Оформить страховку", "Аннулировать страховой полис"),
        ("Списать оплату поездки", "Вернуть оплату поездки"),
        ("Выпустить электронные документы", "Аннулировать электронные документы"))),
    ("Перевод между счетами", (
        ("Создать запись о переводе", "Пометить перевод отменённым"),
        ("Заблокировать сумму на счёте отправителя", "Снять блокировку суммы на счёте отправителя"),
        ("Списать сумму со счёта отправителя", "Вернуть сумму на счёт отправителя"),
        ("Зачислить сумму на счёт получателя", "Списать сумму со счёта получателя"),
        ("Начислить комиссию банку", "Вернуть комиссию клиенту"),
        ("Записать проводку в журнал", "Записать сторнирующую проводку"))),
    ("Приём сотрудника", (
        ("Создать учётную запись сотрудника", "Заблокировать учётную запись сотрудника"),
        ("Выдать доступ к корпоративной почте", "Отозвать доступ к корпоративной почте"),
        ("Заказать рабочий ноутбук", "Отменить заказ рабочего ноутбука"),
        ("Оформить пропуск в офис", "Аннулировать пропуск в офис"),
        ("Назначить наставника", "Снять назначение наставника"),
        ("Отправить приглашение на онбординг", "Отозвать приглашение на онбординг"))),
    ("Подключение тарифа", (
        ("Создать подписку клиента", "Отменить подписку клиента"),
        ("Выделить клиенту квоту ресурсов", "Освободить квоту ресурсов клиента"),
        ("Списать первый платёж", "Вернуть первый платёж"),
        ("Создать счёт в личном кабинете", "Аннулировать счёт в личном кабинете"),
        ("Выдать клиенту промокод", "Деактивировать выданный промокод"),
        ("Отправить приветственное письмо", "Отправить письмо об отмене подключения"))),
    ("Запись на приём к врачу", (
        ("Занять слот в расписании врача", "Освободить слот в расписании врача"),
        ("Создать карту пациента на визит", "Удалить карту пациента на визит"),
        ("Списать предоплату за приём", "Вернуть предоплату за приём"),
        ("Забронировать кабинет", "Снять бронь кабинета"),
        ("Выписать направление на анализы", "Аннулировать направление на анализы"),
        ("Отправить пациенту напоминание", "Отправить пациенту уведомление об отмене"))),
)
SAGA_N = (4, 5, 6)
SAGA_K_MIN = 4  # ошибка не раньше 4-го шага: упорядочиваются минимум 3 компенсации
SAGA_STEPS_SPACE = sum(math.factorial(k - 1) - 1 for n in SAGA_N for k in range(SAGA_K_MIN, n + 1))


@family(code="be.arch.saga_compensation_order", specialization="backend", area="arch", level=5,
        fmt="order", median_time_s=140,
        space_size=len(SAGAS) * ID_COUNT * SAGA_STEPS_SPACE)  # без тождественной перестановки
def saga_compensation_order(rng: random.Random) -> Generated:
    title, steps = rng.choice(SAGAS)
    n = rng.choice(SAGA_N)
    k = rng.randint(SAGA_K_MIN, n)
    comps = [steps[i][1] for i in range(k - 1)]
    canon = list(range(k - 2, -1, -1))  # индексы компенсаций в нужном порядке
    while True:
        order = list(range(k - 1))
        rng.shuffle(order)
        if order != canon:  # показанный порядок не совпадает с готовым ответом
            break
    shown = tuple(comps[i] for i in order)
    answer = tuple(order.index(i) + 1 for i in canon)
    listing = "\n".join(f"{i + 1}) {steps[i][0]}" for i in range(n))
    return Generated(
        "order",
        Prompt(text=f"Сага «{title}» (экземпляр саги №{rng.randint(1, ID_COUNT)}) выполняет шаги по порядку:\n"
                    f"{listing}\nШаг {k} завершился ошибкой, следующие шаги не запускались. "
                    "Расположите компенсирующие действия успешных шагов в том порядке, в котором оркестратор "
                    "саги должен их выполнить.",
               steps=shown, answer_hint="Номера всех действий через пробел, например: 2 1 3 …"),
        answer, ("saga_reverse",),
    )


# --- be.arch.quorum_read --------------------------------------------------------
QUORUM_N = tuple(range(3, 10))
QUORUM_ID_MIN = 1000  # идентификатор не совпадает с однозначным ключом ответа


@family(code="be.arch.quorum_read", specialization="backend", area="arch", level=5,
        fmt="calc", median_time_s=130,
        space_size=sum(QUORUM_N) * len(STORES) * (ID_COUNT - QUORUM_ID_MIN + 1))  # пар (N, W): N вариантов W на каждое N
def quorum_read(rng: random.Random) -> Generated:
    n = rng.choice(QUORUM_N)
    w = rng.randint(1, n)
    return Generated(
        "number",
        Prompt(text=f"Хранилище {rng.choice(STORES)}, ключ order:{rng.randint(QUORUM_ID_MIN, ID_COUNT)}. Число "
                    f"реплик: {n}. Число реплик, которые должны подтвердить запись: {w}. Чтение "
                    "опрашивает R реплик и берёт самое свежее значение из полученных. Каково "
                    "минимальное R, при котором чтение гарантированно увидит последнюю "
                    "подтверждённую запись?",
               answer_hint="Целое число реплик"),
        n - w + 1, ("quorum_read",),
    )
