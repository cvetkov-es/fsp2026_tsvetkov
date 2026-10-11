import ast
import json
import math
import re

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import backend_http as http_module

from ._helpers import area_codes
from ._helpers import make as _make
from ._helpers import row_for as _row_for

AREA_CODES = area_codes("http")
SEEDS = range(40)


def _assert_four_distinct(inst):
    opts = inst.prompt.options
    assert len(opts) == 4 and len(set(opts)) == 4
    assert inst.radicals == ("mcq", 4)


def _assert_mcq_shape(inst, correct_text):
    _assert_four_distinct(inst)
    assert inst.prompt.options[inst.answer] == correct_text


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


# ---------------------------------------------------------------- batch A
def test_method_idempotency_key():
    code = "be.http.method_idempotency"
    for seed in SEEDS:
        inst = _make(code, seed)
        opts = inst.prompt.options
        assert len(opts) == 4 and len(set(opts)) == 4
        methods = sorted(o.split()[0] for o in opts)
        assert methods == ["DELETE", "GET", "POST", "PUT"]
        assert opts[inst.answer].startswith("POST ")
        assert sum(o.startswith("POST ") for o in opts) == 1
        prefixes = {o.split()[1].split("?")[0].split("/")[3] for o in opts}
        assert len(prefixes) == 1  # один и тот же ресурс во всех вариантах
    assert len({_make(code, s).answer for s in range(60)}) == 4


def _path_shape(option: str) -> str:
    """Форма пути варианта: collection, item, page, sub_collection, sub_item (независимо от генератора)."""
    path = option.split()[1]
    if "?page=" in path:
        return "page"
    segments = path.split("/")[4:]  # после '', 'api', 'vN', ресурс
    return ("collection", "item", "sub_collection", "sub_item")[len(segments)]


def test_method_idempotency_path_shapes_vary_for_every_method():
    shapes = {}
    for seed in range(300):
        for o in _make("be.http.method_idempotency", seed).prompt.options:
            shapes.setdefault(o.split()[0], set()).add(_path_shape(o))
    assert shapes == {"POST": {"collection", "sub_collection"},
                      "GET": {"item", "page", "collection", "sub_collection"},
                      "PUT": {"item", "sub_item"}, "DELETE": {"item", "sub_item"}}


def test_method_idempotency_correct_not_always_shortest_path():
    code = "be.http.method_idempotency"
    shapes = set()
    for seed in range(60):
        inst = _make(code, seed)
        shapes.add(inst.prompt.options[inst.answer].count("/"))
    assert len(shapes) > 1  # у POST бывает и «голый» путь, и вложенный


def test_cache_control_scenario_to_header():
    code = "be.http.cache_control_header"
    seen = set()
    for seed in SEEDS:
        inst = _make(code, seed)
        templates, header, _ = _row_for(inst.prompt.text, http_module.CACHE_ROWS)
        opts = inst.prompt.options
        _assert_four_distinct(inst)
        assert re.sub(r"=\d+", "=N", opts[inst.answer]) == header
        # дистракторы не содержат правильный заголовок
        assert sum(re.sub(r"=\d+", "=N", o) == header for o in opts) == 1
        seen.add(header)
    assert seen == {"no-store", "no-cache", "private"}


def test_cache_control_rows_are_unambiguous():
    for _, header, pool in http_module.CACHE_ROWS:
        assert header not in pool
        assert len(set(pool)) == len(pool) >= 3
        # спорные для сценария значения не используем как дистракторы
        assert not {"must-revalidate", "max-age=0", "no-transform"} & set(pool)


