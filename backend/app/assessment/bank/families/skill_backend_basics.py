"""Навык «Основы бэкенда»: области http и api. Концепции — базовые, не повторяют семейства be.*: навык проходит, например, фронтендер.
"""
import base64
import json
import math
import random
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from urllib.parse import parse_qs, urlsplit

from app.assessment.bank.base import SHUFFLES, Generated, Prompt, family, mcq

SPEC = "skill:backend_basics"
SERVICES = ("billing", "catalog", "orders", "auth", "search", "delivery", "profile", "reports", "payments",
            "booking", "notify", "media")
RESOURCES = ("orders", "users", "products", "invoices", "tickets", "files", "reviews", "teams", "courses", "posts")


# --- sk.be.url_parts --------------------------------------------------------------------------
HOSTS = ("api.shop.ru", "example.com", "cdn.media.net", "auth.corp.local", "data.city.gov", "pay.bank.ru",
         "static.site.io", "my.app.dev")
PATH_PARTS = ("v1", "v2", "api", "users", "orders", "files", "search", "reports", "items", "admin", "public")
QUERY_PARAMS = {"page": tuple(str(n) for n in range(1, 21)), "sort": ("asc", "desc", "new", "top", "price"),
                "lang": ("ru", "en", "de", "fr"), "q": ("python", "docker", "sql", "react", "go"),
                "limit": ("10", "20", "50", "100"), "tag": ("news", "sale", "new", "faq"),
                "ref": ("mail", "tg", "vk", "ads"), "mode": ("full", "short", "draft", "dark")}
FRAGMENTS = ("top", "reviews", "faq", "step-2", "price", "section-3")


@family(code="sk.be.url_parts", specialization=SPEC, area="http", level=1, fmt="calc",
        space_size=2 * len(HOSTS) * 3 * len(PATH_PARTS) ** 2 * (len(QUERY_PARAMS) * 4) ** 2 * 3,
        median_time_s=35)
def url_parts(rng: random.Random) -> Generated:
    scheme = rng.choice(("http", "https"))
    port = rng.choice(("", f":{rng.choice((8080, 8443, 3000, 5000, 9000))}"))
    path = "/" + "/".join(rng.sample(PATH_PARTS, rng.randint(2, 3)))
    keys = rng.sample(sorted(QUERY_PARAMS), rng.randint(2, 3))
    query = "&".join(f"{k}={rng.choice(QUERY_PARAMS[k])}" for k in keys)
    url = f"{scheme}://{rng.choice(HOSTS)}{port}{path}?{query}#{rng.choice(FRAGMENTS)}"
    parts = urlsplit(url)
    asked = rng.choice(("host", "path", "param"))
    if asked == "host":
        text, answer = "Какой хост (без схемы и порта) у этого URL?", parts.hostname
    elif asked == "path":
        text, answer = "Какой путь (path) у этого URL — без строки запроса и якоря?", parts.path
    else:
        key = rng.choice(keys)
        text, answer = f"Какое значение параметра {key} у этого URL?", parse_qs(parts.query)[key][0]
    return Generated("text", Prompt(text=text, code=url, language="text", answer_hint="Строка без кавычек"),
                     answer, ("url_parts",))


# --- sk.be.status_class -----------------------------------------------------------------------
CODES = (200, 201, 202, 204, 206, 301, 302, 303, 304, 307, 308, 400, 401, 403, 404, 405, 409, 410, 415, 422, 429,
         500, 501, 502, 503, 504)
CLASSES = {"2": "2xx — успех", "3": "3xx — перенаправление", "4": "4xx — ошибка клиента", "5": "5xx — ошибка сервера"}
METHODS = ("GET", "POST", "PUT", "DELETE")


@family(code="sk.be.status_class", specialization=SPEC, area="http", level=1, fmt="mcq",
        space_size=len(CODES) * len(SERVICES) * len(METHODS) * len(RESOURCES) * SHUFFLES, median_time_s=25)
