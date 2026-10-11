"""Семейства Frontend · браузер и сеть."""
import math
import random
from datetime import UTC, datetime

from app.assessment.bank.base import Generated, Prompt, family, mcq

SITES = ("интернет-магазина", "онлайн-банка", "почтового сервиса", "онлайн-школы", "сервиса доставки",
         "соцсети", "трекера задач", "турагентства", "медицинской клиники", "кинотеатра")

# --- fe.browser.same_origin -------------------------------------------------------
DOMAINS = ("example.com", "shop.ru", "bank.test", "school.org", "travel.net", "media.io")
SUBDOMAINS = ("www", "app", "shop", "my", "lk", "portal")
PATHS = ("catalog", "orders", "profile", "cart", "news", "help", "search", "settings")
OTHER_PORTS = {"https": (8443, 4443, 3000), "http": (8080, 8000, 3000)}
DEFAULT_PORTS = {"https": 443, "http": 80}


def _url(scheme: str, host: str, port: int | None, path: str) -> str:
    return f"{scheme}://{host}{f':{port}' if port else ''}/{path}"


@family(code="fe.browser.same_origin", specialization="frontend", area="browser", level=1, fmt="calc",
        # схема × поддомен × домен × путь страницы × путь верного варианта × вид верного × 3 из 4 видов отличия
        space_size=2 * len(SUBDOMAINS) * len(DOMAINS) * len(PATHS) * (len(PATHS) - 1) * 2 * 4 * 24,
        median_time_s=40)
def same_origin(rng: random.Random) -> Generated:
    scheme = rng.choice(("https", "https", "http"))
    sub, domain = rng.choice(SUBDOMAINS), rng.choice(DOMAINS)
    host = f"{sub}.{domain}"
    page, other = rng.sample(PATHS, 2)
    base = f"{_url(scheme, host, None, page)}?page={rng.randint(2, 9)}"
    # тот же origin: другой путь, иногда с явным портом по умолчанию
    explicit = rng.random() < 0.35
    correct = _url(scheme, host, DEFAULT_PORTS[scheme] if explicit else None, other)
    if not explicit and rng.random() < 0.5:
        correct += f"#{rng.choice(('top', 'reviews', 'faq'))}"
    kinds = {
        "scheme": _url("http" if scheme == "https" else "https", host, None, page),
        "sub": _url(scheme, f"{rng.choice([s for s in SUBDOMAINS if s != sub])}.{domain}", None, page),
        "bare": _url(scheme, domain, None, other),
        "port": _url(scheme, host, rng.choice(OTHER_PORTS[scheme]), page),
    }
    wrong = [kinds[k] for k in rng.sample(sorted(kinds), 3)]
    text = (f"Страница открыта по адресу {base}. Какой из адресов относится к тому же происхождению (origin), "
            "что и страница?")
    return mcq(rng, text, correct, wrong, radicals=("same_origin", 4))


# --- fe.browser.token_storage -------------------------------------------------------
TOKEN_NAMES = ("session_id", "access_token", "auth", "sid", "jwt", "refresh_token")
TOKEN_TEMPLATES = (
    "Веб-приложение {site} после входа получает сессионный токен {token}. Главное требование — чтобы токен "
    "нельзя было украсть через XSS (внедрённый на страницу скрипт). Где его хранить?",
    "После авторизации в веб-приложении {site} сервер выдаёт токен {token}. Нужно, чтобы даже при XSS-уязвимости "
    "чужой скрипт на странице не смог его прочитать. Где хранить токен?",
)
TOKEN_CORRECT = (
    "В cookie с флагами HttpOnly, Secure и SameSite: скрипты страницы его не прочитают",
    "В cookie HttpOnly; Secure; SameSite=Lax — браузер отправит её сам, код не прочитает",
)
TOKEN_WRONG = (
    "В localStorage, чтобы токен сохранялся между перезагрузками и всегда был под рукой у кода",
    "В sessionStorage: он очистится при закрытии вкладки, а код сможет его прочитать",
    "В параметре адреса ?token=… у каждой ссылки, чтобы сервер видел его во всех запросах страницы",
    "В глобальной переменной window.token, чтобы любой модуль приложения мог его взять",
    "В обычной cookie без флагов, чтобы и сервер, и JavaScript имели к токену доступ в любой момент",
)