def test_pagination_math_key():
    code = "be.http.pagination_math"
    kinds = set()
    for seed in range(120):
        inst = _make(code, seed)
        t = inst.prompt.text
        n = int(re.search(r"коллекции /api/\w+: (\d+)", t).group(1))
        limit = int(re.search(r"limit=(\d+)", t).group(1))
        assert 50 <= n <= 5000 and limit in (10, 20, 25, 50, 100)
        pages = -(-n // limit)
        if "Какой offset" in t:
            k = int(re.search(r"страницу (\d+)", t).group(1))
            assert 1 <= k <= pages
            assert "с единицы" in t
            expected = (k - 1) * limit
            kinds.add("offset")
        elif "последней" in t:
            expected = n - (pages - 1) * limit
            assert 1 <= expected <= limit
            kinds.add("last")
        else:
            assert "Сколько запросов" in t
            expected = math.ceil(n / limit)
            kinds.add("count")
        assert inst.kind == "number" and inst.answer == expected
    assert kinds == {"offset", "last", "count"}


# ---------------------------------------------------------------- batch B
GATEWAY_KEYWORDS = {"таймаут": "504", "некорректн": "502", "повторить позже": "503", "необработанн": "500"}


def test_gateway_status_key():
    code = "be.http.gateway_status"
    seen = set()
    for seed in range(80):
        inst = _make(code, seed)
        text = inst.prompt.text
        hit = [c for kw, c in GATEWAY_KEYWORDS.items() if kw in text]
        assert len(hit) == 1, text  # сценарий однозначно относится к одному коду
        opts = inst.prompt.options
        assert sorted(opts) == ["500", "502", "503", "504"]
        assert opts[inst.answer] == hit[0]
        _, correct, distractors = _row_for(text, http_module.GATEWAY_ROWS)
        assert correct == hit[0] and correct not in distractors
        seen.add(hit[0])
        assert inst.radicals == ("mcq", 4)
    assert seen == {"500", "502", "503", "504"}


def test_gateway_status_question_does_not_track_key():
    tails = {_make("be.http.gateway_status", s).prompt.text.rsplit(". ", 1)[1] for s in range(80)}
    assert tails == {"Какой код ответа корректен?"}


def test_idempotency_key_retry_key():
    code = "be.http.idempotency_key_retry"
    for seed in SEEDS:
        inst = _make(code, seed)
        _, correct, distractors = _row_for(inst.prompt.text, http_module.IDEMPOTENCY_ROWS)
        _assert_mcq_shape(inst, correct)
        assert correct not in distractors
        assert re.search("тот же ключ|тем же ключом|ключ тот же", inst.prompt.text)
        assert re.search(r"Idempotency-Key: [0-9a-f]{8}\b", inst.prompt.text)
        assert set(inst.prompt.options) == {correct, *distractors}


def test_put_vs_patch_key():
    code = "be.http.put_vs_patch"
    methods = set()
    for seed in range(80):
        inst = _make(code, seed)
        t = inst.prompt.text
        _, correct, distractors = _row_for(t, http_module.PUT_PATCH_ROWS)
        _assert_mcq_shape(inst, correct)
        all_fields = re.search(r"поля: ([^.]+)\.", t).group(1).split(", ")
        sent = re.search(r"Поля в теле запроса: ([^.]+)\.", t).group(1).split(", ")
        assert 4 <= len(all_fields) <= 5 and len(sent) == 2 and set(sent) < set(all_fields)
        method = "PUT" if " PUT " in t else "PATCH"
        methods.add(method)
        if method == "PUT":
            assert correct.startswith("Будут сброшены")  # полная замена представления
        else:
            assert "RFC 7396" in t and correct.startswith("Останутся прежними")
        assert not any(d.startswith(correct.split(":")[0]) for d in distractors)
    assert methods == {"PUT", "PATCH"}


@pytest.mark.parametrize("name", ["GATEWAY_ROWS", "IDEMPOTENCY_ROWS", "PUT_PATCH_ROWS"])
def test_batch_b_options_symmetric(name):
    for _, correct, distractors in getattr(http_module, name):
        lens = [len(o) for o in (correct, *distractors)]
        assert max(lens) <= 1.4 * min(lens), (name, lens)


def test_put_vs_patch_options_are_outcome_and_reason():
    for _, correct, distractors in http_module.PUT_PATCH_ROWS:
        for o in (correct, *distractors):
            outcome, reason = o.split(": ")
            assert outcome and reason and ":" not in reason


# ---------------------------------------------------------------- batch C
SAFE_METHODS = {"GET", "HEAD", "POST"}
SAFE_HEADERS = {"Accept", "Accept-Language", "Content-Language", "Content-Type"}
SAFE_CONTENT_TYPES = {"application/x-www-form-urlencoded", "multipart/form-data", "text/plain"}
OPTION_RE = re.compile(r"^([A-Z]+) (https://\S+) \(([\w-]+): (.+)\)$")


def _is_simple_request(option: str) -> bool:
    """Правило «простого запроса» из Fetch Standard, написанное независимо от генератора."""
    method, _, header, value = OPTION_RE.match(option).groups()
    if method not in SAFE_METHODS or header not in SAFE_HEADERS:
        return False
    return header != "Content-Type" or value in SAFE_CONTENT_TYPES


def test_cors_preflight_exactly_one_non_simple():
    code = "be.http.cors_preflight"
    positions = set()
    for seed in range(80):
        inst = _make(code, seed)
        opts = inst.prompt.options
        assert len(opts) == 4 and len(set(opts)) == 4 and inst.radicals == ("mcq", 4)
        assert all(OPTION_RE.match(o) for o in opts), opts
        non_simple = [i for i, o in enumerate(opts) if not _is_simple_request(o)]
        assert non_simple == [inst.answer]
        positions.add(inst.answer)
    assert positions == {0, 1, 2, 3}


def test_cors_preflight_pools_follow_fetch_rules():
    # шаблоны-пулы генератора сами не должны противоречить правилу
    for opt in http_module.CORS_SIMPLE_EXAMPLES:
        assert _is_simple_request(opt), opt
    for opt in http_module.CORS_NON_SIMPLE_EXAMPLES:
        assert not _is_simple_request(opt), opt


JSON_KIND = {int: "с числа", str: "со строки", bool: "с boolean", list: "с массива"}


BREAKING_RE = re.compile(r"^(Удалить поле|Переименовать поле|Сменить тип поля) (\w+)")


def test_breaking_change_key():
    code = "be.http.breaking_change"
    kinds, first_words, correct_longest = set(), set(), 0
    n = 300
    for seed in range(n):
        inst = _make(code, seed)
        schema = json.loads(inst.prompt.code)
        assert 4 <= len(schema) <= 6
        opts = inst.prompt.options
        _assert_four_distinct(inst)
        # независимая классификация: ломает клиентов только изменение существующего JSON-поля схемы
        breaking = [i for i, o in enumerate(opts)
                    if (m := BREAKING_RE.match(o)) and m.group(2) in schema]
        assert breaking == [inst.answer]
        opt = opts[inst.answer]
        verb = BREAKING_RE.match(opt).group(1)
        field = BREAKING_RE.match(opt).group(2)
        kinds.add(verb)
        if verb == "Переименовать поле":
            assert re.search(r" в (\w+) в ответе", opt).group(1) not in schema
        if verb == "Сменить тип поля":
            v = schema[field]
            kind = bool if isinstance(v, bool) else type(v)
            assert f"поля {field} {JSON_KIND[kind]} на" in opt
        for i, o in enumerate(opts):
            if i != inst.answer:
                first_words.add(o.split()[0])
                assert not BREAKING_RE.match(o)
        # три безопасных изменения не начинаются одним глаголом: иначе ключ виден по первому слову
        assert len({o.split()[0] for i, o in enumerate(opts) if i != inst.answer}) > 1, opts
        lens = [len(o) for o in opts]
        assert max(lens) <= 1.4 * min(lens), lens
        correct_longest += len(opt) == max(lens)
        assert "игнорируют незнакомые поля и заголовки" in inst.prompt.text
    assert kinds == {"Удалить поле", "Переименовать поле", "Сменить тип поля"}
    assert {"Добавить", "Изменить", "Переименовать", "Убрать"} <= first_words  # форма не выдаёт ключ
    assert correct_longest <= 0.5 * n


def test_breaking_change_endpoint_keeps_api_prefix():
    for seed in range(200):
        for o in _make("be.http.breaking_change", seed).prompt.options:
            if "эндпоинт" in o:
                assert re.search(r"GET /api/v\d/\w+/\w+,", o), o


def _etags(s):
    return re.findall(r'"([0-9a-f]+)"', s)


def test_conditional_request_key():
    code = "be.http.conditional_request"
    outcomes = set()
    methods = set()
    write_outcomes = set()
    matched_writes = 0
    for seed in range(200):
        inst = _make(code, seed)
        t = inst.prompt.text
        assert sorted(inst.prompt.options) == ["200", "204", "304", "412"]
        current = re.search(r"Текущий ETag ресурса \S+: \"([0-9a-f]+)\"", t).group(1)
        method = re.search(r"отправил (\w+) ", t).group(1)
        header, raw = re.search(r"с заголовком (If-[\w-]+): (.+?)\. Какой", t).groups()
        values = _etags(raw)
        assert len(current) == 8 and values and len(set(values)) == len(values)
        if method == "GET":
            assert header == "If-None-Match" and "При успешном" not in t
            expected = "304" if current in values else "200"
        else:
            assert method in ("PUT", "PATCH", "DELETE") and header == "If-Match"
            with_body = "в теле ответа" in t
            assert with_body != ("без тела" in t)
            # фраза об успехе соответствует методу: у DELETE нет «обновлённого представления»
            if method == "DELETE":
                assert "При успешном удалении" in t and "обновлённое представление" not in t, t
            else:
                assert "При успешном изменении" in t
            if current in values:  # совпал: код успеха однозначно задан фразой о теле ответа
                expected = "200" if with_body else "204"
            else:
                expected = "412"
        matched_write = method != "GET" and current in values
        write_outcomes.add(expected if method != "GET" else None)
        matched_writes += matched_write
        methods.add(method)
        outcomes.add(expected)
        assert inst.prompt.options[inst.answer] == expected and inst.radicals == ("mcq", 4)
    assert outcomes == {"200", "204", "304", "412"} and methods == {"GET", "PUT", "PATCH", "DELETE"}
    assert {"200", "204", "412"} <= write_outcomes  # запись — не только 412
    assert matched_writes > 20



# ---------------------------------------------------------------- batch D
def _simulate_per_second(capacity, rate, times):
    """Независимая симуляция: пошагово по секундам, пополнение в начале каждой целой секунды."""
    tokens, accepted = capacity, 0
    for second in range(0, max(times) + 1):
        if second > 0:
            tokens = min(capacity, tokens + rate)
        for _ in range(times.count(second)):
            if tokens >= 1:
                tokens -= 1
                accepted += 1
    return accepted


def test_token_bucket_key():
    code = "be.http.token_bucket_accepts"
    answers = set()
    for seed in range(150):
        inst = _make(code, seed)
        t = inst.prompt.text
        capacity = int(re.search(r"Ёмкость корзины \(токенов\): (\d+)", t).group(1))
        rate = int(re.search(r"Скорость пополнения \(токенов в секунду\): (\d+)", t).group(1))
        times = ast.literal_eval(inst.prompt.code.split("=", 1)[1].strip())
        assert 3 <= capacity <= 10 and rate >= 1 and 8 <= len(times) <= 12
        assert times == sorted(times) and all(isinstance(x, int) and x >= 0 for x in times)
        assert inst.kind == "number"
        assert inst.answer == _simulate_per_second(capacity, rate, times)
        assert 0 < inst.answer <= len(times)
        answers.add(inst.answer)
    assert len(answers) >= 5


def test_token_bucket_model_is_stated():
    t = _make("be.http.token_bucket_accepts", 1).prompt.text
    for phrase in ("Корзина полна в момент времени 0", "не выше ёмкости", "целые секунды", "отклоняется",
                   "Пополнение в момент t происходит до обработки запросов, пришедших в момент t"):
        assert phrase in t


def test_token_bucket_not_trivially_all_accepted():
    all_accepted = bursts = 0
    n = 300
    for seed in range(n):
        inst = _make("be.http.token_bucket_accepts", seed)
        times = ast.literal_eval(inst.prompt.code.split("=", 1)[1].strip())
        all_accepted += inst.answer == len(times)
        bursts += len(set(times)) < len(times)
    assert all_accepted <= 0.3 * n  # ответ «приняты все» не должен быть самым частым исходом
    assert bursts > 0.9 * n


def test_webhook_delivery_key():
    code = "be.http.webhook_delivery"
    for seed in SEEDS:
        inst = _make(code, seed)
        _, correct, distractors = _row_for(inst.prompt.text, http_module.WEBHOOK_ROWS)
        _assert_mcq_shape(inst, correct)
        assert correct not in distractors
        assert "at-least-once" in inst.prompt.text and re.search(r"evt_[0-9a-f]{8}", inst.prompt.text)
        # ключ — единственный вариант с дедупликацией по id; в дистракторах её нет
        assert "id" in correct and not any("id " in d.split(":")[0] for d in distractors)
        assert not any(("идемпотент" in d) for d in distractors)


def test_parallel_idempotency_race_key():
    code = "be.http.parallel_idempotency_race"
    for seed in SEEDS:
        inst = _make(code, seed)
        _, correct, distractors = _row_for(inst.prompt.text, http_module.RACE_ROWS)
        _assert_mcq_shape(inst, correct)
        assert "тома" in correct.lower() or "атомарн" in correct.lower()
        assert not any("атомарн" in d.lower() for d in distractors)
        assert "несколь" in inst.prompt.text.lower() and "ещё не записан" in inst.prompt.text


@pytest.mark.parametrize("name", ["WEBHOOK_ROWS", "RACE_ROWS"])
def test_batch_d_options_symmetric(name):
    for _, correct, distractors in getattr(http_module, name):
        lens = [len(o) for o in (correct, *distractors)]
        assert max(lens) <= 1.4 * min(lens), (name, lens)


@pytest.mark.parametrize("code", [c for c in AREA_CODES if c != "be.http.status_code"])
def test_no_number_noun_agreement_traps(code):
    """Случайное число не стоит перед существительным: нет «21 секунд», «5 объектов»."""
    for seed in range(200):
        text = _make(code, seed).prompt.text
        assert not re.search(r"(?<![/=\w])\d{1,4} [а-яё]{2,}", text), text  # id в пути и 8-значный ключ не считаются


@pytest.mark.parametrize("name", ["IDEMPOTENCY_ROWS", "PUT_PATCH_ROWS", "WEBHOOK_ROWS", "RACE_ROWS"])
def test_correct_option_is_neither_longest_nor_shortest_in_any_row(name):
    for _, correct, distractors in getattr(http_module, name):
        lens = [len(d) for d in distractors]
        assert min(lens) < len(correct) < max(lens), (name, correct, len(correct), lens)


def test_put_vs_patch_distractors_are_not_synonyms():
    """В каждой строке не более одного «прежнего» исхода и не более одного «сброшено/пусто»."""
    keep = ("Останутся прежними", "Будут объединены")
    wipe = ("Будут сброшены", "Станут пустыми")
    for _, correct, distractors in http_module.PUT_PATCH_ROWS:
        options = (correct, *distractors)
        assert sum(o.startswith(keep) for o in options) <= 1
        assert sum(o.startswith(wipe) for o in options) <= 1
        assert len({o.split(":")[0] for o in options}) == 4


def test_webhook_scene_is_coherent():
    for seed in range(100):
        text = _make("be.http.webhook_delivery", seed).prompt.text
        hits = [sc for sc in http_module.WEBHOOK_SCENES if all(part in text for part in sc)]
        assert len(hits) == 1, text
        assert "Провайдер (" not in text


def test_race_text_does_not_send_the_key_itself():
    for seed in range(60):
        text = _make("be.http.parallel_idempotency_race", seed).prompt.text
        assert "отправил Idempotency-Key" not in text and "дважды подряд" not in text


def test_number_keys_not_stated_in_text():
    """Ключ (number) не должен стоять в тексте отдельным числом, кроме совпадения с входными данными."""
    for seed in range(150):
        inst = _make("be.http.pagination_math", seed)
        numbers = [int(x) for x in re.findall(r"(?<![\w/=])\d+(?![\w/])", inst.prompt.text)]
        n = int(re.search(r"коллекции /api/\w+: (\d+)", inst.prompt.text).group(1))
        limit = int(re.search(r"limit=(\d+)", inst.prompt.text).group(1))
        k = re.search(r"страницу (\d+)", inst.prompt.text)
        inputs = {n, limit, int(k.group(1)) if k else None}
        if inst.answer not in inputs:
            assert inst.answer not in numbers, inst.prompt.text


def test_token_bucket_text_does_not_state_the_answer():
    """Ключ не стоит в тексте отдельным числом, кроме совпадения с входом (ёмкость, скорость, число запросов)."""
    checked = 0
    for seed in range(200):
        inst = _make("be.http.token_bucket_accepts", seed)
        t = inst.prompt.text
        capacity = int(re.search(r"Ёмкость корзины \(токенов\): (\d+)", t).group(1))
        rate = int(re.search(r"Скорость пополнения \(токенов в секунду\): (\d+)", t).group(1))
        times = ast.literal_eval(inst.prompt.code.split("=", 1)[1].strip())
        if int(inst.answer) in {capacity, rate, len(times)}:
            continue
        numbers = {int(x) for x in re.findall(r"(?<![\w/=.])\d+(?![\w])", t)}
        assert int(inst.answer) not in numbers, t
        checked += 1
    assert checked >= 100  # исключение — меньшинство экземпляров


def test_conditional_request_method_does_not_fix_the_key():
    """По методу ключ не угадать: у каждого метода не один исход, «DELETE → 412» и «GET → 304» не почти всегда верны."""
    keys = {}
    for seed in range(400):
        inst = _make("be.http.conditional_request", seed)
        method = re.search(r"отправил (\w+) ", inst.prompt.text).group(1)
        keys.setdefault(method, []).append(inst.prompt.options[inst.answer])
    assert set(keys) == {"GET", "PUT", "PATCH", "DELETE"}
    for method, ks in keys.items():
        assert len(set(ks)) >= 2, (method, set(ks))
    delete = keys["DELETE"]
    assert len(delete) >= 30 and {"200", "204", "412"} <= set(delete)
    assert sum(k == "412" for k in delete) <= 0.7 * len(delete), sum(k == "412" for k in delete) / len(delete)
    get = keys["GET"]  # «GET → 304» тоже не должно быть почти всегда верным
    assert sum(k == "304" for k in get) <= 0.6 * len(get), sum(k == "304" for k in get) / len(get)


def test_conditional_request_etag_count_does_not_fix_the_key():
    """У GET число ETag в If-None-Match не выдаёт ключ: и при одном, и при двух ETag 304 и 200 примерно поровну."""
    by_len = {}
    for seed in range(1000):
        inst = _make("be.http.conditional_request", seed)
        t = inst.prompt.text
        if re.search(r"отправил (\w+) ", t).group(1) != "GET":
            continue
        raw = re.search(r"с заголовком If-None-Match: (.+?)\. Какой", t).group(1)
        by_len.setdefault(len(_etags(raw)), []).append(inst.prompt.options[inst.answer])
    assert set(by_len) == {1, 2}
    for n, ks in by_len.items():
        top = max(ks.count(k) for k in set(ks))
        assert len(ks) >= 60 and top <= 0.6 * len(ks), (n, {k: ks.count(k) for k in set(ks)})


def test_conditional_request_space_counts_every_branch():
    """Пространство — сумма по шести ветвям генератора, у каждой свои подстановки."""
    m = http_module
    branches = {
        "get_match": m.ETAG_SPACE,
        "get_match_in_list": 2 * m.ETAG_PAIRS,  # текущий ETag в списке первым или вторым
        "get_nomatch": m.ETAG_PAIRS,
        "get_nomatch_in_list": m.ETAG_PAIRS * m.ETAG_NEAR,  # два чужих ETag, второй — хотя бы почти-копия
        "write_nomatch": len(m.WRITE_METHODS) * 2 * m.ETAG_PAIRS,  # метод × фраза о теле ответа
        "write_match": len(m.WRITE_METHODS) * 2 * m.ETAG_SPACE,  # метод × исход 200/204 (фраза о теле)
    }
    expected = m.PATH_VARIANTS * m.MAX_ID * sum(branches.values()) * 24
    assert REGISTRY["be.http.conditional_request"].space_size == expected