def status_class(rng: random.Random) -> Generated:
    code = rng.choice(CODES)
    text = (f"Сервис {rng.choice(SERVICES)} на запрос {rng.choice(METHODS)} /{rng.choice(RESOURCES)} ответил "
            f"кодом {code}. К какому классу относится ответ?")
    key = CLASSES[str(code)[0]]
    return mcq(rng, text, key, [v for v in CLASSES.values() if v != key])


# --- sk.be.rest_route_for_action --------------------------------------------------------------
# действие, правильный запрос, три неверных; у неверных — разные первые слова или та же форма с ошибкой
ACTIONS = (
    ("Добавить комментарий к посту {id}", "POST /posts/{id}/comments",
     ("GET /posts/{id}/comments", "POST /comments/{id}/posts", "PUT /posts/{id}")),
    ("Получить список заказов пользователя {id}", "GET /users/{id}/orders",
     ("POST /users/{id}/orders", "GET /orders/{id}/users", "GET /getUserOrders/{id}")),
    ("Изменить только email пользователя {id}", "PATCH /users/{id}",
     ("POST /users/{id}/update", "GET /users/{id}/email", "DELETE /users/{id}/email")),
    ("Удалить файл {id}", "DELETE /files/{id}",
     ("POST /files/{id}/delete", "GET /files/delete/{id}", "PUT /files/{id}")),
    ("Создать заказ в магазине {id}", "POST /stores/{id}/orders",
     ("PUT /stores/{id}", "GET /stores/{id}/orders/create", "POST /orders/{id}/stores")),
    ("Получить карточку товара {id}", "GET /products/{id}",
     ("POST /products/{id}", "GET /getProduct/{id}", "PUT /products/{id}/get")),
)


@family(code="sk.be.rest_route_for_action", specialization=SPEC, area="api", level=2, fmt="mcq",
        space_size=len(ACTIONS) * 9999 * SHUFFLES, median_time_s=40)
def rest_route_for_action(rng: random.Random) -> Generated:
    text, correct, wrong = rng.choice(ACTIONS)
    i = rng.randint(1, 9999)
    return mcq(rng, f"{text.format(id=i)}. Какой запрос лучше всего соответствует REST?", correct.format(id=i),
               [w.format(id=i) for w in wrong])


# --- sk.be.content_type_choice ----------------------------------------------------------------
FIELDS = ("email", "name", "phone", "city", "comment", "rating", "title", "amount", "login", "code", "age", "tag")
FILES = ("avatar.png", "resume.pdf", "scan.jpg", "report.docx", "photo.webp", "contract.pdf")
TYPES = ("application/json", "multipart/form-data", "application/x-www-form-urlencoded", "text/csv")


@family(code="sk.be.content_type_choice", specialization=SPEC, area="http", level=2, fmt="mcq",
        space_size=len(RESOURCES) * math.perm(len(FIELDS), 2) * (3 + len(FILES)) * SHUFFLES, median_time_s=40)
def content_type_choice(rng: random.Random) -> Generated:
    f1, f2 = rng.sample(FIELDS, 2)
    res = rng.choice(RESOURCES)
    shape = rng.randrange(4)
    if shape == 0:
        text = f'Мобильное приложение отправляет в POST /api/{res} объект {{"{f1}": …, "{f2}": …}}.'
    elif shape == 1:
        text = f"Форма отправляет на /api/{res} файл {rng.choice(FILES)} и поле {f1} в одном запросе."
    elif shape == 2:
        text = f"Обычная HTML-форма без вложений отправляет поля {f1} и {f2} методом POST на /{res} (enctype по умолчанию)."
    else:
        text = f"Скрипт отправляет в PUT /api/{res}/import таблицу в формате CSV с колонками {f1} и {f2}, без обёрток."
    return mcq(rng, f"{text} Какой Content-Type у тела запроса?", TYPES[shape], [t for t in TYPES if t != TYPES[shape]])


# --- sk.be.json_count_fields ------------------------------------------------------------------
SKUS = ("A1", "B7", "C3", "D9", "E2", "F5", "G8", "H4")
STATUSES = ("paid", "new", "shipped", "canceled")