@family(code="fe.browser.token_storage", specialization="frontend", area="browser", level=1, fmt="mcq",
        space_size=len(TOKEN_TEMPLATES) * len(SITES) * len(TOKEN_NAMES) * len(TOKEN_CORRECT)
        * math.comb(len(TOKEN_WRONG), 3) * 24, median_time_s=35)
def token_storage(rng: random.Random) -> Generated:
    text = rng.choice(TOKEN_TEMPLATES).format(site=rng.choice(SITES), token=rng.choice(TOKEN_NAMES))
    return mcq(rng, text, rng.choice(TOKEN_CORRECT), rng.sample(TOKEN_WRONG, 3))


# --- fe.browser.cookie_attributes ---------------------------------------------------
COOKIE_ATTRS = ("HttpOnly", "Secure", "SameSite=Strict", "SameSite=Lax", "Max-Age", "Expires", "Path", "Domain")
COOKIE_QUESTIONS = (  # (вопрос, атрибут)
    ("Какой атрибут запрещает JavaScript на странице читать cookie {name} через document.cookie?", "HttpOnly"),
    ("Какой атрибут запрещает браузеру отправлять cookie {name} по незашифрованному HTTP?", "Secure"),
    ("Какой атрибут запрещает отправлять cookie {name} в любых запросах, пришедших с других сайтов, включая "
     "переходы по ссылкам?", "SameSite=Strict"),
    ("Какой атрибут задаёт срок жизни cookie {name} в секундах?", "Max-Age"),
    ("Какой атрибут ограничивает отправку cookie {name} запросами, путь которых начинается с заданного "
     "префикса?", "Path"),
)
COOKIE_NAMES = ("session", "cart_id", "lang", "theme", "csrftoken", "visitor", "ab_group", "promo")


@family(code="fe.browser.cookie_attributes", specialization="frontend", area="browser", level=2, fmt="mcq",
        space_size=len(COOKIE_QUESTIONS) * len(COOKIE_NAMES) * len(SITES) * 1000 * math.comb(len(COOKIE_ATTRS) - 1, 3)
        * 24, median_time_s=45)
def cookie_attributes(rng: random.Random) -> Generated:
    question, attr = rng.choice(COOKIE_QUESTIONS)
    name = rng.choice(COOKIE_NAMES)
    text = f"Сервер {rng.choice(SITES)} выставляет cookie {name}. " + question.format(name=name)
    code = f"Set-Cookie: {name}={rng.randint(100000, 999999):x}; ..."
    return mcq(rng, text, attr, rng.sample([a for a in COOKIE_ATTRS if a != attr], 3), code=code, language="http")


# --- fe.browser.cors_readable ---------------------------------------------------------
CORS_OPTIONS = {
    "ok": "Ответ доступен: все условия CORS для этого запроса выполнены",
    "mismatch": "Ответ недоступен: Access-Control-Allow-Origin не совпадает с origin страницы",
    "star_credentials": "Ответ недоступен: при credentials: 'include' нельзя * в Access-Control-Allow-Origin",
    "no_acac": "Ответ недоступен: при credentials: 'include' нужен Access-Control-Allow-Credentials: true",
}
# правдоподобные, но неверные исходы: opaque бывает только в режиме no-cors; простой GET идёт без preflight;
# без credentials заголовок Access-Control-Allow-Credentials не нужен
CORS_OPAQUE = "Ответ придёт как opaque: статус и тело скрыты, но ошибки в консоли не будет"
CORS_PREFLIGHT = "Ответ недоступен: для чужого origin браузер сначала требует preflight-запрос OPTIONS"
CORS_ACAC_ALWAYS = "Ответ недоступен: без Access-Control-Allow-Credentials: true браузер не отдаёт ответ коду"
API_PATHS = ("orders", "profile", "cart", "messages", "stats", "items")
# каждый случай отказывает ровно по одному условию: (ACAO, credentials, ACAC, ключ)
CORS_CASES = (
    ("*", False, False, "ok"), ("exact", False, False, "ok"), ("exact", True, True, "ok"),
    ("*", True, True, "star_credentials"), ("exact", True, False, "no_acac"),
    ("other", False, False, "mismatch"), ("other", True, True, "mismatch"),
)


