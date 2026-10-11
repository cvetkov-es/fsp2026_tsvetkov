"""Семейства Data/Analytics · статистика и эксперименты.

Конвенция вычисления (σ генеральной совокупности, z = 1.96, двусторонний тест и т. п.) всегда названа в тексте;
параметры подобраны так, чтобы ответ не лежал у границы округления.
"""
import math
import random
import statistics

from app.assessment.bank.base import Generated, Prompt, Table, family, mcq

METRIC_CONTEXTS = ("время ответа сервера, мс", "сумма чека, руб.", "оценка курса по 100-балльной шкале",
                   "длительность сессии, мин", "число товаров в корзине", "время доставки, ч")


def _far(x: float, digits: int) -> bool:
    """x далеко от границы округления до digits знаков (ответ не зависит от способа округления)."""
    return abs((x * 10**digits) % 1 - 0.5) > 0.01


def _values_code(xs: list[int]) -> str:
    return f"values = [{', '.join(map(str, xs))}]"


# --- da.stats.mean_median ---------------------------------------------------------------
@family(code="da.stats.mean_median", specialization="data", area="stats", level=1, fmt="calc",
        space_size=len(METRIC_CONTEXTS) * 2 * 100**7, median_time_s=45)
def mean_median(rng: random.Random) -> Generated:
    ask_median = rng.random() < 0.5
    while True:
        xs = [rng.randint(1, 100) for _ in range(rng.randint(7, 11))]
        if rng.random() < 0.5:
            xs[rng.randrange(len(xs))] = rng.randint(150, 400)  # выброс: среднее уходит от медианы
        mean, median = statistics.fmean(xs), statistics.median(xs)
        if _far(mean, 2) and round(mean, 2) != round(median, 2):
            break
    context = rng.choice(METRIC_CONTEXTS)
    what = "медиану" if ask_median else "среднее арифметическое"
    text = f"{context[0].upper() + context[1:]}: значения в коде. Найдите {what} этих значений."
    return Generated("number", Prompt(text=text, code=_values_code(xs), language="python",
                                      answer_hint="Число; если не целое — с двумя знаками после запятой"),
                     round(median if ask_median else mean, 2), ("central_tendency",))


# --- da.stats.percent_change ------------------------------------------------------------------
PC_METRICS = ("выручка", "число заказов", "DAU", "конверсия в покупку (в базисных пунктах)", "средний чек",
              "число регистраций")


@family(code="da.stats.percent_change", specialization="data", area="stats", level=1, fmt="calc",
        space_size=len(PC_METRICS) * 4951 * 4950, median_time_s=40)
def percent_change(rng: random.Random) -> Generated:
    while True:
        was, now = rng.randint(50, 5000), rng.randint(50, 5000)
        change = (now - was) / was * 100
        if was != now and _far(change, 1):
            break
    text = (f"Метрика «{rng.choice(PC_METRICS)}» за прошлый и текущий месяц: было {was}, стало {now}. На сколько "
            "процентов она изменилась?")
    return Generated("number", Prompt(text=text, answer_hint="Число процентов с одним знаком после запятой; падение — "
                                                             "отрицательное число, например -12.5"),
                     round(change, 1), ("percent_change",))


# --- da.stats.population_std -------------------------------------------------------------------
@family(code="da.stats.population_std", specialization="data", area="stats", level=2, fmt="calc",
        space_size=len(METRIC_CONTEXTS) * 50**6, median_time_s=60)
def population_std(rng: random.Random) -> Generated:
    while True:
        xs = [rng.randint(1, 50) for _ in range(rng.randint(6, 10))]
        sigma = statistics.pstdev(xs)
        if _far(sigma, 2) and round(sigma, 2) != round(statistics.stdev(xs), 2):
            break
    context = rng.choice(METRIC_CONTEXTS)
    text = (f"{context[0].upper() + context[1:]}: значения в коде. Найдите стандартное отклонение σ "
            "генеральной совокупности (сумма квадратов отклонений делится на n, а не на n − 1).")
    return Generated("number", Prompt(text=text, code=_values_code(xs), language="python",
                                      answer_hint="Число с двумя знаками после запятой"),
                     round(sigma, 2), ("population_std",))