def _order(rng: random.Random, oid: int) -> dict:
    order = {"id": oid, "status": rng.choice(STATUSES), "total": rng.randrange(100, 20001, 10),
             "items": [{"sku": s, "qty": rng.randint(1, 5)} for s in rng.sample(SKUS, rng.randint(1, 5))]}
    extras = [("discount", rng.choice((0, 5, 10, 15))), ("gift", rng.choice((True, False))),
              ("coupon", rng.choice(("SALE10", "NEW", None))), ("weight", round(rng.uniform(0.2, 9.9), 1)),
              ("zip", str(rng.randint(100000, 999999))), ("delivery_days", rng.randint(1, 9))]
    for k, v in rng.sample(extras, rng.randint(2, 4)):
        order[k] = v  # число-строка "zip" и логическое gift — не числа
    return order


@family(code="sk.be.json_count_fields", specialization=SPEC, area="api", level=2, fmt="calc",
        space_size=900 * 2000**3 * 2, median_time_s=55)
def json_count_fields(rng: random.Random) -> Generated:
    ids = rng.sample(range(100, 1000), rng.randint(2, 3))
    doc = {"orders": [_order(rng, i) for i in ids], "page": rng.randint(1, 9)}
    order = rng.choice(doc["orders"])
    if rng.random() < 0.5:
        text = f"Сколько элементов в массиве items у заказа с id {order['id']}?"
        answer = len(order["items"])
    else:
        text = (f"Сколько полей с числовыми значениями (number в JSON) у заказа с id {order['id']}? "
                "Вложенные объекты и массивы не учитываются.")
        answer = sum(isinstance(v, int | float) and not isinstance(v, bool) for v in order.values())
    return Generated("number", Prompt(text=text, code=json.dumps(doc, ensure_ascii=False, indent=2), language="json",
                                      answer_hint="Целое число"), answer, ("json_structure",))


# --- sk.be.basic_auth_header ------------------------------------------------------------------
LOGINS = ("anna", "boris", "admin", "ci", "bot", "vera", "gleb", "ops", "dev", "test")
PASSWORDS = ("qwe", "s3cr", "pass1", "k9x", "abc42", "zz7", "hello", "m0on", "ru24", "pw8")


def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


@family(code="sk.be.basic_auth_header", specialization=SPEC, area="http", level=2, fmt="mcq",
        space_size=len(LOGINS) * 1000 * len(PASSWORDS) * SHUFFLES, median_time_s=40)
def basic_auth_header(rng: random.Random) -> Generated:
    """Base64 считает код: кандидат выбирает схему и то, что кодируется (login:password), — без утилит."""
    login = f"{rng.choice(LOGINS)}{rng.randint(0, 999)}"
    password = rng.choice(PASSWORDS)
    return mcq(rng, f"Клиент обращается к API с Basic-аутентификацией: логин {login}, пароль {password}. Какой "
                    "заголовок Authorization он отправит?",
               f"Basic {_b64(f'{login}:{password}')}",
               (f"Basic {login}:{password}", f"Bearer {_b64(f'{login}:{password}')}", f"Basic {_b64(login)}"),
               radicals=("basic_auth", 4))


# --- sk.be.retry_after_seconds ----------------------------------------------------------------
@family(code="sk.be.retry_after_seconds", specialization=SPEC, area="http", level=3, fmt="calc",
        space_size=365 * 86400 * 3600 * 2, median_time_s=60)
def retry_after_seconds(rng: random.Random) -> Generated:
    date = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=rng.randrange(365 * 86400))
    wait = rng.randint(5, 3600)
    if rng.random() < 0.5:
        retry = str(wait)
    else:
        retry = format_datetime(date + timedelta(seconds=wait), usegmt=True)
    code = "\n".join(["HTTP/1.1 429 Too Many Requests", f"Date: {format_datetime(date, usegmt=True)}",
                      f"Retry-After: {retry}", "Content-Type: application/json"])
    return Generated("number", Prompt(
        text="Через сколько секунд после получения ответа клиенту можно повторить запрос?", code=code,
        language="http", answer_hint="Целое число секунд"), wait, ("retry_after",))


