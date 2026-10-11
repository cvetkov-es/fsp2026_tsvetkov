import itertools
import json
import math
import random

from app.assessment.bank.base import (
    SHUFFLES,
    Generated,
    Prompt,
    family,
    mcq,
    rows_space,
    template_fields,
)

SCENARIOS = (
    ("Клиент отправил POST /{path}, и сервер создал {res}. Какой код ответа корректнее всего?",
     201, (200, 202, 204)),
    ("Пользователь аутентифицирован, но не имеет прав на изменение ({method} /{path}/{id}). "
     "Какой код ответа?", 403, (401, 400, 409)),
    ("Запрос {method} /{path}/{id} пришёл без токена доступа, а ресурс требует аутентификации. "
     "Какой код ответа?", 401, (403, 400, 407)),
    ("DELETE /{path}/{id} успешно удалил {res}, тело ответа не нужно. Какой код ответа?",
     204, (200, 202, 410)),
    ("POST /{path} пытается создать {res} с уже существующим уникальным ключом. Какой код ответа?",
     409, (404, 412, 500)),
    ("Тело запроса {method} /{path}/{id} — корректный JSON, но поле amount отрицательное, "
     "а это запрещено бизнес-правилом. Какой код ответа?", 422, (404, 405, 415)),
    ("Клиент превысил лимит запросов к /{path}. Какой код ответа?", 429, (503, 403, 400)),
    ("Клиент отправил {method} /{path}/{id} с Content-Type: text/plain, а API принимает только "
     "JSON. Какой код ответа?", 415, (404, 406, 422)),
)
RESOURCES = (("orders", "заказ"), ("users", "пользователя"), ("payments", "платёж"),
             ("documents", "документ"), ("projects", "проект"), ("tickets", "заявку"),
             ("invoices", "счёт"), ("courses", "курс"), ("teams", "команду"),
             ("reports", "отчёт"), ("devices", "устройство"), ("bookings", "бронирование"),
             ("contracts", "договор"), ("vehicles", "автомобиль"), ("warehouses", "склад"),
             ("subscriptions", "подписку"), ("vacancies", "вакансию"), ("reviews", "отзыв"),
             ("coupons", "купон"), ("shipments", "отправку"))
METHODS = ("PUT", "PATCH")
API_VERSIONS = 5
MAX_ID = 9999


def _space_size() -> int:
    """Честный подсчёт: множители только за те подстановки, что есть в шаблоне сценария."""
    total = 0
    for template, _, _ in SCENARIOS:
        used = template_fields(template)
        n = API_VERSIONS * len(RESOURCES)  # path и res выбираются вместе
        n *= len(METHODS) if "method" in used else 1
        n *= MAX_ID if "id" in used else 1
        total += n * SHUFFLES
    return total


@family(code="be.http.status_code", specialization="backend", area="http", level=1,
        fmt="mcq", space_size=_space_size(),
        median_time_s=30)
def status_code(rng: random.Random) -> Generated:
    template, correct, distractors = rng.choice(SCENARIOS)
    path, res = rng.choice(RESOURCES)
    text = template.format(path=f"api/v{rng.randint(1, API_VERSIONS)}/{path}", res=res,
                           method=rng.choice(METHODS), id=rng.randint(1, MAX_ID))
    return mcq(rng, text, str(correct), [str(d) for d in distractors])


# ---------------------------------------------------------------------------
# План 03b: наполнение области http
# ---------------------------------------------------------------------------
PATHS = tuple(p for p, _ in RESOURCES)
PATH_VARIANTS = len(PATHS) * API_VERSIONS  # «api/vN/ресурс» — одна подстановка {path}


def _path(rng: random.Random) -> str:
    return f"api/v{rng.randint(1, API_VERSIONS)}/{rng.choice(PATHS)}"


# --- be.http.method_idempotency -------------------------------------------------
SUB_RESOURCES = ("comments", "items", "attachments", "events", "notes")
MAX_PAGE = 20
GET_SHAPES = ("item", "page", "collection", "sub_collection")
# число вариантов пути каждой формы: элемент /{id}, вложенная коллекция /{id}/{sub}, её элемент
ITEM_PATHS = MAX_ID
SUB_COLLECTION_PATHS = MAX_ID * len(SUB_RESOURCES)
SUB_ITEM_PATHS = SUB_COLLECTION_PATHS * MAX_ID


@family(code="be.http.method_idempotency", specialization="backend", area="http", level=1,
        fmt="mcq", median_time_s=30,
        space_size=len(PATHS) * API_VERSIONS * (1 + SUB_COLLECTION_PATHS)
        * (ITEM_PATHS + (MAX_PAGE - 1) + 1 + SUB_COLLECTION_PATHS)
        * (ITEM_PATHS + SUB_ITEM_PATHS) ** 2 * SHUFFLES)