# --- da.stats.conditional_probability ------------------------------------------------------------
COND_PAIRS = (  # (событие A: да / нет, событие B: да / нет)
    (("кликнул на баннер", "не кликнул на баннер"), ("купил", "не купил")),
    (("открыл письмо", "не открыл письмо"), ("перешёл на сайт", "не перешёл на сайт")),
    (("пришёл из рекламы", "пришёл из поиска"), ("зарегистрировался", "не зарегистрировался")),
    (("использовал промокод", "не использовал промокод"), ("вернулся через месяц", "не вернулся через месяц")),
)


@family(code="da.stats.conditional_probability", specialization="data", area="stats", level=2, fmt="calc",
        space_size=len(COND_PAIRS) * 3 * 296**4 // 10, median_time_s=55)
def conditional_probability(rng: random.Random) -> Generated:
    (a_yes, a_no), (b_yes, b_no) = rng.choice(COND_PAIRS)
    form = rng.choice(("b|a", "b|not_a", "a|b"))
    while True:
        a, b, c, d = (rng.randint(5, 300) for _ in range(4))
        num, den = {"b|a": (a, a + b), "b|not_a": (c, c + d), "a|b": (a, a + c)}[form]
        if _far(num / den, 2):
            break
    event, given = {"b|a": (b_yes, a_yes), "b|not_a": (b_yes, a_no), "a|b": (a_yes, b_yes)}[form]
    table = Table("Пользователи", ("группа", b_yes, b_no), ((a_yes, a, b), (a_no, c, d)))
    text = (f"Таблица — число пользователей по двум признакам. Какова оценка вероятности того, что пользователь "
            f"{event}, если он {given}?")
    return Generated("number", Prompt(text=text, tables=(table,), answer_hint="Число от 0 до 1 с двумя знаками после "
                                                                             "запятой, например 0.37"),
                     round(num / den, 2), ("conditional_probability",))


# --- da.stats.weighted_average ------------------------------------------------------------------------
WEIGHTED_CONTEXTS = (  # (вступление, колонки, диапазон значений)
    ("Отзывы о товаре сгруппированы по оценке", ("оценка", "число отзывов"), (1, 5)),
    ("Товар закупали партиями по разной цене", ("цена за штуку, руб.", "штук в партии"), (50, 900)),
    ("Оценки студента по курсам разного объёма", ("оценка", "кредиты курса"), (2, 5)),
    ("Заказы по складам с разным временем доставки", ("время доставки, ч", "число заказов"), (4, 72)),
)


@family(code="da.stats.weighted_average", specialization="data", area="stats", level=2, fmt="calc",
        space_size=len(WEIGHTED_CONTEXTS) * 200**3 * 4, median_time_s=55)
def weighted_average(rng: random.Random) -> Generated:
    intro, cols, (lo, hi) = rng.choice(WEIGHTED_CONTEXTS)
    while True:
        values = rng.sample(range(lo, hi + 1), min(rng.randint(3, 5), hi - lo + 1))
        weights = [rng.randint(1, 200) for _ in values]
        w = sum(v * k for v, k in zip(values, weights, strict=True)) / sum(weights)
        if _far(w, 2) and round(w, 2) != round(statistics.fmean(values), 2):
            break
    table = Table("Данные", cols, tuple(zip(values, weights, strict=True)))
    text = f"{intro} (таблица). Найдите среднее значение «{cols[0]}», взвешенное по «{cols[1]}»."
    return Generated("number", Prompt(text=text, tables=(table,), answer_hint="Число с двумя знаками после запятой"),
                     round(w, 2), ("weighted_mean",))


# --- da.stats.simpsons_paradox ---------------------------------------------------------------------------
SIMPSON_SEGMENTS = (("мобильные", "десктоп"), ("новые", "вернувшиеся"), ("Москва", "регионы"),
                    ("органика", "реклама"))
SIMPSON_OPTIONS = ("{x} лучше в каждом сегменте, но {y} лучше по сумме сегментов",
                   "{x} лучше и в каждом сегменте, и по сумме сегментов")


def _simpson_rows(rng: random.Random, paradox: bool) -> tuple[list[tuple], str, str]:
    """Строки (вариант, сегмент, посетители, покупки), победитель в сегментах и по сумме."""
    low, high = rng.sample(rng.choice(SIMPSON_SEGMENTS), 2)
    while True:
        x = rng.choice(("A", "B"))
        y = "B" if x == "A" else "A"
        r_low, r_high = rng.uniform(0.02, 0.06), rng.uniform(0.10, 0.25)
        lift = rng.uniform(0.005, 0.02)
        rates = {(x, low): r_low + lift, (y, low): r_low, (x, high): r_high + lift, (y, high): r_high}
        if paradox:  # победитель сегментов почти весь в «слабом» сегменте, проигравший — в «сильном»
            traffic = {(x, low): rng.randint(2000, 9000), (x, high): rng.randint(200, 900),
                       (y, low): rng.randint(200, 900), (y, high): rng.randint(2000, 9000)}
        else:
            n1, n2 = rng.randint(1000, 5000), rng.randint(1000, 5000)
            traffic = {(x, low): n1, (y, low): n1 + rng.randint(-300, 300), (x, high): n2,
                       (y, high): n2 + rng.randint(-300, 300)}
        rows = [(v, s, traffic[(v, s)], round(rates[(v, s)] * traffic[(v, s)])) for v in ("A", "B") for s in (low, high)]
        rate = {(v, s): c / n for v, s, n, c in rows}
        seg_ok = all(rate[(x, s)] - rate[(y, s)] > 0.002 for s in (low, high))
        tot = {v: sum(c for vv, _, _, c in rows if vv == v) / sum(n for vv, _, n, _ in rows if vv == v) for v in "AB"}
        winner = max(tot, key=tot.get)
        if seg_ok and abs(tot["A"] - tot["B"]) > 0.002 and (winner != x) == paradox:
            return rows, x, winner


@family(code="da.stats.simpsons_paradox", specialization="data", area="stats", level=3, fmt="calc",
        space_size=len(SIMPSON_SEGMENTS) * 2 * 2 * 7000 * 700 * 24, median_time_s=90)
def simpsons_paradox(rng: random.Random) -> Generated:
    rows, seg_winner, total_winner = _simpson_rows(rng, rng.random() < 0.7)
    statements = {}
    for x in ("A", "B"):
        y = "B" if x == "A" else "A"
        statements[(x, y)] = SIMPSON_OPTIONS[0].format(x=x, y=y)
        statements[(x, x)] = SIMPSON_OPTIONS[1].format(x=x)
    key = statements[(seg_winner, total_winner)]
    text = ("Результаты A/B-теста по двум сегментам аудитории — в таблице; метрика — конверсия в покупку (покупки / "
            "посетители). Какой вывод верен?")
    table = Table("Эксперимент", ("вариант", "сегмент", "посетители", "покупки"), tuple(rows))
    return mcq(rng, text, key, [s for s in statements.values() if s != key], tables=(table,),
               radicals=("simpson", 4))


# --- da.stats.srm_check -------------------------------------------------------------------------------------
SRM_YES = "Да, есть SRM: доли групп значимо отличаются от 50/50, и результатам теста доверять нельзя"
SRM_NO = "Нет: отклонение от 50/50 в пределах случайного, результаты можно анализировать дальше"
SRM_WRONG = (
    "Да, есть SRM, но результаты всё равно можно использовать, если перевзвесить группы по размеру",
    "Проверить нельзя: для SRM нужны конверсии групп, одних размеров групп недостаточно",
)
SRM_PRODUCTS = ("новая кнопка оплаты", "редизайн карточки товара", "новый онбординг", "рекомендации на главной",
                "упрощённая регистрация")


@family(code="da.stats.srm_check", specialization="data", area="stats", level=3, fmt="calc",
        space_size=len(SRM_PRODUCTS) * 195_000 * 50, median_time_s=80)
def srm_check(rng: random.Random) -> Generated:
    srm = rng.random() < 0.5
    while True:
        total = rng.randint(5000, 200_000)
        delta = rng.randint(1, max(2, int(3 * math.sqrt(total))))
        n_a = total // 2 + delta * rng.choice((1, -1))
        n_b = total - n_a
        chi2 = (n_a - n_b) ** 2 / total
        p = math.erfc(math.sqrt(chi2 / 2))
        if (p < 0.0005 if srm else p > 0.002) and n_a != n_b:
            break
    text = (f"Эксперимент «{rng.choice(SRM_PRODUCTS)}»: трафик делится 50/50. Размер группы A — {n_a}, группы "
            f"B — {n_b}. Есть ли sample ratio mismatch при пороге p < 0.001? Для χ² с одной степенью свободы этому "
            "порогу соответствует χ² > 10.83.")
    key = SRM_YES if srm else SRM_NO
    return mcq(rng, text, key, [SRM_NO if srm else SRM_YES, *SRM_WRONG], radicals=("srm_chi2", 4))


# --- da.stats.ci_halfwidth -----------------------------------------------------------------------------------
@family(code="da.stats.ci_halfwidth", specialization="data", area="stats", level=3, fmt="calc",
        space_size=49_801 * 500, median_time_s=80)
def ci_halfwidth(rng: random.Random) -> Generated:
    while True:
        n = rng.randint(200, 50_000)
        k = rng.randint(max(1, n // 100), max(2, n // 3))
        p = k / n
        h = 1.96 * math.sqrt(p * (1 - p) / n)
        if _far(h, 4):
            break
    text = (f"Посетителей: {n}, покупок: {k}. Найдите полуширину 95% доверительного интервала для доли покупок по "
            "нормальной аппроксимации: 1.96 · √(p(1 − p) / n), где p — наблюдаемая доля.")
    return Generated("number", Prompt(text=text, answer_hint="Число с четырьмя знаками после запятой, например 0.0123"),
                     round(h, 4), ("proportion_ci",))


# --- da.stats.ab_z_test ---------------------------------------------------------------------------------------
AB_OPTIONS = {
    "b": "Различие значимо: B лучше A",
    "a": "Различие значимо: A лучше B",
    "ns": "Различие не значимо на уровне α = 0.05",
}
AB_WRONG = "Сравнивать нельзя: размеры групп разные, z-тест к ним неприменим"


@family(code="da.stats.ab_z_test", specialization="data", area="stats", level=4, fmt="calc",
        space_size=10**10, median_time_s=110)
def ab_z_test(rng: random.Random) -> Generated:
    want = rng.choice(("a", "b", "ns"))
    while True:
        n_a, n_b = rng.randint(800, 20_000), rng.randint(800, 20_000)
        base = rng.uniform(0.02, 0.2)
        lift = rng.uniform(-0.03, 0.03) * base * (4 if want != "ns" else 1)
        c_a, c_b = round(base * n_a), round((base + lift) * n_b)
        p = (c_a + c_b) / (n_a + n_b)
        z = (c_b / n_b - c_a / n_a) / math.sqrt(p * (1 - p) * (1 / n_a + 1 / n_b))
        got = "ns" if abs(z) <= 1.96 else "b" if z > 0 else "a"
        if got == want and not 1.8 < abs(z) < 2.15 and n_a != n_b:
            break
    table = Table("A/B-тест", ("вариант", "пользователи", "конверсии"), (("A", n_a, c_a), ("B", n_b, c_b)))
    text = ("Двусторонний z-тест для двух долей, α = 0.05: z = (p_B − p_A) / √(p(1 − p)(1/n_A + 1/n_B)), где p — "
            "общая доля конверсий обеих групп; различие значимо, если |z| > 1.96. Какой вывод верен?")
    return mcq(rng, text, AB_OPTIONS[want], [*(v for k, v in AB_OPTIONS.items() if k != want), AB_WRONG],
               tables=(table,), radicals=("two_proportion_z", 4))


# --- da.stats.bonferroni_count ------------------------------------------------------------------------------
BONF_METRICS = ("конверсия", "средний чек", "выручка на пользователя", "удержание D7", "время на сайте",
                "глубина просмотра", "доля отказов", "число заказов", "доля повторных покупок", "CTR рекомендаций")


@family(code="da.stats.bonferroni_count", specialization="data", area="stats", level=4, fmt="calc",
        space_size=10**9, median_time_s=90)
def bonferroni_count(rng: random.Random) -> Generated:
    alpha = rng.choice((0.05, 0.1))
    while True:
        m = rng.randint(5, 10)
        threshold = alpha / m
        ps = [round(rng.choice((rng.uniform(0.0001, threshold), rng.uniform(threshold, alpha), rng.uniform(alpha, 0.6))), 4)
              for _ in range(m)]
        count = sum(p < threshold for p in ps)
        if all(abs(p - threshold) > 0.1 * threshold for p in ps) and sum(p < alpha for p in ps) != count:
            break
    table = Table("p-значения", ("метрика", "p"), tuple(zip(rng.sample(BONF_METRICS, m), ps, strict=True)))
    text = (f"В A/B-тесте проверили {m} метрик, по каждой — свой тест (p-значения в таблице). С поправкой "
            f"Бонферрони при общем уровне значимости α = {alpha} сколько метрик признаются значимыми?")
    return Generated("number", Prompt(text=text, tables=(table,), answer_hint="Целое число"), count, ("bonferroni",))


# --- da.stats.peeking ---------------------------------------------------------------------------------------------
PEEKING_EXPERIMENTS = ("новая главная", "кнопка покупки в один клик", "бесплатная доставка от 1500 ₽",
                       "персональные рекомендации", "упрощённая анкета")
PEEKING_CORRECT = (
    "Проверки с остановкой при первой значимости завышают долю ложноположительных: ошибка I рода выше 5%",
    "Каждый просмотр — ещё шанс случайно увидеть p < 0.05, поэтому ошибка I рода сильно больше 5%",
)
PEEKING_WRONG = (
    "Всё корректно: частые проверки только повышают мощность теста, а ошибка I рода остаётся на уровне 5%",
    "Подглядывать можно, если размеры групп равны: тогда вероятность ложной значимости совсем не меняется",
    "Проблема лишь в длительности: тест идёт дольше, а на долю ложных срабатываний это не влияет",
    "Ранняя остановка уменьшает ошибку I рода, хотя и немного завышает оценку размера эффекта",
)


@family(code="da.stats.peeking", specialization="data", area="stats", level=4, fmt="mcq",
        space_size=len(PEEKING_EXPERIMENTS) * 20 * 3 * len(PEEKING_CORRECT) * math.comb(len(PEEKING_WRONG), 3) * 24,
        median_time_s=90)
def peeking(rng: random.Random) -> Generated:
    days = rng.randint(10, 29)
    when = rng.choice(("каждое утро", "после каждой тысячи пользователей", "каждый вечер"))
    stop = rng.randint(3, days - 2)
    text = (f"Эксперимент «{rng.choice(PEEKING_EXPERIMENTS)}» запланирован на {days} дн. Аналитик смотрит p-значение "
            f"{when} и останавливает тест, как только видит p < 0.05; это случилось на {stop}-й день. Что не так "
            "с таким выводом?")
    return mcq(rng, text, rng.choice(PEEKING_CORRECT), rng.sample(PEEKING_WRONG, 3))


# --- da.stats.sample_size -------------------------------------------------------------------------------------------
SIZE_METRICS = ("конверсия в покупку", "конверсия в регистрацию", "конверсия в подписку", "CTR кнопки",
                "доля оплаченных заказов")
SIZE_EXPERIMENTS = ("новый лендинг", "другой текст кнопки", "короткая форма", "новый тариф", "push-напоминание",
                    "бонус за первый заказ")


@family(code="da.stats.sample_size", specialization="data", area="stats", level=5, fmt="calc",
        # метрика × эксперимент × базовая конверсия (тысячные) × MDE (тысячные); часть отбрасывается у целых
        space_size=len(SIZE_METRICS) * len(SIZE_EXPERIMENTS) * 281 * 46 // 2, median_time_s=140)
def sample_size(rng: random.Random) -> Generated:
    while True:
        p1 = rng.randint(20, 300) / 1000
        mde = rng.randint(5, 50) / 1000
        p2 = p1 + mde
        n = (1.96 + 0.84) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / mde**2
        if 0.01 < n % 1 < 0.99:
            break
    text = (f"Эксперимент «{rng.choice(SIZE_EXPERIMENTS)}», метрика — {rng.choice(SIZE_METRICS)}. Нужно рассчитать "
            f"размер выборки на группу: базовая конверсия {p1}, минимальный "
            f"обнаруживаемый эффект (абсолютный) MDE {mde}, α = 0.05 (двусторонний), мощность 0.8. Формула: "
            "n = (1.96 + 0.84)² · (p₁(1 − p₁) + p₂(1 − p₂)) / MDE², где p₂ = p₁ + MDE. Сколько пользователей нужно в "
            "каждой группе?")
    return Generated("number", Prompt(text=text, answer_hint="Целое число (округлите вверх)"), math.ceil(n),
                     ("sample_size_two_proportions",))


# --- da.stats.regression_to_mean --------------------------------------------------------------------------------------
RTM_CONTEXTS = (  # (кого отобрали, показатель, что сделали)
    ("магазинов сети", "по выручке", "провели тренинг для продавцов"),
    ("курьеров", "по скорости доставки", "выдали новые маршруты в приложении"),
    ("школ района", "по среднему баллу ЕГЭ", "запустили программу наставничества"),
    ("менеджеров по продажам", "по числу сделок", "назначили еженедельные встречи с руководителем"),
    ("рекламных кампаний", "по CTR", "обновили креативы"),
)
RTM_CORRECT = (
    "Нет: худшие по отбору в среднем улучшатся и сами (регрессия к среднему); нужна контрольная группа",
    "Нельзя: провал слабейших отчасти случаен, и они подтянутся сами; нужна контрольная группа",
)
RTM_WRONG = (
    "Да: рост статистически значим, значит он вызван именно вмешательством, а не случайностью",
    "Да, если рост больше 10%: регрессия к среднему объясняет только совсем небольшие изменения показателя",
    "Нет, но лишь потому, что выборка мала; на большой выборке такой вывод был бы вполне корректным",
    "Да: регрессия к среднему бывает только у чисто случайных величин, а этот показатель вовсе не случаен",
)


@family(code="da.stats.regression_to_mean", specialization="data", area="stats", level=5, fmt="mcq",
        space_size=len(RTM_CONTEXTS) * 16 * 26 * len(RTM_CORRECT) * math.comb(len(RTM_WRONG), 3) * 24,
        median_time_s=120)
def regression_to_mean(rng: random.Random) -> Generated:
    who, metric, action = rng.choice(RTM_CONTEXTS)
    share, growth = rng.randint(5, 20), rng.randint(5, 30)
    text = (f"Из всех {who} отобрали {share}% самых слабых {metric} за прошлый квартал и {action}. В следующем "
            f"квартале показатель у этой группы вырос в среднем на {growth}%. Можно ли приписать рост вмешательству?")
    return mcq(rng, text, rng.choice(RTM_CORRECT), rng.sample(RTM_WRONG, 3))
