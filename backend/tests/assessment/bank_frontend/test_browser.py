"""Семантические тесты Frontend · браузер и сеть: ключ проверяется независимо от генератора."""
import re
from urllib.parse import urlsplit

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import frontend_browser as br

from .._bank_helpers import area_codes, make

AREA_CODES = area_codes("browser", "frontend")


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)
    assert r.space_estimate >= 50_000, (code, r.space_estimate)


def _mcq_parts(inst):
    key = inst.prompt.options[inst.answer]
    return key, [o for i, o in enumerate(inst.prompt.options) if i != inst.answer]


# ------------------------------------------------------------------ same_origin
def _origin(url: str) -> tuple[str, str, int]:
    """(схема, хост, порт) по RFC 6454; порт по умолчанию — 80 для http, 443 для https."""
    u = urlsplit(url)
    return u.scheme, u.hostname, u.port or {"http": 80, "https": 443}[u.scheme]


def test_same_origin_key():
    explicit_default_port = 0
    for seed in range(300):
        inst = make("fe.browser.same_origin", seed)
        base = re.search(r"Страница открыта по адресу (\S+)\.", inst.prompt.text).group(1)
        same = [o for o in inst.prompt.options if _origin(o) == _origin(base)]
        assert same == [inst.prompt.options[inst.answer]]  # ровно один вариант того же происхождения
        explicit_default_port += bool(re.search(r":(443|80)/", same[0]))
    assert explicit_default_port >= 30  # явный порт по умолчанию — тот же origin


# ------------------------------------------------------------------ token_storage
def test_token_storage_key():
    for seed in range(200):
        inst = make("fe.browser.token_storage", seed)
        key, others = _mcq_parts(inst)
        assert key in br.TOKEN_CORRECT and set(others) <= set(br.TOKEN_WRONG)
        assert "HttpOnly" in key and not any("HttpOnly" in o for o in others)


# ------------------------------------------------------------------ cookie_attributes
COOKIE_PURPOSE = {  # назначение → атрибут (независимая таблица)
    "JavaScript": "HttpOnly", "незашифрованному": "Secure", "других сайтов": "SameSite=Strict",
    "срок жизни": "Max-Age", "префикс": "Path",
}


def test_cookie_attributes_key():
    asked = set()
    for seed in range(200):
        inst = make("fe.browser.cookie_attributes", seed)
        hits = [attr for cue, attr in COOKIE_PURPOSE.items() if cue in inst.prompt.text]
        assert len(hits) == 1, inst.prompt.text
        key, others = _mcq_parts(inst)
        assert key == hits[0] and hits[0] not in others
        assert set(others) <= set(br.COOKIE_ATTRS)
        asked.add(key)
    assert asked == set(COOKIE_PURPOSE.values())


# ------------------------------------------------------------------ cors_readable
def _cors_key(page_origin: str, acao: str, credentials: bool, acac: bool) -> str:
    """CORS-проверка по спецификации Fetch (простой GET без preflight), порядок шагов — как в стандарте."""
    if not credentials and acao == "*":
        return "ok"
    if acao != page_origin:
        return "star_credentials" if acao == "*" else "mismatch"
    if not credentials:
        return "ok"
    return "ok" if acac else "no_acac"


def test_cors_readable_key():
    seen = set()
    for seed in range(300):
        inst = make("fe.browser.cors_readable", seed)
        page = re.search(r"Страница с origin (\S+) ", inst.prompt.text).group(1)
        code = inst.prompt.code
        credentials = "credentials: 'include'" in code
        acao = re.search(r"^Access-Control-Allow-Origin: (\S+)$", code, re.M).group(1)
        acac = bool(re.search(r"^Access-Control-Allow-Credentials: true$", code, re.M))
        want = _cors_key(page, acao, credentials, acac)
        assert inst.prompt.options[inst.answer] == br.CORS_OPTIONS[want]
        assert br.CORS_OPAQUE != inst.prompt.options[inst.answer]  # режим cors: opaque не бывает
        # ровно одна причина: при отказе по одному условию остальные выполнены
        if want == "mismatch":
            assert not credentials or acac
        if want == "star_credentials":
            assert acac
        seen.add(want)
    assert seen == {"ok", "mismatch", "star_credentials", "no_acac"}


# ------------------------------------------------------------------ max_age_fresh
def test_max_age_fresh_key():
    seen = set()
    for seed in range(300):
        inst = make("fe.browser.max_age_fresh", seed)
        t, code = inst.prompt.text, inst.prompt.code
        max_age = int(re.search(r"max-age=(\d+)", code).group(1))
        age = int(m.group(1)) if (m := re.search(r"^Age: (\d+)$", code, re.M)) else 0
        later = int(re.search(r"Через (\d+) с после", t).group(1))
        current_age = age + later  # RFC 9111: возраст = Age + время пребывания в кэше
        etag, lm = "ETag:" in code, "Last-Modified:" in code
        assert not (etag and lm)
        if current_age < max_age:
            want = "cache"
        else:
            want = "etag" if etag else "last_modified" if lm else "full"
        assert inst.prompt.options[inst.answer] == br.FRESH_OPTIONS[want]
        assert abs(current_age - max_age) >= 5
        seen.add(want)
    assert seen == {"cache", "etag", "last_modified", "full"}