def method_idempotency(rng: random.Random) -> Generated:
    base = f"/api/v{rng.randint(1, API_VERSIONS)}/{rng.choice(PATHS)}"

    def item() -> str:
        return f"{base}/{rng.randint(1, MAX_ID)}"

    def sub_collection() -> str:
        return f"{item()}/{rng.choice(SUB_RESOURCES)}"

    def sub_item() -> str:
        return f"{sub_collection()}/{rng.randint(1, MAX_ID)}"

    # формы путей меняются у всех методов, чтобы ключ (POST) не выделялся ни длиной, ни числом сегментов
    post = f"POST {sub_collection() if rng.random() < 0.5 else base}"
    shape = rng.choice(GET_SHAPES)
    get = "GET " + {"item": item, "page": lambda: f"{base}?page={rng.randint(2, MAX_PAGE)}",
                    "collection": lambda: base, "sub_collection": sub_collection}[shape]()
    put = f"PUT {sub_item() if rng.random() < 0.5 else item()}"
    delete = f"DELETE {sub_item() if rng.random() < 0.5 else item()}"
    return mcq(
        rng,
        "Мобильный клиент при сбое сети автоматически повторяет запрос. "
        "Какой из запросов при такой повторной отправке может создать дубликат ресурса?",
        post, (get, put, delete))


# --- be.http.cache_control_header -----------------------------------------------
CACHE_AGES = (60, 300, 600, 900)
# (шаблоны, правильное значение, пул дистракторов); «=N» — подставляется max-age/s-maxage
CACHE_ROWS = (
    (("Ответ на GET /{path} содержит персональные данные пользователя. Их нельзя сохранять ни в каком "
      "кэше: ни в кэше браузера, ни в общих кэшах (прокси, CDN). Какое значение заголовка Cache-Control "
      "нужно указать?",
      "Ответ на GET /{path} содержит платёжные реквизиты. По требованию безопасности копию ответа нельзя "
      "записывать ни в один кэш, включая кэш браузера. Какое значение заголовка Cache-Control подойдёт?",
      "Эндпоинт GET /{path} возвращает медицинские сведения. Хранить копию ответа где бы то ни было "
      "(в браузере, на прокси, в CDN) запрещено. Какое значение Cache-Control нужно указать?"),
     "no-store", ("no-cache", "private", "public", "max-age=N")),
    (("Для GET /{path} нужно, чтобы кэши хранили копию ответа, а перед каждым её использованием "
      "перепроверяли актуальность на сервере (например, по ETag). Какое значение Cache-Control "
      "нужно указать?",
      "Данные из GET /{path} должны оставаться в кэше, но показывать копию без согласования с сервером "
      "нельзя: нужно, чтобы перед каждым показом она проверялась на актуальность. Какое значение "
      "Cache-Control подходит?",
      "Требуется, чтобы клиенты хранили ответ GET /{path} и каждый раз спрашивали у сервера, не "
      "изменился ли он, прежде чем отдать копию. Какое значение Cache-Control нужно указать?"),
     "no-cache", ("no-store", "public", "private", "max-age=N")),
    (("Ответ на GET /{path} зависит от текущего пользователя. Нужно, чтобы браузер этого пользователя "
      "сохранял ответ и переиспользовал его, а общие кэши (прокси, CDN) его не хранили. Какое значение "
      "Cache-Control нужно указать?",
      "Страница GET /{path} персонализирована: требуется, чтобы браузер самого пользователя кэшировал "
      "её, а прокси и CDN не сохраняли. Какое значение Cache-Control подходит?",
      "Ответ GET /{path} предназначен одному пользователю: нужно, чтобы его кэшировал браузер, а кэши "
      "между клиентом и сервером — нет. Какое значение Cache-Control нужно указать?"),
     "private", ("public", "no-store", "s-maxage=N", "max-age=N")),
)


def _cache_space() -> int:
    total = 0
    for templates, _, pool in CACHE_ROWS:
        for combo in itertools.combinations(pool, 3):
            total += len(templates) * PATH_VARIANTS * len(CACHE_AGES) ** sum("=N" in c for c in combo)
    return total * SHUFFLES


@family(code="be.http.cache_control_header", specialization="backend", area="http", level=2,
        fmt="mcq", space_size=_cache_space(), median_time_s=45)
def cache_control_header(rng: random.Random) -> Generated:
    templates, correct, pool = rng.choice(CACHE_ROWS)
    text = rng.choice(templates).format(path=_path(rng))
    chosen = rng.sample(pool, 3)
    distractors = [d.replace("=N", f"={rng.choice(CACHE_AGES)}") for d in chosen]
    return mcq(rng, text, correct, distractors)


# --- be.http.pagination_math ----------------------------------------------------
PAGE_LIMITS = (10, 20, 25, 50, 100)
MIN_TOTAL, MAX_TOTAL = 50, 5000