def _other_origin(rng: random.Random, scheme: str, sub: str, domain: str, port: int | None) -> str:
    kind = rng.choice(("scheme", "sub", "port"))
    if kind == "scheme":
        return _url("http" if scheme == "https" else "https", f"{sub}.{domain}", port, "").rstrip("/")
    if kind == "sub":
        return _url(scheme, f"{rng.choice([s for s in SUBDOMAINS if s != sub])}.{domain}", port, "").rstrip("/")
    return _url(scheme, f"{sub}.{domain}", rng.choice([p for p in OTHER_PORTS[scheme] if p != port]), "").rstrip("/")


@family(code="fe.browser.cors_readable", specialization="frontend", area="browser", level=2, fmt="calc",
        # нижняя оценка: случай × схема × поддомен × домен страницы × домен API × путь × вариант чужого origin
        space_size=len(CORS_CASES) * 2 * len(SUBDOMAINS) * len(DOMAINS) * len(DOMAINS) * len(API_PATHS) * 3 * 24,
        median_time_s=60)
def cors_readable(rng: random.Random) -> Generated:
    acao_kind, credentials, acac, key = rng.choice(CORS_CASES)
    scheme = rng.choice(("https", "http"))
    sub, domain = rng.choice(SUBDOMAINS), rng.choice(DOMAINS)
    port = rng.choice((None, None, OTHER_PORTS[scheme][0]))
    page = _url(scheme, f"{sub}.{domain}", port, "").rstrip("/")
    acao = {"*": "*", "exact": page, "other": None}[acao_kind] or _other_origin(rng, scheme, sub, domain, port)
    api = f"https://api.{rng.choice(DOMAINS)}/v1/{rng.choice(API_PATHS)}"
    opts = ", { credentials: 'include' }" if credentials else ""
    headers = ["HTTP/1.1 200 OK", "Content-Type: application/json", f"Access-Control-Allow-Origin: {acao}"]
    if acac:
        headers.append("Access-Control-Allow-Credentials: true")
    code = "\n".join([f"const res = await fetch('{api}'{opts});", "const data = await res.json();", "", "// ответ сервера:",
                      *headers])
    text = (f"Страница с origin {page} выполняет запрос из кода (простой GET, без preflight). Ниже — код и "
            "заголовки ответа сервера. Сможет ли код страницы прочитать ответ?")
    # дистракторы ссылаются только на то, что видно в коде: credentials, «*», отсутствие ACAC
    pool = [CORS_OPTIONS[k] for k in ("ok", "mismatch") if k != key] + [CORS_OPAQUE, CORS_PREFLIGHT]
    if credentials and not acac and key != "no_acac":
        pool.append(CORS_OPTIONS["no_acac"])
    if not credentials and not acac:
        pool.append(CORS_ACAC_ALWAYS)
    return mcq(rng, text, CORS_OPTIONS[key], rng.sample(pool, 3), code=code, language="javascript",
               radicals=("cors_check", 4))


# --- fe.browser.max_age_fresh -------------------------------------------------------------
FRESH_OPTIONS = {
    "cache": "Возьмёт ответ из кэша, не обращаясь к серверу",
    "etag": "Отправит условный запрос с If-None-Match для проверки актуальности",
    "last_modified": "Отправит условный запрос с If-Modified-Since для проверки актуальности",
    "full": "Запросит ресурс целиком, без условных заголовков",
}
FRESH_RESOURCES = ("/api/catalog", "/static/app.css", "/api/rates", "/news/feed", "/api/profile", "/img/logo.png")
MAX_AGES = (60, 120, 300, 600, 900, 3600)


@family(code="fe.browser.max_age_fresh", specialization="frontend", area="browser", level=2, fmt="calc",
        # ресурс × max-age × Age (есть / нет, значение) × время до запроса × валидатор (нижняя оценка)
        space_size=len(FRESH_RESOURCES) * len(MAX_AGES) * 30 * 50 * 3 * 24, median_time_s=60)
