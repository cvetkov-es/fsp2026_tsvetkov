import re
from datetime import datetime, timedelta
from itertools import combinations

import pytest

from app.assessment.bank.base import REGISTRY, rows_space
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import backend_arch as arch

from ._helpers import area_codes
from ._helpers import make as _make
from ._helpers import row_for as _row_for

AREA_CODES = area_codes("arch")
MCQ_CODES = [c for c in AREA_CODES if REGISTRY[c].fmt == "mcq"]
SEEDS = range(60)
# код -> таблица сценариев (шаблоны, правильный, пул дистракторов)
ROWS = {
    "be.arch.scale_up_vs_out": "SCALE_ROWS",
    "be.arch.queue_vs_sync": "QUEUE_ROWS",
    "be.arch.read_your_writes": "RYW_ROWS",
    "be.arch.cache_stampede": "STAMPEDE_ROWS",
    "be.arch.at_least_once_consumer": "CONSUMER_ROWS",
    "be.arch.backpressure": "BACKPRESSURE_ROWS",
}


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)
    assert r.space_estimate >= 50_000, (code, r.space_estimate)


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]
    assert len(AREA_CODES) == 13


def _numbers(text):
    """Отдельно стоящие числа текста (без частей слов и идентификаторов вида order:1234)."""
    text = re.sub(r"order:\d+", "", text)
    return {int(x) for x in re.findall(r"(?<![\w:.])\d+(?![\w.])", text)}