def _pagination_space() -> int:
    offset_variants = sum(-(-n // lim) for n in range(MIN_TOTAL, MAX_TOTAL + 1) for lim in PAGE_LIMITS)
    plain = (MAX_TOTAL - MIN_TOTAL + 1) * len(PAGE_LIMITS)
    return len(PATHS) * (offset_variants + 2 * plain)


@family(code="be.http.pagination_math", specialization="backend", area="http", level=2,
        fmt="calc", space_size=_pagination_space(), median_time_s=50)
def pagination_math(rng: random.Random) -> Generated:
    n = rng.randint(MIN_TOTAL, MAX_TOTAL)
    limit = rng.choice(PAGE_LIMITS)
    pages = -(-n // limit)
    res = rng.choice(PATHS)
    intro = f"Всего объектов в коллекции /api/{res}: {n}. "
    kind = rng.choice(("offset", "count", "last"))
    if kind == "offset":
        k = rng.randint(1, pages)
        text = (intro + f"Клиент запрашивает их страницами: GET /api/{res}?limit={limit}&offset=… "
                "Нумерация страниц идёт с единицы, первая страница начинается с offset=0. "
                f"Какой offset нужно передать, чтобы получить страницу {k}?")
        answer = (k - 1) * limit
    elif kind == "count":
        text = (intro + f"Один запрос с limit={limit} возвращает за раз не больше объектов, чем указано в limit. "
                "Сколько запросов нужно сделать, чтобы получить все объекты (страницы идут подряд, "
                "последняя может быть неполной)?")
        answer = pages
    else:
        text = (intro + f"Клиент запрашивает их страницами с limit={limit}, страницы идут подряд "
                "без пропусков. Сколько объектов будет на последней странице?")
        answer = n - (pages - 1) * limit
    return Generated("number", Prompt(text=text, answer_hint="Целое число"), answer, ("pagination",))


# --- be.http.gateway_status -----------------------------------------------------
GATEWAYS = ("nginx", "envoy", "haproxy", "traefik", "kong", "istio-gateway", "apisix", "api-gateway")
SERVICES = ("orders-service", "billing-service", "auth-service", "catalog-service", "search-service",
            "profile-service", "notify-service", "report-service", "ledger-service", "media-service",
            "pricing-service", "stock-service", "delivery-service", "support-service", "export-service",
            "import-service", "points-service", "booking-service", "chat-service", "audit-service")
UPSTREAM_TIMEOUTS = (5, 10, 15, 20, 30, 60)
REQ_METHODS = ("GET", "POST", "PUT")
_GW_TAIL = "Какой код ответа корректен?"
GATEWAY_ROWS = (
    (("Запрос {req} прошёл через шлюз {gw} к сервису {svc}. Сервис не прислал ответ за отведённое время "
      "({t} с), и шлюз прервал ожидание по таймауту. " + _GW_TAIL,
      "Шлюз {gw} проксирует {req} в сервис {svc}. Сервис завис и не ответил до истечения таймаута "
      "в {t} с. " + _GW_TAIL),
     "504", ("500", "502", "503")),
    (("Запрос {req} прошёл через шлюз {gw} к сервису {svc}. Сервис ответил, но прислал некорректный ответ: "
      "шлюз не смог разобрать его как HTTP-ответ. " + _GW_TAIL,
      "Шлюз {gw} проксирует {req} в сервис {svc}. Соединение установилось, но сервис прислал шлюзу "
      "некорректный ответ (оборванные заголовки). " + _GW_TAIL),
     "502", ("500", "503", "504")),
    (("Запрос {req} идёт через шлюз {gw} к сервису {svc}. Сервис выведен на обслуживание и сообщает, "
      "что временно не принимает запросы; клиенту предлагается повторить позже. " + _GW_TAIL,
      "Сервис {svc} перегружен и временно не может обработать {req} (шлюз {gw}); клиенту стоит "
      "повторить позже. " + _GW_TAIL),
     "503", ("500", "502", "504")),
    (("Сервис {svc} получил {req}, но в его коде возникло необработанное исключение. Шлюз {gw} передал "
      "клиенту ответ сервиса. " + _GW_TAIL,
      "Обработчик {req} в сервисе {svc} упал с необработанным исключением; ответ сервиса дошёл до клиента "
      "через шлюз {gw}. " + _GW_TAIL),
     "500", ("502", "503", "504")),
)
GATEWAY_SIZES = {"req": len(REQ_METHODS) * PATH_VARIANTS, "gw": len(GATEWAYS), "svc": len(SERVICES),
                 "t": len(UPSTREAM_TIMEOUTS)}


@family(code="be.http.gateway_status", specialization="backend", area="http", level=2,
        fmt="mcq", space_size=rows_space(GATEWAY_ROWS, GATEWAY_SIZES), median_time_s=50)
def gateway_status(rng: random.Random) -> Generated:
    templates, correct, distractors = rng.choice(GATEWAY_ROWS)
    text = rng.choice(templates).format(
        req=f"{rng.choice(REQ_METHODS)} /{_path(rng)}", gw=rng.choice(GATEWAYS),
        svc=rng.choice(SERVICES), t=rng.choice(UPSTREAM_TIMEOUTS))
    return mcq(rng, text, correct, distractors)


# --- be.http.idempotency_key_retry ----------------------------------------------
IDEMPOTENT_OPS = (("payments", "создание платежа"), ("orders", "оформление заказа"),
                  ("transfers", "перевод между счетами"), ("bookings", "бронирование номера"),
                  ("invoices", "выставление счёта"), ("subscriptions", "оформление подписки"))
KEY_SPACE = 16**8


def _idempotent_request(rng: random.Random) -> str:
    path, what = rng.choice(IDEMPOTENT_OPS)
    return f"POST /api/v{rng.randint(1, API_VERSIONS)}/{path} ({what})"


def _hex8(rng: random.Random) -> str:
    return f"{rng.randrange(KEY_SPACE):08x}"


IDEMPOTENCY_ROWS = (
    (("Клиент отправил {req} с заголовком Idempotency-Key: {key}. Ответ не пришёл из-за сетевого таймаута, "
      "и клиент повторил запрос: тот же ключ, то же тело. К этому моменту первый запрос уже успешно "
      "выполнен и его результат сохранён. Как сервер должен обработать повтор?",
      "Сервис принимает {req} с заголовком Idempotency-Key: {key}. Из-за обрыва соединения клиент не "
      "получил ответ и отправил идентичный запрос с тем же ключом. Первый запрос завершился успешно, "
      "результат сохранён на сервере. Как сервер должен обработать повтор?"),
     "Вернуть сохранённый ответ на первый запрос, не выполняя операцию снова",
     ("Выполнить операцию ещё раз и вернуть клиенту результат нового выполнения",
      "Отклонить повтор с кодом 409 Conflict, потому что ключ уже был использован",
      "Отклонить повтор с кодом 400, потому что такой запрос уже приходил")),
    (("Мобильное приложение послало {req} с Idempotency-Key: {key}, но не дождалось ответа и через "
      "несколько секунд отправило такой же запрос с тем же ключом. Первый запрос к тому времени "
      "завершился успешно, результат записан. Что должен сделать сервер с повтором?",
      "Для {req} клиент указал Idempotency-Key: {key}. После таймаута он повторил запрос: тело "
      "идентично, ключ тот же. Первое выполнение уже завершено, результат сохранён. Что должен сделать "
      "сервер с повтором?"),
     "Отдать клиенту результат первого выполнения без повторного исполнения операции",
     ("Исполнить операцию заново, потому что первый ответ клиент так и не получил",
      "Всегда отвечать кодом 409 Conflict на любой повтор запроса с тем же ключом",
      "Ответить кодом 400 Bad Request и потребовать от клиента сгенерировать новый уникальный ключ")),
)


@family(code="be.http.idempotency_key_retry", specialization="backend", area="http", level=3,
        fmt="mcq", median_time_s=70,
        space_size=rows_space(IDEMPOTENCY_ROWS, {"req": len(IDEMPOTENT_OPS) * API_VERSIONS, "key": KEY_SPACE}))
def idempotency_key_retry(rng: random.Random) -> Generated:
    templates, correct, distractors = rng.choice(IDEMPOTENCY_ROWS)
    text = rng.choice(templates).format(req=_idempotent_request(rng), key=_hex8(rng))
    return mcq(rng, text, correct, distractors)


# --- be.http.put_vs_patch -------------------------------------------------------
ENTITIES = (
    ("users", ("name", "email", "phone", "city", "role", "locale", "status")),
    ("orders", ("status", "amount", "currency", "address", "comment", "priority", "channel")),
    ("products", ("title", "price", "stock", "category", "brand", "weight", "description")),
    ("customers", ("name", "email", "segment", "manager", "discount", "language", "country")),
    ("tickets", ("title", "status", "assignee", "priority", "queue", "deadline", "labels")),
    ("employees", ("name", "position", "department", "grade", "salary", "office", "manager")),
    ("vehicles", ("plate", "model", "color", "mileage", "driver", "status", "region")),
    ("projects", ("title", "owner", "budget", "stage", "deadline", "visibility", "tags")),
)
PUT_TAIL = "Что по семантике PUT произойдёт с остальными полями ресурса?"
PUT_PATCH_ROWS = (
    (("Ресурс {res} содержит поля: {all}. Клиент отправил PUT {res}. Поля в теле запроса: {sent}. "
      + PUT_TAIL,
      "У ресурса {res} есть поля: {all}. Клиент выполнил PUT {res}. Поля в теле запроса: {sent}. "
      + PUT_TAIL),
     "Будут сброшены: PUT заменяет ресурс целиком переданным представлением",
     ("Останутся прежними: PUT изменяет только те поля, которые переданы",
      "Запрос будет отклонён: PUT обязан содержать значения всех полей",
      "Сервер создаст новый ресурс с новым id: PUT всегда порождает отдельную запись")),
    (("Ресурс {res} содержит поля: {all}. Клиент отправил PATCH {res} в формате JSON Merge Patch "
      "(RFC 7396). Поля в теле запроса: {sent}. Что произойдёт с остальными полями ресурса?",
      "У ресурса {res} есть поля: {all}. Клиент выполнил PATCH {res} (JSON Merge Patch, RFC 7396). "
      "Поля в теле запроса: {sent}. Что произойдёт с остальными полями ресурса?"),
     "Останутся прежними: PATCH изменяет только поля, переданные в запросе",
     ("Будут сброшены: PATCH заменяет ресурс целиком переданным представлением",
      "Запрос будет отклонён: PATCH обязан содержать значения всех полей",
      "Сервер вернёт 405: PATCH нельзя применять к существующему ресурсу")),
)


def _put_patch_space() -> int:
    per_entity = sum(math.perm(7, n) * math.comb(n, 2) for n in (4, 5))
    return len(ENTITIES) * API_VERSIONS * MAX_ID * per_entity * 2 * len(PUT_PATCH_ROWS) * SHUFFLES


@family(code="be.http.put_vs_patch", specialization="backend", area="http", level=3,
        fmt="mcq", space_size=_put_patch_space(), median_time_s=70)
def put_vs_patch(rng: random.Random) -> Generated:
    templates, correct, distractors = rng.choice(PUT_PATCH_ROWS)
    name, pool = rng.choice(ENTITIES)
    n = rng.randint(4, 5)
    fields = rng.sample(pool, n)
    sent = sorted(rng.sample(range(n), 2))
    text = rng.choice(templates).format(
        res=f"/api/v{rng.randint(1, API_VERSIONS)}/{name}/{rng.randint(1, MAX_ID)}",
        all=", ".join(fields), sent=", ".join(fields[i] for i in sent))
    return mcq(rng, text, correct, distractors)


# --- be.http.cors_preflight -----------------------------------------------------
CORS_DOMAINS = ("api.shop.example", "gateway.bank.example", "data.school.example", "svc.travel.example",
                "api.market.example", "core.clinic.example", "rest.cargo.example", "api.cinema.example",
                "backend.food.example", "api.studio.example", "hub.media.example", "api.fleet.example")
# Простой запрос по Fetch Standard: GET/HEAD/POST, только CORS-безопасные заголовки,
# Content-Type только application/x-www-form-urlencoded, multipart/form-data или text/plain.
CORS_SIMPLE = (
    "GET {url} (Accept: text/html)",
    "GET {url} (Accept: application/json)",
    "GET {url} (Accept-Language: ru)",
    "HEAD {url} (Accept: */*)",
    "POST {url} (Content-Type: application/x-www-form-urlencoded)",
    "POST {url} (Content-Type: multipart/form-data)",
    "POST {url} (Content-Type: text/plain)",
)
# Непростой: метод вне GET/HEAD/POST, либо заголовок вне безопасного списка, либо иной Content-Type.
CORS_NON_SIMPLE = (
    "PUT {url} (Content-Type: text/plain)",
    "DELETE {url} (Accept: application/json)",
    "GET {url} (Authorization: Bearer {tok})",
    "GET {url} (X-Request-Id: {tok})",
    "POST {url} (Content-Type: application/json)",
    "PATCH {url} (Content-Type: multipart/form-data)",
)
_CORS_SAMPLE = {"url": "https://api.shop.example/api/v1/orders", "tok": "ab12cd34"}
CORS_SIMPLE_EXAMPLES = tuple(t.format(**_CORS_SAMPLE) for t in CORS_SIMPLE)
CORS_NON_SIMPLE_EXAMPLES = tuple(t.format(**_CORS_SAMPLE) for t in CORS_NON_SIMPLE)


@family(code="be.http.cors_preflight", specialization="backend", area="http", level=3,
        fmt="mcq", median_time_s=75,
        space_size=len(CORS_NON_SIMPLE) * math.comb(len(CORS_SIMPLE), 3)
        * (len(CORS_DOMAINS) * PATH_VARIANTS) ** 4 * SHUFFLES)
def cors_preflight(rng: random.Random) -> Generated:
    templates = [rng.choice(CORS_NON_SIMPLE), *rng.sample(CORS_SIMPLE, 3)]
    options = [t.format(url=f"https://{rng.choice(CORS_DOMAINS)}/{_path(rng)}", tok=_hex8(rng))
               for t in templates]
    return mcq(
        rng,
        "Страница https://app.example.com через fetch() из JavaScript отправляет кросс-доменные запросы. "
        "Перед каким из запросов браузер сначала выполнит preflight-запрос OPTIONS?",
        options[0], options[1:])


# --- be.http.breaking_change ----------------------------------------------------
# поле -> (генератор значения, фраза о смене типа)
FIELD_SPECS = {
    "id": (lambda r: r.randint(1, MAX_ID), "с числа на строку"),
    "name": (lambda r: r.choice(("Анна", "Игорь", "Мария", "Олег", "Светлана", "Пётр")),
             "со строки на число"),
    "email": (lambda r: f"user{r.randint(1, MAX_ID)}@example.com", "со строки на число"),
    "status": (lambda r: r.choice(("active", "pending", "closed", "blocked")), "со строки на число"),
    "price": (lambda r: r.randint(100, MAX_ID), "с числа на строку"),
    "created_at": (lambda r: f"2026-{r.randint(1, 12):02d}-{r.randint(1, 28):02d}", "со строки на число"),
    "is_active": (lambda r: r.random() < 0.5, "с boolean на строку"),
    "quantity": (lambda r: r.randint(1, 50), "с числа на строку"),
    "tags": (lambda r: r.sample(("new", "vip", "promo", "beta", "eu"), 2), "с массива на строку"),
    "balance": (lambda r: r.randint(0, MAX_ID), "с числа на строку"),
}
RENAMES = {"id": "uid", "name": "full_name", "email": "contact_email", "status": "state", "price": "amount",
           "created_at": "created", "is_active": "active", "quantity": "qty", "tags": "labels",
           "balance": "funds"}
EXTRA_FIELDS = ("note", "source", "locale", "priority", "region", "comment")
EXTRA_ENDPOINTS = ("stats", "history", "summary", "export")
EXTRA_HEADERS = ("X-Request-Id", "X-Trace-Id", "X-Region")
EXTRA_PARAMS = ("fields", "locale", "expand", "include")
_KEEP = "остальное не менять"
NON_BREAKING_KINDS = 7  # число разных безопасных изменений в _non_breaking_pool


def _breaking_space() -> int:
    schemas = sum(math.perm(len(FIELD_SPECS), n) * 3 * n for n in (4, 5, 6))
    # нижняя оценка: тройка безопасных изменений и порядок вариантов; значения в JSON не считаем
    return schemas * math.comb(NON_BREAKING_KINDS, 3) * PATH_VARIANTS * MAX_ID * SHUFFLES


def _non_breaking_pool(rng: random.Random, path: str, fields: list[str]) -> list[str]:
    """Безопасные для читающего клиента изменения (клиенты игнорируют незнакомые поля и заголовки).

    Не больше двух вариантов начинаются одним глаголом: три дистрактора с общим первым словом
    выдавали бы ключ, который начинается иначе."""
    return [
        f"Расширить ответ новым необязательным полем {rng.choice(EXTRA_FIELDS)}, {_KEEP}",
        f"Открыть новый эндпоинт GET /{path}/{rng.choice(EXTRA_ENDPOINTS)}, {_KEEP}",
        f"Добавить в каждый ответ новый заголовок {rng.choice(EXTRA_HEADERS)}, {_KEEP}",
        f"Изменить порядок ключей в JSON-объекте ответа, {_KEEP}",
        f"Добавить необязательный query-параметр {rng.choice(EXTRA_PARAMS)} в запрос, {_KEEP}",
        f"Переименовать колонку {rng.choice(fields)} в таблице БД, JSON-ответ не менять",
        "Убрать из ответа заголовок X-Powered-By, который клиенты не читают",
    ]


@family(code="be.http.breaking_change", specialization="backend", area="http", level=4,
        fmt="mcq", space_size=_breaking_space(), median_time_s=100)
def breaking_change(rng: random.Random) -> Generated:
    fields = rng.sample(list(FIELD_SPECS), rng.randint(4, 6))
    schema = {f: FIELD_SPECS[f][0](rng) for f in fields}
    target = rng.choice(fields)
    path = _path(rng)
    correct = rng.choice((
        f"Удалить поле {target} из ответа сервера целиком, {_KEEP}",
        f"Переименовать поле {target} в {RENAMES[target]} в ответе сервера, {_KEEP}",
        f"Сменить тип поля {target} {FIELD_SPECS[target][1]}, {_KEEP}",
    ))
    distractors = rng.sample(_non_breaking_pool(rng, path, fields), 3)
    return mcq(
        rng,
        f"Эндпоинт GET /{path}/{rng.randint(1, MAX_ID)} возвращает JSON (пример ниже). Клиенты "
        "читают поля ответа по текущей схеме и игнорируют незнакомые поля и заголовки. Какое из "
        "изменений нарушит обратную совместимость, то есть сломает существующих клиентов?",
        correct, distractors, code=json.dumps(schema, ensure_ascii=False, indent=2), language="json")


# --- be.http.conditional_request ------------------------------------------------
WRITE_METHODS = ("PUT", "PATCH", "DELETE")  # исход успеха задаётся текстом: 200 с телом или 204 без тела
ETAG_SPACE = 16**8
ETAG_NEAR = 8 * 15  # «почти совпавших» ETag на данный: один знак из 8 заменён одним из 15 других
ETAG_PAIRS = ETAG_SPACE * ETAG_NEAR  # второй ETag отличается от первого хотя бы одним знаком (нижняя оценка)
STATUS_OPTIONS = ("200", "204", "304", "412")
# веса ветвей: у GET 304 и 200 уравновешены и при одном ETag, и при списке из двух; у записи 412 и 200/204 —
# тоже, чтобы ни метод, ни длина списка не выдавали ключ («GET → 304», «DELETE → 412», «два ETag → 304»)
CONDITIONAL_CASES = {"get_match": 1, "get_match_in_list": 1, "get_nomatch": 1, "get_nomatch_in_list": 1,
                     "write_nomatch": 2, "write_match": 2}


def _other_etag(rng: random.Random, current: str) -> str:
    if rng.random() < 0.5:  # «почти совпал»: отличается одним знаком
        i = rng.randrange(8)
        digit = rng.choice([c for c in "0123456789abcdef" if c != current[i]])
        return current[:i] + digit + current[i + 1:]
    other = _hex8(rng)
    return other if other != current else _other_etag(rng, current)


@family(code="be.http.conditional_request", specialization="backend", area="http", level=4,
        fmt="mcq", median_time_s=100,
        # ветви: get_match, get_match_in_list (порядок в списке), get_nomatch, get_nomatch_in_list,
        # write_nomatch (метод × фраза о теле), write_match (метод × исход 200/204, заданный фразой)
        space_size=PATH_VARIANTS * MAX_ID * (ETAG_SPACE + 2 * ETAG_PAIRS + ETAG_PAIRS
                                             + ETAG_PAIRS * ETAG_NEAR
                                             + len(WRITE_METHODS) * 2 * ETAG_PAIRS
                                             + len(WRITE_METHODS) * 2 * ETAG_SPACE) * SHUFFLES)
def conditional_request(rng: random.Random) -> Generated:
    current = _hex8(rng)
    case = rng.choices(tuple(CONDITIONAL_CASES), weights=tuple(CONDITIONAL_CASES.values()))[0]
    other = _other_etag(rng, current)
    if case == "get_match":
        method, header, values, status = "GET", "If-None-Match", [current], "304"
    elif case == "get_match_in_list":
        method, header, status = "GET", "If-None-Match", "304"
        values = [current, other] if rng.random() < 0.5 else [other, current]
    elif case == "get_nomatch":
        method, header, values, status = "GET", "If-None-Match", [other], "200"
    elif case == "get_nomatch_in_list":  # два чужих ETag: длина списка не подсказывает 304
        second = _other_etag(rng, current)
        while second == other:
            second = _other_etag(rng, current)
        method, header, values, status = "GET", "If-None-Match", [other, second], "200"
    elif case == "write_nomatch":
        method, header, values, status = rng.choice(WRITE_METHODS), "If-Match", [other], "412"
    else:  # совпавший If-Match (и у DELETE): код успеха однозначно задан фразой о теле ответа
        method, header, values = rng.choice(WRITE_METHODS), "If-Match", [current]
        status = rng.choice(("200", "204"))
    success = ""
    if method != "GET":
        with_body = status == "200" if case == "write_match" else rng.random() < 0.5
        if method == "DELETE":  # с телом (описание результата) — 200, без тела — 204
            success = ("При успешном удалении сервер возвращает в теле ответа описание результата. "
                       if with_body else "При успешном удалении сервер отвечает без тела. ")
        else:
            success = ("При успешном изменении сервер возвращает обновлённое представление ресурса "
                       "в теле ответа. " if with_body else "При успешном изменении сервер отвечает без тела. ")
    resource = f"/{_path(rng)}/{rng.randint(1, MAX_ID)}"
    shown = ", ".join(f'"{v}"' for v in values)
    text = (f'Сервер поддерживает условные запросы по RFC 9110. Текущий ETag ресурса {resource}: "{current}". '
            f"{success}Клиент отправил {method} {resource} с заголовком {header}: {shown}. "
            "Какой код ответа вернёт сервер?")
    return mcq(rng, text, status, [s for s in STATUS_OPTIONS if s != status])


# --- be.http.token_bucket_accepts -----------------------------------------------
BUCKET_CAPACITIES = tuple(range(3, 11))
BUCKET_RATES = (1, 2)
BUCKET_GAPS = (0, 0, 0, 0, 0, 0, 1)  # интервалы между запросами; 0 даёт «пачки» запросов в одну секунду
BUCKET_LENGTHS = (10, 11, 12)


def _bucket_accepted(capacity: int, rate: int, times: list[int]) -> int:
    tokens, last, accepted = capacity, 0, 0
    for t in times:
        tokens = min(capacity, tokens + rate * (t - last))
        last = t
        if tokens >= 1:
            tokens -= 1
            accepted += 1
    return accepted


@family(code="be.http.token_bucket_accepts", specialization="backend", area="http", level=4,
        fmt="output", median_time_s=110,
        space_size=PATH_VARIANTS * len(BUCKET_CAPACITIES) * len(BUCKET_RATES) * sum(2 ** n for n in BUCKET_LENGTHS))
def token_bucket_accepts(rng: random.Random) -> Generated:
    capacity = rng.choice(BUCKET_CAPACITIES)
    rate = rng.choice(BUCKET_RATES)
    now, times = 0, []
    for _ in range(rng.choice(BUCKET_LENGTHS)):
        now += rng.choice(BUCKET_GAPS)
        times.append(now)
    text = (f"Эндпоинт /{_path(rng)} защищён ограничителем частоты, который работает по алгоритму token bucket. "
            f"Ёмкость корзины (токенов): {capacity}. Скорость пополнения (токенов в секунду): {rate}. "
            "Корзина полна в момент времени 0. Токены добавляются в целые секунды (в момент 1, 2, 3 и так далее), "
            "но не выше ёмкости. Пополнение в момент t происходит до обработки запросов, пришедших "
            "в момент t. Каждый запрос забирает один токен; если токенов нет, запрос "
            "отклоняется и ничего не забирает. Моменты поступления запросов (целые секунды) даны ниже. "
            "Сколько запросов будет принято?")
    return Generated(
        "number",
        Prompt(text=text, code=f"times = {times}", language="python", answer_hint="Целое число"),
        _bucket_accepted(capacity, rate, times), ("token_bucket",),
    )


# --- be.http.webhook_delivery ---------------------------------------------------
# согласованные тройки: (отправитель, событие, побочный эффект обработчика)
WEBHOOK_SCENES = (
    ("платёжный провайдер", "payment.succeeded", "начисляет клиенту бонусные баллы"),
    ("служба доставки", "order.shipped", "отправляет клиенту SMS с трек-номером"),
    ("банк-эквайер", "chargeback.opened", "замораживает выплату продавцу по заказу"),
    ("сервис электронной подписи", "document.signed", "переводит договор в статус «подписан»"),
    ("платёжный провайдер", "invoice.paid", "создаёт проводку в журнале учёта"),
    ("биллинговая система", "subscription.renewed", "продлевает подписку пользователя"),
)
WEBHOOK_TIMEOUTS = (5, 10, 15, 20, 30)
WEBHOOK_ROWS = (
    (("Внешний сервис ({prov}) присылает вебхук {ev} на POST /{path}; у каждого события есть уникальный "
      "id, например {evt}. Доставка гарантируется как минимум один раз (at-least-once): если ответ 2xx "
      "не получен за {t} с, провайдер повторяет вебхук. Обработчик {eff}. Из-за таймаута событие {evt} "
      "пришло дважды. Какой подход к обработчику правильный?",
      "Вы принимаете вебхуки от внешнего сервиса ({prov}): событие {ev} приходит на POST /{path} и "
      "имеет уникальный id (например, {evt}). Провайдер работает по принципу at-least-once и повторяет "
      "доставку, если 2xx не получен за {t} с. Обработчик {eff}. Событие {evt} пришло повторно. "
      "Какой подход к обработчику правильный?"),
     "Сделать обработчик идемпотентным: хранить id обработанных событий и пропускать дубли",
     ("Проверять HMAC-подпись каждого вебхука: подлинное событие дважды не придёт",
      "Принимать вебхуки только с IP-адресов провайдера: события с этих адресов дублями не бывают",
      "Отвечать кодом 500 на повторные доставки, чтобы провайдер перестал их присылать")),
    (("Сервис ({prov}) шлёт на POST /{path} вебхуки {ev}; каждое событие имеет уникальный id вида {evt}. "
      "Гарантия доставки — at-least-once: не получив 2xx за {t} с, провайдер отправляет то же событие "
      "снова. Обработчик {eff}. В журнале видно, что {evt} доставлено дважды. Как правильно "
      "спроектировать обработчик?",
      "Внешний сервис ({prov}) уведомляет ваш сервис вебхуком {ev} (POST /{path}), событие помечено "
      "уникальным id {evt}. Доставка at-least-once: если за {t} с не пришёл ответ 2xx, вебхук "
      "отправляется заново. Обработчик {eff}. Событие {evt} уже пришло второй раз. Как правильно "
      "спроектировать обработчик?"),
     "Дедуплицировать события по id: на повтор отвечать 2xx без повторной обработки",
     ("Ограничить частоту входящих вебхуков до одного в секунду и отбрасывать лишние",
      "Проверять HMAC-подпись каждого вебхука: подлинное событие дважды не придёт",
      "На повторную доставку отвечать кодом 500, тогда провайдер перестанет присылать событие")),
)
WEBHOOK_SIZES = {"prov": len(WEBHOOK_SCENES), "ev": 1, "eff": 1, "path": len(PATHS),  # prov/ev/eff — одна тройка
                 "evt": 16**8, "t": len(WEBHOOK_TIMEOUTS)}


@family(code="be.http.webhook_delivery", specialization="backend", area="http", level=5,
        fmt="mcq", space_size=rows_space(WEBHOOK_ROWS, WEBHOOK_SIZES), median_time_s=130)
def webhook_delivery(rng: random.Random) -> Generated:
    templates, correct, distractors = rng.choice(WEBHOOK_ROWS)
    prov, event, effect = rng.choice(WEBHOOK_SCENES)
    text = rng.choice(templates).format(
        prov=prov, ev=event, eff=effect, path=f"hooks/{rng.choice(PATHS)}",
        evt=f"evt_{_hex8(rng)}", t=rng.choice(WEBHOOK_TIMEOUTS))
    return mcq(rng, text, correct, distractors)


# --- be.http.parallel_idempotency_race ------------------------------------------
DATABASES = ("PostgreSQL", "MySQL", "MariaDB")
RACE_ROWS = (
    (("Сервис принимает {req} с заголовком Idempotency-Key: {key}. Клиент по ошибке отправил два "
      "одинаковых запроса почти одновременно, с одним и тем же ключом; результат первого ещё не записан. "
      "Приложение работает в нескольких экземплярах за балансировщиком, данные лежат в {db}. "
      "Что гарантирует, что операция выполнится ровно один раз?",
      "Эндпоинт {req} поддерживает Idempotency-Key. Два параллельных запроса с ключом {key} попали на "
      "разные экземпляры приложения (их запущено несколько), и результат первого ещё не записан. "
      "Данные хранятся в {db}. Что гарантирует, что операция выполнится ровно один раз?"),
     "Атомарно занять ключ до выполнения операции: уникальный индекс или блокировка в БД",
     ("Сначала проверить в таблице, есть ли такой ключ, и только затем выполнять саму операцию",
      "Хранить ключи в кэше внутри процесса приложения и сверяться с этим кэшем",
      "Сравнить тела двух запросов и отбросить тот из них, что пришёл позже")),
    (("Для {req} клиент дважды практически одновременно отправил запрос с Idempotency-Key: {key}; "
      "результат первого ещё не записан. Приложение запущено в нескольких экземплярах, база данных — "
      "{db}. Какое решение гарантирует единственное выполнение операции?",
      "Два одинаковых вызова {req} с ключом Idempotency-Key: {key} пришли параллельно, результат "
      "первого ещё не записан. Экземпляров приложения несколько, данные хранятся в {db}. Какое решение "
      "гарантирует единственное выполнение операции?"),
     "Зарезервировать ключ одной атомарной записью (уникальное ограничение) до начала операции",
     ("Прочитать ключ из базы, а при его отсутствии выполнить операцию и затем записать ключ в таблицу",
      "Держать множество уже виденных ключей в памяти каждого экземпляра приложения",
      "Сравнить тела параллельных запросов и выполнить операцию только для одного из них")),
)
RACE_SIZES = {"req": len(IDEMPOTENT_OPS) * API_VERSIONS, "key": KEY_SPACE, "db": len(DATABASES)}


@family(code="be.http.parallel_idempotency_race", specialization="backend", area="http", level=5,
        fmt="mcq", space_size=rows_space(RACE_ROWS, RACE_SIZES), median_time_s=140)
def parallel_idempotency_race(rng: random.Random) -> Generated:
    templates, correct, distractors = rng.choice(RACE_ROWS)
    text = rng.choice(templates).format(req=_idempotent_request(rng), key=_hex8(rng),
                                        db=rng.choice(DATABASES))
    return mcq(rng, text, correct, distractors)