def max_age_fresh(rng: random.Random) -> Generated:
    max_age = rng.choice(MAX_AGES)
    want_fresh = rng.random() < 0.35
    while True:
        age = rng.randrange(0, max_age, 5) if rng.random() < 0.5 else 0
        later = rng.randrange(5, 2 * max_age, 5)
        current = age + later
        if abs(current - max_age) >= 5 and (current < max_age) == want_fresh:
            break
    validator = rng.choice(("etag", "last_modified", "none"))
    headers = ["HTTP/1.1 200 OK", f"Cache-Control: max-age={max_age}"]
    if age:
        headers.append(f"Age: {age}")
    if validator == "etag":
        headers.append(f'ETag: "{rng.randrange(16**6):06x}"')
    elif validator == "last_modified":
        stamp = datetime(2026, 9, rng.randint(1, 28), rng.randint(0, 23), tzinfo=UTC)
        headers.append(f"Last-Modified: {stamp.strftime('%a, %d %b %Y %H:%M:%S GMT')}")  # день недели — настоящий
    key = "cache" if want_fresh else ("full" if validator == "none" else validator)
    text = (f"Браузер получил ответ на GET {rng.choice(FRESH_RESOURCES)} и сохранил его в кэше (заголовки ниже). "
            f"Через {later} с после получения страница снова запрашивает этот ресурс. Что сделает браузер?")
    return mcq(rng, text, FRESH_OPTIONS[key], [v for k, v in FRESH_OPTIONS.items() if k != key],
               code="\n".join(headers), language="http", radicals=("http_freshness", 4))


# --- fe.browser.render_pipeline_order ----------------------------------------------------
PIPELINE_STEPS = (
    ("Получение HTML-документа по сети", "Загрузка HTML-документа с сервера"),
    ("Построение DOM и CSSOM", "Разбор HTML и CSS в деревья DOM и CSSOM"),
    ("Построение дерева рендеринга (render tree)", "Объединение деревьев в дерево рендеринга"),
    ("Расчёт геометрии элементов (layout)", "Вычисление размеров и положения элементов (layout)"),
    ("Отрисовка пикселей в слоях (paint)", "Заполнение слоёв пикселями (paint)"),
    ("Композиция слоёв в итоговый кадр (composite)", "Сборка слоёв в кадр на экране (composite)"),
)
PIPELINE_PAGES = ("главную страницу", "страницу товара", "статью", "страницу входа", "личный кабинет")


@family(code="fe.browser.render_pipeline_order", specialization="frontend", area="browser", level=3, fmt="order",
        space_size=2**6 * (math.factorial(6) - 1) * len(PIPELINE_PAGES) * len(SITES), median_time_s=70)
def render_pipeline_order(rng: random.Random) -> Generated:
    steps = [rng.choice(variants) for variants in PIPELINE_STEPS]
    order = list(range(6))
    while order == sorted(order):
        rng.shuffle(order)
    shown = tuple(steps[i] for i in order)
    answer = tuple(order.index(i) + 1 for i in range(6))
    text = (f"Браузер впервые открывает {rng.choice(PIPELINE_PAGES)} сайта {rng.choice(SITES)}. Расположите этапы "
            "от загрузки документа до появления кадра на экране в правильном порядке.")
    return Generated("order", Prompt(text=text, steps=shown, answer_hint="Номера всех шагов через пробел, например: 2 1 3 …"),
                     answer, ("critical_rendering_path", 6))


# --- fe.browser.forced_reflow --------------------------------------------------------------
REFLOW_ELEMENTS = ("card", "panel", "menu", "banner", "sidebar", "modal")
REFLOW_WRITES = (("width", "'320px'"), ("height", "'240px'"), ("padding", "'16px'"), ("fontSize", "'18px'"),
                 ("margin", "'24px'"), ("borderWidth", "'4px'"), ("display", "'block'"))
REFLOW_READS = ("offsetHeight", "offsetWidth", "clientHeight", "scrollHeight", "getBoundingClientRect().height")
REFLOW_CORRECT = (
    "Синхронно пересчитает стили и layout и вернёт значение уже с учётом нового стиля",
    "Сразу выполнит принудительный пересчёт layout и вернёт актуальную геометрию",
)
REFLOW_WRONG = (
    "Вернёт значение из прошлого кадра, а layout пересчитает позже, перед следующей отрисовкой",
    "Вернёт 0: новый стиль применится только в следующем кадре",
    "Выполнит только paint без layout: геометрия не зависит от стилей",
    "Бросит исключение: читать геометрию сразу после записи стиля в том же кадре запрещено",
)


@family(code="fe.browser.forced_reflow", specialization="frontend", area="browser", level=3, fmt="mcq",
        space_size=len(REFLOW_ELEMENTS) * len(REFLOW_WRITES) * len(REFLOW_READS) * 2 * len(REFLOW_CORRECT)
        * math.comb(len(REFLOW_WRONG), 3) * 24, median_time_s=60)