# ------------------------------------------------------------ calc families
def test_cache_hit_ratio_key():
    code = "be.arch.cache_hit_ratio"
    for seed in range(200):
        inst = _make(code, seed)
        t = inst.prompt.text
        h, m = map(int, re.search(r"попаданий — (\d+), промахов — (\d+)", t).groups())
        assert 10 <= h <= 9999 and 10 <= m <= 9999
        s = h + m
        # целочисленная арифметика, округление «половина вверх»
        assert inst.answer == (200 * h + s) // (2 * s)
        # дробная часть ровно .5 исключена: округление не зависит от режима
        assert not (200 * h % s == 0 and (200 * h // s) % 2 == 1)
        assert "Округлите до целого" in t
        # ключ не торчит в тексте отдельным числом, если не совпал с входом
        assert inst.answer in (h, m) or inst.answer not in _numbers(t)
    assert len({_make(code, s).answer for s in range(60)}) > 10


def test_ttl_expiry_key():
    code = "be.arch.ttl_expiry"
    wraps = 0
    for seed in range(200):
        inst = _make(code, seed)
        t = inst.prompt.text
        start = re.search(r"записали в кэш в (\d\d:\d\d:\d\d)", t).group(1)
        ttl = int(re.search(r"TTL: (\d+) с", t).group(1))
        assert 30 <= ttl <= 86399
        t0 = datetime.strptime(start, "%H:%M:%S")
        end = t0 + timedelta(seconds=ttl)
        assert inst.answer == end.strftime("%H:%M:%S")
        wraps += end.date() != t0.date()
        assert inst.prompt.answer_hint and "ЧЧ:ММ:СС" in inst.prompt.answer_hint
        assert "ровно через" in t
    assert 0.2 * 200 <= wraps <= 0.8 * 200


def test_timeout_budget_key():
    code = "be.arch.timeout_budget"
    for seed in range(200):
        inst = _make(code, seed)
        t = inst.prompt.text
        a = re.search(r"Сервис «(\w+)» вызывает", t).group(1)
        b, tb, c, tc = re.search(r"Таймаут одной попытки, мс: «(\w+)» — (\d+), «(\w+)» — (\d+)", t).groups()
        rb, rc = map(int, re.search(r"Число повторов после первой попытки: «\w+» — (\d+), «\w+» — (\d+)", t).groups())
        assert len({a, b, c}) == 3
        assert 1 <= rb <= 5 and 1 <= rc <= 5
        # попыток на вызов: 1 + повторы; каждая длится весь таймаут
        expected = sum(int(tb) for _ in range(1 + rb)) + sum(int(tc) for _ in range(1 + rc))
        assert inst.answer == expected
        assert "без пауз между попытками" in t and "1 + число повторов" in t
        assert inst.answer not in _numbers(t)


def test_quorum_read_key():
    code = "be.arch.quorum_read"
    seen = set()
    for seed in range(200):
        inst = _make(code, seed)
        t = inst.prompt.text
        n = int(re.search(r"Число реплик: (\d+)", t).group(1))
        w = int(re.search(r"подтвердить запись: (\d+)", t).group(1))
        assert 3 <= n <= 9 and 1 <= w <= n
        # независимо: наименьшее R, при котором любые R реплик пересекаются с любыми W
        r_min = next(r for r in range(1, n + 1) if all(
            set(a) & set(b) for a in combinations(range(n), r)
            for b in combinations(range(n), w)))
        assert inst.answer == r_min
        assert "R + W" not in t and ">" not in t
        assert inst.answer in (n, w) or inst.answer not in _numbers(t)
        assert re.search(r"Хранилище (Cassandra|ScyllaDB|Riak|Voldemort),", t)
        seen.add(inst.answer)
    assert len(seen) >= 6


# ----------------------------------------------------------- circuit breaker
EVENT_RE = re.compile(r"t=(\d+) с: запрос; при обращении сервис отвечает (ошибкой|успешно)")


def _breaker_state(events, f, w, tq):
    """Независимая симуляция: состояние восстанавливается как функция времени, без флага half-open."""
    opened_at, fails = None, 0   # opened_at != None  <=>  open (или half-open по времени)
    for t, ok in events:
        if opened_at is not None:
            if t < opened_at + w:
                continue  # отклонён, ничего не меняет
            if ok:
                opened_at, fails = None, 0
            else:
                opened_at = t
            continue
        fails = 0 if ok else fails + 1
        if fails >= f:
            opened_at = t
    if opened_at is None:
        return "closed"
    return "half-open" if tq >= opened_at + w else "open"


def test_circuit_breaker_key():
    code = "be.arch.circuit_breaker_state"
    keys = []
    for seed in range(300):
        inst = _make(code, seed)
        t = inst.prompt.text
        f, w, tq, events = _parse_breaker(t)
        assert 8 <= len(events) <= 12 and 2 <= f <= 5 and 10 <= w <= 60
        times = [e[0] for e in events]
        assert times == sorted(set(times)) and tq >= times[-1]
        state = _breaker_state(events, f, w, tq)
        opts = inst.prompt.options
        assert sorted(opts) == ["closed", "disabled", "half-open", "open"]
        assert opts[inst.answer] == state
        keys.append(state)
        # модель в тексте
        for phrase in ("без обращения к сервису", "пробный", "заново с момента этой ошибки",
                       "обнуляет счётчик"):
            assert phrase in t
    for s in ("closed", "open", "half-open"):
        assert keys.count(s) >= 0.2 * 300, (s, keys.count(s))
    assert "disabled" not in keys


def _parse_breaker(text):
    f = int(re.search(r"число ошибок подряд\): (\d+)", text).group(1))
    w = int(re.search(r"ожидания в open, с: (\d+)", text).group(1))
    tq = int(re.search(r"состояние у breaker в момент t=(\d+) с,", text).group(1))
    events = [(int(a), b == "успешно") for a, b in EVENT_RE.findall(text)]
    return f, w, tq, events


def test_circuit_breaker_question_is_one_template_for_both_branches():
    """Вопрос в момент последнего события и позже — один шаблон (не коррелирует с ключом), и он явно
    говорит, что событие, пришедшее в момент вопроса, уже обработано."""
    tails, same_moment = set(), 0
    for seed in range(300):
        text = _make("be.arch.circuit_breaker_state", seed).prompt.text
        _, _, tq, events = _parse_breaker(text)
        same_moment += tq == events[-1][0]
        tails.add(re.sub(r"\d+", "N", text.rsplit("\n", 1)[1]))
    assert same_moment >= 20
    assert len(tails) == 1, tails
    tail = tails.pop()
    assert "включая пришедшие в этот момент" in tail and "уже обработаны" in tail, tail


# Фикстуры, проверенные вручную: (F, W, события (t, успех), tq, состояние)
BREAKER_FIXTURES = [
    # 1: ошибки в t=1,2 -> open@2; t=5 отклонён (5 < 12); t=12 пробный успех -> closed
    (2, 10, [(1, False), (2, False), (5, True), (12, True)], 13, "closed"),
    # 2: open@2; t=12 пробный провал -> open@12 (отсчёт заново); t=15 отклонён; 12+10=22
    (2, 10, [(1, False), (2, False), (12, False), (15, True)], 21, "open"),
    (2, 10, [(1, False), (2, False), (12, False), (15, True)], 22, "half-open"),
    # 3: успех в t=2 обнуляет счётчик; три ошибки подряд 3,4,5 -> open@5; t=24 отклонён; 5+20=25
    (3, 20, [(1, False), (2, True), (3, False), (4, False), (5, False), (24, True)], 24, "open"),
    (3, 20, [(1, False), (2, True), (3, False), (4, False), (5, False), (24, True)], 25, "half-open"),
    # 4: ошибки не подряд (успех между ними) -> порог не достигнут
    (2, 10, [(1, False), (2, True), (3, False), (4, True)], 100, "closed"),
    # 5: пробный запрос ровно в opened+W (t=12): граница включена; успех -> closed
    (2, 10, [(1, False), (2, False), (12, True)], 12, "closed"),
    # 6: после возврата в closed счётчик чист: одна ошибка порог 2 не открывает
    (2, 10, [(1, False), (2, False), (12, True), (13, False)], 14, "closed"),
]


@pytest.mark.parametrize("f,w,events,tq,expected", BREAKER_FIXTURES)
def test_circuit_breaker_fixtures(f, w, events, tq, expected):
    assert _breaker_state(events, f, w, tq) == expected
    assert arch._cb_simulate(events, f, w, tq)[0] == expected


def _alt_lazy_half_open(events, f, w, tq):
    """Иное прочтение: half-open наступает только по приходу запроса, без запроса остаётся open."""
    state = _breaker_state(events, f, w, tq)
    return "open" if state == "half-open" else state


def _alt_rejected_restart_timer(events, f, w, tq):
    """Иное прочтение: отклонённый в open запрос продлевает ожидание (отсчёт заново)."""
    opened_at, fails = None, 0
    for t, ok in events:
        if opened_at is not None:
            if t < opened_at + w:
                opened_at = t
                continue
            opened_at, fails = (None, 0) if ok else (t, 0)
            continue
        fails = 0 if ok else fails + 1
        if fails >= f:
            opened_at = t
    if opened_at is None:
        return "closed"
    return "half-open" if tq >= opened_at + w else "open"


def _alt_total_failures(events, f, w, tq):
    """Иное прочтение: успех не обнуляет счётчик (ошибки считаются суммарно, а не подряд)."""
    opened_at, fails = None, 0
    for t, ok in events:
        if opened_at is not None:
            if t < opened_at + w:
                continue
            opened_at, fails = (None, 0) if ok else (t, 0)
            continue
        fails += 0 if ok else 1
        if fails >= f:
            opened_at = t
    if opened_at is None:
        return "closed"
    return "half-open" if tq >= opened_at + w else "open"


@pytest.mark.parametrize("alt,share", [(_alt_lazy_half_open, 0.25), (_alt_rejected_restart_timer, 0.05),
                                       (_alt_total_failures, 0.08)])
def test_circuit_breaker_alternative_readings_change_key(alt, share):
    n = changed = 0
    for seed in range(300):
        f, w, tq, events = _parse_breaker(_make("be.arch.circuit_breaker_state", seed).prompt.text)
        changed += alt(events, f, w, tq) != _breaker_state(events, f, w, tq)
        n += 1
    assert changed >= share * n, (alt.__name__, changed)


def test_circuit_breaker_surface_heuristic_scores_near_chance():
    """Эвристика «tq позже последнего события -> half-open, иначе по ответу последнего события»."""
    n = hits = 0
    for seed in range(600):
        inst = _make("be.arch.circuit_breaker_state", seed)
        _, _, tq, events = _parse_breaker(inst.prompt.text)
        guess = "half-open" if tq > events[-1][0] else ("closed" if events[-1][1] else "open")
        hits += inst.prompt.options[inst.answer] == guess
        n += 1
    assert hits <= 0.45 * n, hits / n


def test_circuit_breaker_last_outcome_heuristic_is_not_decisive():
    """Эвристика «по ответу последнего события»: success -> closed, ошибка -> open."""
    hits = 0
    for seed in range(600):
        inst = _make("be.arch.circuit_breaker_state", seed)
        _, _, _, events = _parse_breaker(inst.prompt.text)
        hits += inst.prompt.options[inst.answer] == ("closed" if events[-1][1] else "open")
    assert hits <= 0.5 * 600, hits / 600


# --------------------------------------------------------------------- saga
def test_saga_compensation_order_key():
    code = "be.arch.saga_compensation_order"
    ks = []
    for seed in range(200):
        inst = _make(code, seed)
        t = inst.prompt.text
        title = re.search(r"Сага «(.+?)»", t).group(1)
        steps = dict(arch.SAGAS)[title]
        shown_actions = re.findall(r"^(\d+)\) (.+)$", t, re.M)
        n = len(shown_actions)
        assert 4 <= n <= 6
        assert [a for _, a in shown_actions] == [s[0] for s in steps[:n]]
        k = int(re.search(r"Шаг (\d+) завершился ошибкой", t).group(1))
        assert 4 <= k <= n
        ks.append(k)
        comps = inst.prompt.steps
        assert sorted(comps) == sorted(s[1] for s in steps[:k - 1])
        # компенсации успешных шагов в обратном порядке
        wanted = [steps[i][1] for i in range(k - 2, -1, -1)]
        got = [comps[i - 1] for i in inst.answer]
        assert got == wanted
        assert tuple(comps) != tuple(s[1] for s in steps[k - 2::-1])  # исходный порядок показа не готовый ответ
        # шаги k и позже не компенсируются
        assert not set(comps) & {s[1] for s in steps[k - 1:]}
        assert len(inst.answer) == k - 1 >= 3
        assert "экземпляр саги №" in t and "заказ №" not in t
        assert "в том порядке, в котором оркестратор саги должен их выполнить" in t
    assert {4, 5, 6} <= set(ks)


def test_saga_pool_is_coherent():
    titles = [t for t, _ in arch.SAGAS]
    assert len(set(titles)) == len(titles) >= 4
    for _, steps in arch.SAGAS:
        assert len(steps) == 6
        flat = [x for s in steps for x in s]
        assert len(set(flat)) == 12  # нет дубликатов действий и компенсаций


# -------------------------------------------------------------- MCQ shared
def _rows(code):
    return getattr(arch, ROWS[code])


@pytest.mark.parametrize("code", MCQ_CODES)
def test_mcq_options_come_from_scenario_row(code):
    rows = _rows(code)
    positions = set()
    for seed in range(120):
        inst = _make(code, seed)
        opts = inst.prompt.options
        assert len(opts) == 4 and len(set(opts)) == 4
        assert inst.radicals == ("mcq", 4)
        _, correct, pool = _row_for(inst.prompt.text, rows)
        assert opts[inst.answer] == correct
        assert correct not in pool
        wrong = [o for i, o in enumerate(opts) if i != inst.answer]
        assert all(o in pool for o in wrong)
        positions.add(inst.answer)
    assert positions == {0, 1, 2, 3}


@pytest.mark.parametrize("code", MCQ_CODES)
def test_mcq_rows_are_clean(code):
    rows = _rows(code)
    corrects = [r[1] for r in rows]
    pools = [x for r in rows for x in r[2]]
    assert len(set(corrects)) == len(corrects)
    if code != "be.arch.scale_up_vs_out":  # там «противоположное масштабирование» — дистрактор по замыслу
        assert not set(corrects) & set(pools)  # правильный ответ одной строки не дистрактор другой
    for templates, correct, pool in rows:
        assert len(set(pool)) == len(pool) >= 3
        allopts = [correct, *pool]
        assert max(map(len, allopts)) <= 1.4 * min(map(len, allopts)), allopts
        # форма не выдаёт ключ: у ответа свой первый глагол не один на всех
        assert len({o.split()[0] for o in allopts}) >= 3
        assert len(templates) >= 1


@pytest.mark.parametrize("code", MCQ_CODES)
def test_key_is_neither_strictly_longest_nor_shortest_in_its_row(code):
    for _, correct, pool in _rows(code):
        lens = [len(x) for x in pool]
        assert min(lens) <= len(correct) <= max(lens), (correct, len(correct), lens)
        assert not (len(correct) > max(lens) or len(correct) < min(lens))


@pytest.mark.parametrize("code", MCQ_CODES)
def test_same_question_tail_in_every_row(code):
    tails = set()
    for templates, _, _ in _rows(code):
        for t in templates:
            tails.add(re.split(r"(?<=[.])\s", t.strip())[-1])
    assert len(tails) == 1, tails


def test_scale_up_scenarios_match_action():
    code = "be.arch.scale_up_vs_out"
    seen = set()
    for seed in range(200):
        inst = _make(code, seed)
        t = inst.prompt.text
        opts = inst.prompt.options
        correct = opts[inst.answer]
        horizontal = "одинаков" in t and "RAM" not in t
        vertical = "RAM" in t
        assert horizontal != vertical
        assert correct == ("Горизонтальное масштабирование" if horizontal else "Вертикальное масштабирование")
        # противоположное масштабирование всегда среди вариантов: «масштабирование» не выдаёт ключ
        assert sum("масштабирование" in o for o in opts) == 2
        seen.add(correct)
        assert "Как называется" in t
    assert len(seen) == 2


def test_stateless_vs_db_scenarios():
    texts = [_make("be.arch.scale_up_vs_out", s).prompt.text for s in range(200)]
    assert any("БД" in t for t in texts)
    assert any("без состояния" in t for t in texts)
    for t in texts:
        # в сценарии назван сам приём, а не проблема, решаемая репликацией/шардированием
        assert "реплик" not in t.lower() and "шард" not in t.lower()


def test_read_your_writes_scenario_is_replica_lag():
    for seed in range(60):
        t = _make("be.arch.read_your_writes", seed).prompt.text
        assert "primary" in t and "асинхронной реплики" in t and "Лаг репликации" in t


def test_cache_stampede_scenario_numbers():
    rps_seen = set()
    for seed in range(200):
        t = _make("be.arch.cache_stampede", seed).prompt.text
        rps = int(re.search(r"запросов/с: (\d+)", t).group(1))
        assert 100 <= rps <= 10000
        rps_seen.add(rps)
    assert len(rps_seen) > 100


def test_consumer_scenario_is_coherent():
    for seed in range(200):
        t = _make("be.arch.at_least_once_consumer", seed).prompt.text
        svc, event, effect = re.search(r"Сервис «(\w+)» читает события (\w+) .*? и для каждого (.+?)\.", t).groups()
        assert (svc, event, effect) in arch.CONSUMERS
        assert "at-least-once" in t


def test_backpressure_producer_faster():
    for seed in range(200):
        t = _make("be.arch.backpressure", seed).prompt.text
        p, c = map(int, re.search(r"продюсер — (\d+) сообщ\./с, консьюмер — (\d+) сообщ\./с", t).groups())
        assert p > c > 0


# ------------------------------------------------------------ text hygiene
@pytest.mark.parametrize("code", AREA_CODES)
def test_no_numeral_noun_agreement_traps(code):
    """Число сразу перед русским существительным, требующим согласования, не допускается."""
    allowed = {"с", "мс", "ГБ", "сообщ", "завершился"}  # «Шаг 4 завершился» — порядковый номер
    for seed in range(150):
        inst = _make(code, seed)
        texts = [inst.prompt.text, *(inst.prompt.options or ()), *(inst.prompt.steps or ())]
        for text in texts:
            for word in re.findall(r"\d+ ([А-Яа-яЁё]+)", text):
                assert word in allowed, (code, word, text)


def test_pools_have_no_duplicates():
    for name in ("SVCS", "CACHES", "PERIODS", "KEYS", "STORES", "OBJECTS", "RAM_PAIRS", "PAIRS_SERVICES"):
        pool = getattr(arch, name)
        assert len(set(pool)) == len(pool), name
    assert len(set(arch.CONSUMERS)) == len(arch.CONSUMERS)


def test_declared_space_is_at_least_50000():
    for code in AREA_CODES:
        assert REGISTRY[code].space_size >= 50_000, code



def test_consumer_group_not_larger_than_partitions():
    for seed in range(300):
        t = _make("be.arch.at_least_once_consumer", seed).prompt.text
        parts, group = map(int, re.search(r"число партиций: (\d+), потребителей в группе: (\d+)", t).groups())
        assert 2 <= group <= parts


def test_backpressure_options_and_requirement_do_not_echo():
    for seed in range(200):
        inst = _make("be.arch.backpressure", seed)
        assert not any("429" in o or "неограничен" in o for o in inst.prompt.options)
        assert "отказ" not in inst.prompt.text and "429" not in inst.prompt.text


def test_two_ryw_distractors_do_not_share_opening():
    firsts = [" ".join(x.split()[:2]) for x in arch.RYW_POOL]
    assert len(set(firsts)) == len(firsts)


def test_space_is_derived_from_pools():
    """Объявленное пространство — функция именованных пулов: расчёт воспроизводится независимо."""
    import math
    f = REGISTRY
    assert f["be.arch.ttl_expiry"].space_size == (
        arch.SECONDS_PER_DAY * (arch.TTL_MAX - arch.TTL_MIN + 1) * len(arch.KEYS))
    assert f["be.arch.quorum_read"].space_size == sum(arch.QUORUM_N) * len(arch.STORES) * (
        arch.ID_COUNT - arch.QUORUM_ID_MIN + 1)
    assert f["be.arch.queue_vs_sync"].space_size == rows_space(
        arch.QUEUE_ROWS, arch._QUEUE_SIZES, extra=math.comb(len(arch.QUEUE_POOL), 3) * 24)