# ------------------------------------------------------------------ render_pipeline_order
PIPELINE_CUES = (r"HTML-документ", r"DOM и CSSOM", r"дерев\w* рендеринга", r"layout", r"paint", r"composite")


def test_render_pipeline_order_key():
    for seed in range(200):
        inst = make("fe.browser.render_pipeline_order", seed)
        steps = inst.prompt.steps
        stage = [next(i for i, cue in enumerate(PIPELINE_CUES) if re.search(cue, s)) for s in steps]
        assert sorted(stage) == list(range(6))
        ordered = [stage[i - 1] for i in inst.answer]
        assert ordered == list(range(6)) and tuple(inst.answer) != tuple(range(1, 7))


def test_max_age_fresh_http_date_is_consistent():
    """Last-Modified — настоящая дата: день недели соответствует числу (RFC 9110 IMF-fixdate)."""
    from datetime import datetime
    checked = 0
    for seed in range(300):
        code = make("fe.browser.max_age_fresh", seed).prompt.code
        if m := re.search(r"^Last-Modified: (.+)$", code, re.M):
            d = datetime.strptime(m.group(1), "%a, %d %b %Y %H:%M:%S GMT")
            assert d.strftime("%a, %d %b %Y %H:%M:%S GMT") == m.group(1)
            checked += 1
    assert checked >= 50


# ------------------------------------------------------------------ forced_reflow
GEOMETRY_READS = ("offsetHeight", "offsetWidth", "clientHeight", "scrollHeight", "getBoundingClientRect()")
LAYOUT_PROPS = ("width", "height", "padding", "fontSize", "margin", "borderWidth", "display")


def test_forced_reflow_key():
    for seed in range(200):
        inst = make("fe.browser.forced_reflow", seed)
        code = inst.prompt.code
        write = re.search(r"\.style\.(\w+) = ", code).group(1)
        read_line = next(ln for ln in code.splitlines() if any(r in ln for r in GEOMETRY_READS))
        assert write in LAYOUT_PROPS  # запись меняет геометрию — layout действительно устарел
        assert code.index(".style.") < code.index(read_line)  # чтение идёт после записи
        key, others = _mcq_parts(inst)
        assert key in br.REFLOW_CORRECT and set(others) <= set(br.REFLOW_WRONG)


# ------------------------------------------------------------------ script_exec_order
def test_script_exec_order_key():
    timings = set()
    for seed in range(300):
        inst = make("fe.browser.script_exec_order", seed)
        scripts = re.findall(r'<script src="([\w.-]+)"( defer| async)?></script>', inst.prompt.code)
        asyncs = [n for n, a in scripts if a == " async"]
        assert len(asyncs) == 1 and 4 <= len(scripts) <= 5
        regular = [n for n, a in scripts if not a]
        defer = [n for n, a in scripts if a == " defer"]
        assert regular and defer
        # обычные — во время разбора по порядку; defer — после разбора по порядку; async — когда загрузится
        if "раньше всех" in inst.prompt.text:
            assert scripts[0][1] == " async"
            want = asyncs + regular + defer
            timings.add("first")
        else:
            assert "все defer-скрипты выполнятся" in inst.prompt.text
            want = regular + defer + asyncs
            timings.add("last")
        steps = inst.prompt.steps
        assert [steps[i - 1] for i in inst.answer] == want
    assert timings == {"first", "last"}


# ------------------------------------------------------------------ lcp_fix
def test_lcp_fix_key():
    for seed in range(200):
        inst = make("fe.browser.lcp_fix", seed)
        key, others = _mcq_parts(inst)
        assert key in br.LCP_CORRECT and set(others) <= set(br.LCP_WRONG)
        assert 'loading="lazy"' in inst.prompt.code  # изображение LCP сейчас грузится лениво


# ------------------------------------------------------------------ layout_thrash_line
def test_layout_thrash_line_key():
    positions = set()
    for seed in range(200):
        inst = make("fe.browser.layout_thrash_line", seed)
        lines = inst.prompt.code.split("\n")
        assert inst.prompt.answer_hint == "Номер строки:\n" + "\n".join(f"{n:>2}| {ln}" for n, ln in enumerate(lines, 1))
        loop = next(i for i, ln in enumerate(lines) if ln.lstrip().startswith("for ("))
        end = next(i for i in range(loop + 1, len(lines)) if lines[i] == "  }")
        body = lines[loop + 1:end]
        reads = [loop + 2 + i for i, ln in enumerate(body) if re.search(r"\.(offset\w+|client\w+|getBoundingClientRect)", ln)]
        writes = [loop + 2 + i for i, ln in enumerate(body) if ".style." in ln]
        assert reads == [inst.answer]  # чтение геометрии в цикле — одно
        assert min(writes) < inst.answer  # и идёт после записи стиля в той же итерации
        assert 12 <= len(lines) <= 15
        positions.add(inst.answer)
    assert len(positions) >= 3