def forced_reflow(rng: random.Random) -> Generated:
    el = rng.choice(REFLOW_ELEMENTS)
    prop, value = rng.choice(REFLOW_WRITES)
    read = rng.choice(REFLOW_READS)
    var = rng.choice(("size", "h"))
    code = "\n".join([f"const {el} = document.querySelector('.{el}');", f"{el}.style.{prop} = {value};",
                      f"const {var} = {el}.{read};", f"console.log({var});"])
    text = f"Что сделает браузер, когда выполнение дойдёт до строки с чтением {el}.{read}?"
    return mcq(rng, text, rng.choice(REFLOW_CORRECT), rng.sample(REFLOW_WRONG, 3), code=code, language="javascript")


# --- fe.browser.script_exec_order ------------------------------------------------------------
SCRIPT_NAMES = ("analytics.js", "app.js", "vendor.js", "polyfills.js", "widget.js", "chat.js", "ads.js", "i18n.js")
ASYNC_TIMINGS = {
    "first": "загрузится раньше всех — до того, как разбор HTML дойдёт до следующего тега script",
    "last": "загрузится очень поздно — когда разбор HTML уже закончится и все defer-скрипты выполнятся",
}


@family(code="fe.browser.script_exec_order", specialization="frontend", area="browser", level=3, fmt="order",
        # нижняя оценка: четыре скрипта — имена × атрибуты (async один) × время async × перемешивание
        space_size=math.perm(len(SCRIPT_NAMES), 4) * 6 * 2 * 23, median_time_s=80)
def script_exec_order(rng: random.Random) -> Generated:
    timing = rng.choice(sorted(ASYNC_TIMINGS))
    n = rng.randint(4, 5)
    names = rng.sample(SCRIPT_NAMES, n)
    while True:
        attrs = [rng.choice(("", " defer")) for _ in range(n)]
        pos = 0 if timing == "first" else rng.randrange(n)  # «раньше всех» — async стоит первым в документе
        attrs[pos] = " async"
        if "" in attrs and " defer" in attrs:
            break
    regular = [nm for nm, a in zip(names, attrs, strict=True) if a == ""]
    defer = [nm for nm, a in zip(names, attrs, strict=True) if a == " defer"]
    asyncs = [names[pos]]
    want = asyncs + regular + defer if timing == "first" else regular + defer + asyncs
    order = list(range(n))
    while [want[i] for i in order] == want:
        rng.shuffle(order)
    shown = tuple(want[i] for i in order)
    answer = tuple(shown.index(nm) + 1 for nm in want)
    code = "\n".join(["<head>", *(f'  <script src="{nm}"{a}></script>' for nm, a in zip(names, attrs, strict=True)),
                      "</head>"])
    text = (f"Скрипты подключены в <head> в порядке из кода, все внешние. Обычные и defer-скрипты загружаются "
            f"быстро — раньше, чем разбор HTML дойдёт до них. Скрипт {names[pos]} (async) {ASYNC_TIMINGS[timing]}. "
            "В каком порядке выполнятся скрипты?")
    return Generated("order", Prompt(text=text, code=code, language="html", steps=shown,
                                     answer_hint="Номера всех шагов через пробел, например: 2 1 3 …"),
                     answer, ("script_loading", "defer_async"))


# --- fe.browser.lcp_fix -----------------------------------------------------------------------
LCP_PAGES = ("главной странице", "странице акции", "лендинге курса", "странице отеля", "странице товара")
LCP_IMAGES = ("hero", "banner", "cover", "main-photo", "promo")
LCP_CORRECT = (
    'Убрать loading="lazy" у этого изображения и добавить ему fetchpriority="high"',
    'Снять ленивую загрузку с изображения и загрузить его заранее через <link rel="preload">',
)
LCP_WRONG = (
    'Оставить hero как есть и добавить loading="lazy" всем остальным изображениям страницы',
    "Перенести изображение в CSS background-image, чтобы грузилось со стилями",
    'Добавить атрибут decoding="async": он ускоряет загрузку изображения по сети в несколько раз',
    "Вставлять изображение из JavaScript после события load, чтобы оно не мешало остальному",
)


@family(code="fe.browser.lcp_fix", specialization="frontend", area="browser", level=4, fmt="mcq",
        space_size=len(LCP_PAGES) * len(SITES) * len(LCP_IMAGES) * 3 * len(LCP_CORRECT)
        * math.comb(len(LCP_WRONG), 3) * 24, median_time_s=90)