# --- sk.be.backoff_total_wait -----------------------------------------------------------------
BASES = (0.5, 1, 2, 3)
MULTIPLIERS = (2, 3)
CAPS = (10, 20, 30, 60)


@family(code="sk.be.backoff_total_wait", specialization=SPEC, area="api", level=3, fmt="calc",
        space_size=len(BASES) * len(MULTIPLIERS) * len(CAPS) * 5 * len(SERVICES) * len(RESOURCES), median_time_s=70)
def backoff_total_wait(rng: random.Random) -> Generated:
    b, m, c, k = rng.choice(BASES), rng.choice(MULTIPLIERS), rng.choice(CAPS), rng.randint(3, 7)
    total = sum(min(b * m**i, c) for i in range(k))
    text = (f"Клиент сервиса {rng.choice(SERVICES)} повторяет неудачный запрос к /{rng.choice(RESOURCES)} с "
            f"экспоненциальной задержкой: base = {b:g} с, множитель {m}, потолок {c} с. Перед первой повторной "
            f"попыткой ждёт base, перед каждой следующей — в {m} раза дольше, но не дольше потолка. Сколько секунд "
            f"суммарно клиент проведёт в ожидании до {k}-й повторной попытки включительно?")
    return Generated("number", Prompt(text=text, answer_hint="Число секунд, например 15 или 7.5"), total,
                     ("exponential_backoff",))


# --- sk.be.compatible_change ------------------------------------------------------------------
API_FIELDS = ("email", "phone", "address", "status", "amount", "comment", "deadline", "priority", "owner_id", "tags")
TYPE_CHANGES = (("number", "string"), ("string", "number"), ("string", "array"), ("boolean", "string"))


@family(code="sk.be.compatible_change", specialization=SPEC, area="api", level=3, fmt="mcq",
        space_size=len(RESOURCES) * math.perm(len(API_FIELDS), 4) * len(TYPE_CHANGES) * SHUFFLES, median_time_s=50)
def compatible_change(rng: random.Random) -> Generated:
    res = rng.choice(RESOURCES)
    new, old, req, typed = rng.sample(API_FIELDS, 4)
    t1, t2 = rng.choice(TYPE_CHANGES)
    return mcq(rng, f"Публичным API /{res} пользуются внешние клиенты. Какое изменение их не сломает?",
               f"добавить в ответ необязательное поле {new}",
               (f"переименовать в ответе поле {old} в {old}_value", f"сделать поле {req} в запросе обязательным",
                f"сменить тип поля {typed} с {t1} на {t2}"))


# --- sk.be.grpc_to_http_status ----------------------------------------------------------------
GRPC_HTTP = {"NOT_FOUND": "404", "INVALID_ARGUMENT": "400", "UNAUTHENTICATED": "401", "PERMISSION_DENIED": "403",
             "UNAVAILABLE": "503", "DEADLINE_EXCEEDED": "504", "ALREADY_EXISTS": "409", "RESOURCE_EXHAUSTED": "429"}
RPC_METHODS = ("GetUser", "CreateOrder", "ListItems", "UpdateProfile", "DeleteFile", "Pay", "Search", "Book",
               "Refund", "Upload")


@family(code="sk.be.grpc_to_http_status", specialization=SPEC, area="api", level=4, fmt="mcq",
        space_size=len(GRPC_HTTP) * math.comb(len(GRPC_HTTP) - 1, 3) * len(SERVICES) * len(RPC_METHODS) * SHUFFLES,
        median_time_s=50)
def grpc_to_http_status(rng: random.Random) -> Generated:
    grpc = rng.choice(sorted(GRPC_HTTP))
    key = GRPC_HTTP[grpc]
    others = rng.sample(sorted(v for v in GRPC_HTTP.values() if v != key), 3)
    return mcq(rng, f"Сервис {rng.choice(SERVICES)} за grpc-gateway на вызов {rng.choice(RPC_METHODS)} вернул статус "
                    f"{grpc}. Какой HTTP-код получит REST-клиент?", key, others)