# ------------------------------------------------------------------ cache_busting
def test_cache_busting_key():
    for seed in range(200):
        inst = make("fe.browser.cache_busting", seed)
        key, others = _mcq_parts(inst)
        assert key in br.CACHE_CORRECT and set(others) <= set(br.CACHE_WRONG)
        assert "immutable" in key and "no-cache" in key


# ------------------------------------------------------------------ csp_blocked
def _host_port(url: str) -> tuple[str, str, int]:
    u = urlsplit(url)
    return u.scheme, u.hostname, u.port or {"http": 80, "https": 443}.get(u.scheme, 0)


def _source_allows(src: str, url: str, page: str) -> bool:
    """Сопоставление источника CSP Level 3 (без путей): 'self', схема, хост с необязательным *. ."""
    if url == "inline":
        return src == "'unsafe-inline'"
    scheme, host, port = _host_port(url) if not url.startswith("data:") else ("data", None, 0)
    if src == "'self'":
        return _host_port(url) == _host_port(page) if scheme != "data" else False
    if src.endswith(":") and "/" not in src:
        return scheme == src[:-1]
    if src == "'none'":
        return False
    s = urlsplit(src if "://" in src else f"{scheme}://{src}")
    if s.scheme != scheme or scheme == "data":
        return False
    if s.hostname.startswith("*."):
        return host.endswith(s.hostname[1:]) and host != s.hostname[2:]  # *.x — только поддомены
    return host == s.hostname


def _csp_allows(policy: str, kind: str, url: str, page: str) -> bool:
    directives = dict(re.findall(r"([\w-]+) ([^;]+)", policy))
    srcs = directives.get(f"{kind}-src", directives.get("default-src", "")).split()
    return any(_source_allows(s, url, page) for s in srcs)


def test_csp_blocked_key():
    traps = set()
    for seed in range(300):
        inst = make("fe.browser.csp_blocked", seed)
        page = re.search(r"Страница (https://\S+) отдаётся", inst.prompt.text).group(1)
        policy = re.search(r"^Content-Security-Policy: (.+)$", inst.prompt.code, re.M).group(1)
        blocked = []
        for opt in inst.prompt.options:
            kind, url = br.CSP_RESOURCE_KIND[opt.split()[0]], opt.split()[-1]
            if opt.startswith("Встроенный"):
                url = "inline"
            if not _csp_allows(policy, kind, url, page):
                blocked.append(opt)
        assert blocked == [inst.prompt.options[inst.answer]]
        traps.add(blocked[0].split()[0])
    assert len(traps) >= 3


# ------------------------------------------------------------------ detached_dom_leak
def test_detached_dom_leak_key():
    holders = set()
    for seed in range(200):
        inst = make("fe.browser.detached_dom_leak", seed)
        key, others = _mcq_parts(inst)
        holder = re.search(r"достижимыми через (\S+?)[;,:]", key).group(1)
        assert holder in inst.prompt.code  # ссылку держит объект из кода
        assert set(others) <= set(br.LEAK_WRONG)
        holders.add(holder.split(".")[0])
    assert len(holders) >= 3


def test_csp_resource_form_does_not_fix_the_key():
    """Вид ресурса (встроенный скрипт, data:, стиль) встречается и среди разрешённых, и среди заблокированных."""
    seen = {}
    for seed in range(600):
        inst = make("fe.browser.csp_blocked", seed)
        for i, opt in enumerate(inst.prompt.options):
            form = "inline" if opt.startswith("Встроенный") else "data" if "data:" in opt else opt.split()[0]
            seen.setdefault(form, set()).add(i == inst.answer)
    for form in ("inline", "data", "Стиль", "Скрипт", "Изображение", "Запрос", "Шрифт"):
        assert seen.get(form) == {True, False}, (form, seen.get(form))



def test_cors_distractors_cite_only_visible_conditions():
    """Дистрактор не ссылается на условие, которого в коде нет: credentials, «*», отсутствие ACAC."""
    for seed in range(300):
        inst = make("fe.browser.cors_readable", seed)
        code = inst.prompt.code
        credentials = "credentials: 'include'" in code
        star = re.search(r"^Access-Control-Allow-Origin: \*$", code, re.M) is not None
        acac = "Access-Control-Allow-Credentials: true" in code
        for i, o in enumerate(inst.prompt.options):
            if i == inst.answer:
                continue
            if "credentials: 'include'" in o:
                assert credentials, (o, code)
            if "нельзя *" in o:
                assert star, (o, code)
            if "нужен Access-Control-Allow-Credentials" in o:
                assert not acac, (o, code)