def lcp_fix(rng: random.Random) -> Generated:
    img = rng.choice(LCP_IMAGES)
    width = rng.choice((1200, 1600, 1920))
    code = "\n".join(["<main>", f'  <img src="/img/{img}-{width}.webp" width="{width}" height="{width // 2}"',
                      '       loading="lazy" alt="Главное фото">', "  <h1>…</h1>", "</main>"])
    text = (f"На {rng.choice(LCP_PAGES)} сайта {rng.choice(SITES)} самый крупный элемент первого экрана — это "
            "изображение из кода; Lighthouse показывает, что оно и есть LCP, и LCP слишком большой. Что "
            "исправить в первую очередь?")
    return mcq(rng, text, rng.choice(LCP_CORRECT), rng.sample(LCP_WRONG, 3), code=code, language="html")


def _numbered(lines: list[str]) -> str:
    return "\n".join(f"{n:>2}| {ln}" for n, ln in enumerate(lines, start=1))


# --- fe.browser.layout_thrash_line -------------------------------------------------------
THRASH_FUNCS = ("resizeCards", "alignTiles", "fitRows", "updateItems", "layoutGrid")
THRASH_CLASSES = (("card", "cards"), ("tile", "tiles"), ("row", "rows"), ("item", "items"), ("cell", "cells"))
THRASH_READS = ("offsetHeight", "offsetWidth", "clientHeight", "getBoundingClientRect().height")


@family(code="fe.browser.layout_thrash_line", specialization="frontend", area="browser", level=4, fmt="bug",
        # функция × класс × чтение × множитель × запас × проверка пустого × комментарий × вторая запись
        space_size=len(THRASH_FUNCS) * len(THRASH_CLASSES) * len(THRASH_READS) * 9 * 9 * 2 * 2 * 2,
        median_time_s=100)
def layout_thrash_line(rng: random.Random) -> Generated:
    fn = rng.choice(THRASH_FUNCS)
    it, items = rng.choice(THRASH_CLASSES)
    read = rng.choice(THRASH_READS)
    lines = [f"function {fn}(container) {{", f"  const {items} = container.querySelectorAll('.{it}');"]
    if rng.random() < 0.5:
        lines.append(f"  if ({items}.length === 0) return 0;")
    lines.append("  let total = 0;")
    if rng.random() < 0.5:
        lines.append("  // подгоняем размеры под сетку")
    lines += [f"  for (const {it} of {items}) {{",
              f"    {it}.style.width = `${{{it}.dataset.cols * {rng.randrange(40, 121, 10)}}}px`;"]
    if rng.random() < 0.5:
        lines.append(f"    {it}.style.padding = '{rng.randrange(4, 21, 4)}px';")
    key = len(lines) + 1
    lines += [f"    const h = {it}.{read};", f"    {it}.style.minHeight = `${{h + {rng.randrange(8, 41, 4)}}}px`;",
              "    total += h;", "  }", "  container.style.height = `${total}px`;", "  return total;", "}"]
    text = ("Функция заметно тормозит на сотнях элементов: профайлер показывает многократный пересчёт layout. "
            "В какой строке браузер вынужден синхронно пересчитывать layout на каждой итерации цикла?")
    return Generated("line", Prompt(text=text, code="\n".join(lines), language="javascript",
                                    answer_hint=f"Номер строки:\n{_numbered(lines)}"), key, ("layout_thrashing",))


# --- fe.browser.cache_busting ----------------------------------------------------------------
CACHE_PROJECTS = ("интернет-магазина", "личного кабинета", "лендинга", "админки", "блога", "SPA-приложения")
CACHE_CORRECT = (
    "Хэш содержимого в именах JS/CSS и для них max-age=31536000, immutable; index.html — no-cache",
    "JS и CSS с хэшем в имени и Cache-Control: immutable на год; index.html — no-cache",
)
CACHE_WRONG = (
    "Всем файлам Cache-Control: no-store — тогда браузер никогда не будет хранить старую версию сайта",
    "Всем файлам, включая index.html, max-age=31536000, immutable — так кэш работает лучше всего",
    "Добавлять ?v=Date.now() к ссылкам на JS и CSS при каждом запросе index.html, чтобы сбросить кэш",
    "Хэш в имени index.html, а JS и CSS отдавать с no-cache без хэша в именах",
)
CACHE_FILES = ("index.html", "app.js", "vendor.js", "styles.css")


@family(code="fe.browser.cache_busting", specialization="frontend", area="browser", level=4, fmt="mcq",
        space_size=len(CACHE_PROJECTS) * 99**4 * len(CACHE_CORRECT) * math.comb(len(CACHE_WRONG), 3) * 24,
        median_time_s=90)
def cache_busting(rng: random.Random) -> Generated:
    code = "\n".join(f"dist/{name:<12}{rng.randint(1, 99) * (10 if name.endswith('.js') else 1)} КБ"
                     for name in CACHE_FILES)
    text = (f"Сборка {rng.choice(CACHE_PROJECTS)} выдаёт файлы из листинга. После каждого деплоя часть "
            "пользователей ещё видит старую версию. Нужно, чтобы обновления доходили сразу, а статика при этом "
            "кэшировалась надолго. Какую схему кэширования выбрать?")
    return mcq(rng, text, rng.choice(CACHE_CORRECT), rng.sample(CACHE_WRONG, 3), code=code, language="text")


# --- fe.browser.csp_blocked ---------------------------------------------------------------------
CSP_RESOURCE_KIND = {"Скрипт": "script", "Встроенный": "script", "Изображение": "img", "Запрос": "connect",
                     "Шрифт": "font", "Стиль": "style"}
CSP_CDNS = ("jsdelivr.net", "cdnjs.com", "unpkg.com", "static-cdn.ru")
CSP_IMG = ("imgix.net", "pics.ru", "photos.io", "media-store.net")
CSP_FONTS = ("fonts.gstatic.com", "fonts.myfonts.ru")
CSP_FOREIGN = ("tracker.io", "ads-net.com", "metrics.biz", "spy.example")
CSP_NAMES = ("main", "app", "widget", "chart", "menu", "promo")


def _csp(rng: random.Random) -> tuple[str, str, dict[str, list[str]], dict[str, list[str]]]:
    """Политика, адрес страницы, разрешённые и заблокированные ресурсы (по построению).

    Каждый вид ресурса бывает и разрешённым, и заблокированным: 'unsafe-inline' и data: в политике
    случайны, стиль бывает своим и с чужого CDN, — по форме варианта ключ не угадать."""
    domain, sub = rng.choice(DOMAINS), rng.choice(SUBDOMAINS)
    page = f"https://{sub}.{domain}"
    cdn, img, font, foreign, name = (rng.choice(CSP_CDNS), rng.choice(CSP_IMG), rng.choice(CSP_FONTS),
                                     rng.choice(CSP_FOREIGN), rng.choice(CSP_NAMES))
    with_font, with_inline, with_data = rng.random() < 0.5, rng.random() < 0.4, rng.random() < 0.6
    script_src = "'self' 'unsafe-inline'" if with_inline else "'self'"
    img_src = "'self' data:" if with_data else "'self'"
    parts = ["default-src 'self'", f"script-src {script_src} https://{cdn}", f"img-src {img_src} https://*.{img}",
             f"connect-src 'self' https://api.{domain}"]
    if with_font:
        parts.append(f"font-src https://{font}")
    inline = "Встроенный <script> в разметке страницы"
    data_img = "Изображение data:image/png;base64,iVBORw0KGgo="
    allowed = {
        "cdn": f"Скрипт https://{cdn}/{name}.min.js", "self_js": f"Скрипт {page}/js/{name}.js",
        "img_sub": f"Изображение https://cdn.{img}/{name}.png", "api": f"Запрос fetch к https://api.{domain}/v1/{name}",
        "css": f"Стиль {page}/css/{name}.css",
    }
    blocked = {
        "bare": f"Изображение https://{img}/{name}.png",  # *.img не покрывает сам домен img
        "scheme": f"Скрипт http://{cdn}/{name}.min.js",  # источник указан с https
        "foreign": f"Запрос fetch к https://{foreign}/collect",
        "sibling": f"Скрипт https://static.{domain}/{name}.js",  # другой поддомен — не 'self'
        "style_cdn": f"Стиль https://{cdn}/{name}.css",  # style-src нет — действует default-src 'self'
    }
    (allowed if with_inline else blocked)["inline"] = inline
    (allowed if with_data else blocked)["data"] = data_img
    (allowed if with_font else blocked)["font"] = f"Шрифт https://{font}/{name}.woff2"  # без font-src — default-src
    return "; ".join(parts), page, {k: [v] for k, v in allowed.items()}, {k: [v] for k, v in blocked.items()}


@family(code="fe.browser.csp_blocked", specialization="frontend", area="browser", level=5, fmt="calc",
        # нижняя оценка: домен × поддомен × CDN × домен картинок × шрифт × чужой домен × имя × ловушка × 3 разрешённых
        space_size=len(DOMAINS) * len(SUBDOMAINS) * len(CSP_CDNS) * len(CSP_IMG) * len(CSP_FONTS) * len(CSP_FOREIGN)
        * len(CSP_NAMES) * 5 * math.comb(5, 3) * 24, median_time_s=140)
def csp_blocked(rng: random.Random) -> Generated:
    policy, page, allowed, blocked = _csp(rng)
    trap = rng.choice(sorted(blocked))
    ok = [allowed[k][0] for k in rng.sample(sorted(allowed), 3)]
    text = f"Страница {page} отдаётся с заголовком из кода. Какой из ресурсов страницы браузер заблокирует?"
    return mcq(rng, text, blocked[trap][0], ok, code=f"Content-Security-Policy: {policy}", language="http",
               radicals=("csp_matching", 4))


# --- fe.browser.detached_dom_leak ------------------------------------------------------------------
LEAK_VARIANTS = {  # вид удерживающей ссылки → (строки кода с {holder}, holder для ответа)
    "array": (("const {holder} = [];",), "{holder}.push(li);", "{holder}"),
    "map": (("const {holder} = new Map();",), "{holder}.set(id, li);", "{holder}"),
    "listener": ((), "window.addEventListener('resize', () => li.classList.toggle('compact', innerWidth < 600));",
                 "window"),
    "timer": ((), "setInterval(() => {{ li.dataset.seen = String(Date.now()); }}, 1000);", "setInterval"),
}
LEAK_HOLDERS = ("cache", "rows", "history", "registry", "byId", "nodes")
LEAK_CORRECT = "Удалённые узлы остаются достижимыми через {holder}; GC их не освободит, ссылки надо убрать"
LEAK_WRONG = (
    "innerHTML = '' не удаляет узлы: они остаются на странице, просто становятся невидимыми для пользователя",
    "Сборщик мусора в браузере освобождает DOM-узлы только при перезагрузке страницы",
    "Узлы, созданные через createElement, нужно освобождать вручную вызовом node.free() после удаления",
    "Утечку даёт appendChild: вместо него нужно использовать insertAdjacentHTML",
)
LEAK_LISTS = (("addRow", "clearList"), ("addMessage", "resetChat"), ("addItem", "clearCart"),
              ("addLogLine", "clearLog"), ("addCard", "resetBoard"), ("addTag", "clearTags"),
              ("addComment", "clearComments"), ("addEvent", "resetTimeline"))
LEAK_CLASSES = ("row", "msg", "item", "entry", "card", "tag")


@family(code="fe.browser.detached_dom_leak", specialization="frontend", area="browser", level=5, fmt="mcq",
        # нижняя оценка — без имени хранилища (у слушателя и таймера его нет): вид × функции × тег × класс
        space_size=len(LEAK_VARIANTS) * len(LEAK_LISTS) * 3 * len(LEAK_CLASSES) * math.comb(len(LEAK_WRONG), 3) * 24,
        median_time_s=120)
def detached_dom_leak(rng: random.Random) -> Generated:
    kind = rng.choice(sorted(LEAK_VARIANTS))
    decl, keep, holder_tpl = LEAK_VARIANTS[kind]
    holder_name = rng.choice(LEAK_HOLDERS)
    add, clear = rng.choice(LEAK_LISTS)
    tag = rng.choice(("li", "div", "p"))
    code = "\n".join([*(d.format(holder=holder_name) for d in decl), *([""] if decl else []),
                      f"function {add}(list, id, text) {{", f"  const li = document.createElement('{tag}');",
                      f"  li.className = '{rng.choice(LEAK_CLASSES)}';", "  li.textContent = text;",
                      "  list.appendChild(li);", f"  {keep.format(holder=holder_name)}",
                      "}", "", f"function {clear}(list) {{", "  list.innerHTML = '';", "}"])
    holder = holder_tpl.format(holder=holder_name)
    text = (f"Функции {add} и {clear} вызываются по очереди тысячи раз. Потребление памяти страницы растёт, а "
            "снимок кучи показывает тысячи отсоединённых (detached) DOM-элементов. В чём причина?")
    return mcq(rng, text, LEAK_CORRECT.format(holder=holder), rng.sample(LEAK_WRONG, 3), code=code,
               language="javascript")
