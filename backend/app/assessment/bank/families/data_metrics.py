"""Семейства Data/Analytics · метрики и продуктовая аналитика.

Определение метрики всегда однозначно (формула или явное описание в тексте); параметры подобраны так,
чтобы ответ не лежал у границы округления.
"""
import math
import random

from app.assessment.bank.base import Generated, Prompt, Table, family, mcq

PRODUCTS = ("Фитнес-трекер", "Онлайн-курс", "Доставка цветов", "Онлайн-кинотеатр", "Кофемашина", "Тариф Про")
APPS = ("Заметки+", "Бюджет", "Читалка", "Трекер привычек", "Медитации", "Погода")


def _far(x: float, digits: int) -> bool:
    return abs((x * 10**digits) % 1 - 0.5) > 0.01


def _pct(text: str, value: float, radicals: tuple, tables: tuple = ()) -> Generated:
    return Generated("number", Prompt(text=text, tables=tables, answer_hint="Процент с одним знаком после запятой, "
                                                                           "например 12.5"),
                     round(value, 1), radicals)


# --- da.metrics.conversion_rate -------------------------------------------------------------
@family(code="da.metrics.conversion_rate", specialization="data", area="metrics", level=1, fmt="calc",
        space_size=len(PRODUCTS) * 49_501 * 100, median_time_s=35)
def conversion_rate(rng: random.Random) -> Generated:
    while True:
        visitors = rng.randint(500, 50_000)
        buys = rng.randint(max(1, visitors // 200), visitors // 8)
        value = buys / visitors * 100
        if _far(value, 1):
            break
    text = (f"Лендинг «{rng.choice(PRODUCTS)}» за неделю. Посетителей: {visitors}, покупок: {buys}. Какова "
            "конверсия посетителя в покупку, %?")
    return _pct(text, value, ("conversion",))


# --- da.metrics.dau_mau -------------------------------------------------------------------------
@family(code="da.metrics.dau_mau", specialization="data", area="metrics", level=1, fmt="calc",
        space_size=len(APPS) * 10**6, median_time_s=35)
def dau_mau(rng: random.Random) -> Generated:
    while True:
        mau = rng.randint(5_000, 500_000)
        dau = rng.randint(mau // 20, mau // 2)
        value = dau / mau * 100
        if _far(value, 1):
            break
    text = (f"Приложение «{rng.choice(APPS)}»: среднее DAU — {dau}, MAU за тот же месяц — {mau}. Какова stickiness "
            "(DAU / MAU), %?")
    return _pct(text, value, ("stickiness",))


# --- da.metrics.funnel_step -----------------------------------------------------------------------
FUNNELS = (
    ("Зашли на сайт", "Открыли карточку товара", "Добавили в корзину", "Начали оформление", "Оплатили"),
    ("Открыли лендинг", "Нажали кнопку регистрации", "Заполнили форму", "Подтвердили почту", "Создали проект"),
    ("Установили приложение", "Прошли онбординг", "Создали первую задачу", "Пригласили коллегу",
     "Оформили подписку"),
)


@family(code="da.metrics.funnel_step", specialization="data", area="metrics", level=2, fmt="calc",
        space_size=len(FUNNELS) * 10**8, median_time_s=50)
def funnel_step(rng: random.Random) -> Generated:
    names = rng.choice(FUNNELS)[:rng.randint(4, 5)]
    while True:
        counts = [rng.randint(5_000, 100_000)]
        for _ in names[1:]:
            counts.append(int(counts[-1] * rng.uniform(0.15, 0.8)))
        i = rng.randint(1, len(names) - 2) if rng.random() < 0.8 else 0
        value = counts[i + 1] / counts[i] * 100  # конверсия шага — от предыдущего шага
        if _far(value, 1) and round(counts[i + 1] / counts[0] * 100, 1) != round(value, 1) or i == 0 and _far(value, 1):
            break
    table = Table("Воронка", ("шаг", "пользователей"), tuple(zip(names, counts, strict=False)))
    text = f"Воронка — в таблице. Какова конверсия перехода с шага «{names[i]}» на шаг «{names[i + 1]}», %?"
    return _pct(text, value, ("funnel_step_conversion",), (table,))


# --- da.metrics.arppu ----------------------------------------------------------------------------------
@family(code="da.metrics.arppu", specialization="data", area="metrics", level=2, fmt="calc",
        space_size=len(APPS) * 10**8, median_time_s=50)
def arppu(rng: random.Random) -> Generated:
    while True:
        users = rng.randint(2_000, 200_000)
        paying = rng.randint(max(10, users // 100), users // 5)
        revenue = paying * rng.randint(150, 3000) + rng.randint(1, 999)
        value = revenue / paying
        if _far(value, 2) and round(revenue / users, 2) != round(value, 2):
            break
    text = (f"Приложение «{rng.choice(APPS)}». Выручка за месяц — {revenue} ₽, активных пользователей — {users}, "
            f"из них платящих — {paying}. Каков ARPPU за месяц, ₽?")
    return Generated("number", Prompt(text=text, answer_hint="Число с двумя знаками после запятой"), round(value, 2),
                     ("arppu",))


# --- da.metrics.day_n_retention -------------------------------------------------------------------------------
RETENTION_DAYS = (1, 7, 14, 30)


@family(code="da.metrics.day_n_retention", specialization="data", area="metrics", level=2, fmt="calc",
        space_size=10**9, median_time_s=50)
def day_n_retention(rng: random.Random) -> Generated:
    month = rng.randint(1, 12)
    cohorts = [f"2026-{month:02d}-{d:02d}" for d in sorted(rng.sample(range(1, 29), 3))]
    while True:
        rows = []
        for c in cohorts:
            size = rng.randint(300, 5000)
            share, active = rng.uniform(0.3, 0.6), []
            for _ in RETENTION_DAYS:
                active.append(int(size * share))
                share *= rng.uniform(0.4, 0.85)
            rows.append((c, size, *active))
        cohort_i, day_i = rng.randrange(3), rng.randrange(len(RETENTION_DAYS))
        value = rows[cohort_i][2 + day_i] / rows[cohort_i][1] * 100
        if _far(value, 1):
            break
    table = Table("Когорты", ("когорта", "размер", *(f"день {d}" for d in RETENTION_DAYS)), tuple(rows))
    text = (f"Таблица — размер когорт и число пользователей, активных в день N после установки. Каково удержание "
            f"когорты {cohorts[cohort_i]} на день {RETENTION_DAYS[day_i]}, %?")
    return _pct(text, value, ("classic_retention",), (table,))


# --- da.metrics.simple_ltv ---------------------------------------------------------------------------------------
@family(code="da.metrics.simple_ltv", specialization="data", area="metrics", level=3, fmt="calc",
        space_size=len(PRODUCTS) * 1951 * 61 * 191, median_time_s=70)
def simple_ltv(rng: random.Random) -> Generated:
    while True:
        arpu, margin, churn = rng.randint(50, 2000), rng.randint(20, 80), rng.randint(10, 200) / 10
        ltv = arpu * margin / 100 / (churn / 100)
        if _far(ltv, 0):
            break
    text = (f"Подписка «{rng.choice(PRODUCTS)}»: ARPU — {arpu} ₽ в месяц, маржинальность — {margin}%, месячный отток — "
            f"{churn:g}%. Оцените LTV клиента в простой модели с постоянным месячным оттоком (средняя «жизнь» "
            "клиента — 1 / отток месяцев).")
    return Generated("number", Prompt(text=text, answer_hint="Целое число рублей"), round(ltv), ("simple_ltv",))


# --- da.metrics.rolling_retention --------------------------------------------------------------------------------
@family(code="da.metrics.rolling_retention", specialization="data", area="metrics", level=3, fmt="calc",
        space_size=10**9, median_time_s=80)
def rolling_retention(rng: random.Random) -> Generated:
    n = rng.choice((3, 7, 14))
    while True:
        users = []
        for _ in range(rng.randint(6, 10)):
            days = sorted(rng.sample(range(1, 2 * n + 3), rng.randint(0, 4)))
            users.append(days)
        rolling = sum(any(d >= n for d in ds) for ds in users) / len(users) * 100
        classic = sum(n in ds for ds in users) / len(users) * 100
        if _far(rolling, 1) and round(classic, 1) != round(rolling, 1) and 0 < rolling < 100:
            break
    rows = tuple((f"u{i + 1}", ", ".join(map(str, ds)) or "—") for i, ds in enumerate(users))  # «—» — не заходил
    table = Table("Когорта", ("пользователь", "дни активности после установки"), rows)
    text = (f"Таблица — дни, в которые пользователи когорты заходили в приложение (день установки — 0). Rolling "
            f"retention дня {n} — доля когорты, вернувшейся в день {n} или позже. Чему он равен, %?")
    return _pct(text, rolling, ("rolling_retention",), (table,))


# --- da.metrics.unique_users_definition ---------------------------------------------------------------------------
PERIODS = (("неделю", "WAU"), ("месяц", "MAU"), ("квартал", "QAU"))
UU_TABLES = ("events", "sessions", "page_views", "actions")
UU_DATES = ("event_date", "created_at", "day")
UU_SEGMENTS = ("из России", "из Казахстана", "мобильного приложения", "веб-версии", "платного тарифа",
               "бесплатного тарифа")
UU_CORRECT = ("COUNT(DISTINCT user_id) по всем строкам за {period} сразу",
              "COUNT(DISTINCT user_id) одним запросом сразу за {period}")
UU_WRONG = (
    "Сумма дневных значений COUNT(DISTINCT user_id) за все дни периода",
    "Среднее дневное число уникальных пользователей, умноженное на число дней",
    "COUNT(*) всех строк таблицы {table} за этот период",
    "Наибольшее из дневных значений COUNT(DISTINCT user_id) за период",
)


@family(code="da.metrics.unique_users_definition", specialization="data", area="metrics", level=3, fmt="mcq",
        space_size=len(PERIODS) * len(UU_TABLES) * len(UU_DATES) * len(APPS) * len(UU_SEGMENTS) * len(UU_CORRECT)
        * 4 * 24,
        median_time_s=60)
def unique_users_definition(rng: random.Random) -> Generated:
    period, metric = rng.choice(PERIODS)
    table, date = rng.choice(UU_TABLES), rng.choice(UU_DATES)
    text = (f"В приложении «{rng.choice(APPS)}» нужно посчитать {metric} — число уникальных пользователей "
            f"{rng.choice(UU_SEGMENTS)} за {period} — "
            f"по таблице {table}(user_id, {date}, …). Как сделать это правильно?")
    return mcq(rng, text, rng.choice(UU_CORRECT).format(period=period),
               [w.format(table=table) for w in rng.sample(UU_WRONG, 3)])


# --- da.metrics.cac_payback -------------------------------------------------------------------------------------------
@family(code="da.metrics.cac_payback", specialization="data", area="metrics", level=4, fmt="calc",
        space_size=len(PRODUCTS) * 9_801 * 1_951 * 61, median_time_s=90)
def cac_payback(rng: random.Random) -> Generated:
    while True:
        cac, arpu, margin = rng.randint(200, 10_000), rng.randint(50, 2000), rng.randint(20, 80)
        months = cac / (arpu * margin / 100)
        if 0.5 < months < 60 and _far(months, 1) and round(cac / arpu, 1) != round(months, 1):
            break
    text = (f"Продукт «{rng.choice(PRODUCTS)}»: CAC — {cac} ₽, ARPU — {arpu} ₽ в месяц, маржинальность — {margin}%. "
            "За сколько месяцев окупится привлечение клиента? Отток и дисконтирование не учитывайте.")
    return Generated("number", Prompt(text=text, answer_hint="Число месяцев с одним знаком после запятой"),
                     round(months, 1), ("cac_payback",))


# --- da.metrics.guardrail -----------------------------------------------------------------------------------------------
# (что тестируем — уникальная фраза текста, guardrail, пул дистракторов, целевая метрика — она же в пуле)
GUARDRAIL_ROWS = (
    ("агрессивные push-уведомления", "Доля отписок от push и удалений приложения",
     ("DAU приложения в тестовой группе за период", "Число отправленных уведомлений на пользователя",
      "Средняя длина текста уведомления в символах", "Доля открытых уведомлений от всех отправленных"),
     "DAU приложения в тестовой группе за период"),
    ("скидку 20% на первый заказ", "Валовая маржа на заказ после скидки",
     ("Конверсия посетителя в первый заказ", "Число показов баннера со скидкой за день",
      "Средний размер скидки на один заказ в рублях", "Число применённых промокодов за неделю"),
     "Конверсия посетителя в первый заказ"),
    ("бесконечную ленту рекомендаций", "Число жалоб и скрытий контента на пользователя",
     ("Среднее время в приложении на одного пользователя", "Число показанных карточек ленты за одну сессию",
      "Средняя длина ленты за одну сессию в экранах", "Число прокруток ленты на одного пользователя"),
     "Среднее время в приложении на одного пользователя"),
    ("оформление заказа без подтверждения адреса", "Доля доставок, сорванных из-за ошибки в адресе",
     ("Среднее время оформления одного заказа в секундах", "Число кликов от корзины до оплаты заказа",
      "Конверсия из корзины в оплаченный заказ за неделю", "Число полей в форме оформления заказа"),
     "Среднее время оформления одного заказа в секундах"),
)
GUARDRAIL_PRODUCTS = ("маркетплейса", "сервиса доставки еды", "соцсети", "приложения такси", "онлайн-кинотеатра",
                      "банковского приложения")
GUARDRAIL_AUDIENCES = ("всех пользователей", "новых пользователей", "пользователей Android", "пользователей iOS")
# как цель эксперимента названа в тексте — для каждой строки GUARDRAIL_ROWS (по индексу)
GUARDRAIL_GOALS = ("роста DAU", "роста конверсии в первый заказ", "роста времени в приложении",
                   "сокращения времени оформления заказа")


@family(code="da.metrics.guardrail", specialization="data", area="metrics", level=4, fmt="mcq",
        space_size=len(GUARDRAIL_ROWS) * len(GUARDRAIL_PRODUCTS) * len(GUARDRAIL_AUDIENCES) * 5 * 13 * 4 * 24,
        median_time_s=80)
def guardrail(rng: random.Random) -> Generated:
    i = rng.randrange(len(GUARDRAIL_ROWS))
    what, correct, pool, target, goal = (*GUARDRAIL_ROWS[i], GUARDRAIL_GOALS[i])
    weeks, lift = rng.randint(2, 6), rng.randint(3, 15)
    # целевая метрика — частая ошибка, поэтому она почти всегда среди вариантов
    others = [p for p in pool if p != target]
    wrong = [target, *rng.sample(others, 2)] if rng.random() < 0.8 else rng.sample(others, 3)
    text = (f"Команда {rng.choice(GUARDRAIL_PRODUCTS)} тестирует {what} для {rng.choice(GUARDRAIL_AUDIENCES)} в "
            f"течение {weeks} нед. и ждёт {goal} на {lift}% — это целевая метрика. Какую guardrail-метрику важнее "
            "всего добавить, чтобы не навредить продукту?")
    return mcq(rng, text, correct, wrong)


# --- da.metrics.north_star --------------------------------------------------------------------------------------------
NORTH_STAR_ROWS = (
    ("музыкальный стриминг по подписке", "Часы прослушивания платящими подписчиками за неделю",
     ("Общее число установок приложения на всех платформах", "Число треков в каталоге сервиса на конец каждого месяца",
      "Выручка от рекламы в бесплатном тарифе за неделю", "Число подписчиков официальных страниц сервиса в соцсетях")),
    ("маркетплейс товаров для дома", "Число успешно доставленных заказов в неделю",
     ("Число зарегистрированных продавцов на площадке", "Число просмотров карточек товаров за неделю",
      "Среднее время на сайте за одно посещение", "Число товарных позиций в каталоге площадки")),
    ("сервис совместного редактирования документов для команд",
     "Число команд, совместно правящих документы каждую неделю",
     ("Число созданных документов, включая пустые, за неделю", "Число новых регистраций в сервисе за календарную неделю",
      "Посещаемость лендинга сервиса за неделю по всем каналам", "Число скачанных шаблонов документов за неделю")),
    ("приложение для изучения языков", "Число учеников, занимающихся три дня в неделю и чаще",
     ("Число скачиваний приложения из магазинов за неделю", "Число отправленных ученикам push-уведомлений за неделю",
      "Число слов во встроенном словаре приложения", "Средняя оценка приложения в магазине приложений за месяц")),
    ("сервис заказа такси", "Число завершённых поездок в неделю",
     ("Число водителей на линии в часы пик за неделю", "Число открытий приложения пассажирами за неделю",
      "Средняя оценка интерфейса приложения в опросах", "Число установок приложения пассажирами за неделю")),
)
NS_STAGES = ("на стадии роста", "после запуска в новом регионе", "перед раундом инвестиций")
NS_REGIONS = ("в России", "в Казахстане", "в Узбекистане", "в Беларуси")
NS_NAMES = ("Альфа", "Вектор", "Орбита", "Маяк", "Кедр", "Полюс", "Бриз", "Янтарь", "Сокол", "Гавань",
            "Ладья", "Пчёлка")


@family(code="da.metrics.north_star", specialization="data", area="metrics", level=4, fmt="mcq",
        space_size=len(NORTH_STAR_ROWS) * len(NS_STAGES) * len(NS_REGIONS) * len(NS_NAMES) * 4 * 24,
        median_time_s=80)
def north_star(rng: random.Random) -> Generated:
    what, correct, pool = rng.choice(NORTH_STAR_ROWS)
    text = (f"Компания «{rng.choice(NS_NAMES)}» — {what} {rng.choice(NS_REGIONS)}, {rng.choice(NS_STAGES)}. Какая "
            "метрика лучше всего подходит на роль North Star — отражает ценность, которую получают пользователи, и "
            "ведёт к выручке?")
    return mcq(rng, text, correct, rng.sample(pool, 3))


# --- da.metrics.mix_shift ----------------------------------------------------------------------------------------------
MIX_SEGMENTS = (("органика", "реклама"), ("мобильные", "десктоп"), ("новые", "вернувшиеся"), ("Москва", "регионы"))
MIX_OPTIONS = {
    "mix": "Конверсия внутри сегментов не изменилась: общая упала из-за роста доли трафика с низкой конверсией",
    "both": "Конверсия упала в обоих сегментах: ухудшение реальное, а не из-за состава трафика",
    "one": "Конверсия упала только в сегменте «{seg}», в другом она стабильна, состав трафика прежний",
}


def _mix_rows(rng: random.Random, kind: str, segs: tuple[str, str]) -> list[tuple]:
    """(сегмент, период, посетители, покупки); у «высокого» сегмента конверсия выше."""
    hi, lo = segs
    r = {hi: rng.uniform(0.06, 0.12), lo: rng.uniform(0.01, 0.03)}
    total_prev, total_curr = rng.randint(20_000, 80_000), rng.randint(20_000, 80_000)
    share_prev = rng.uniform(0.5, 0.7)  # доля «высокого» сегмента
    share_curr = share_prev - rng.uniform(0.2, 0.3) if kind == "mix" else share_prev + rng.uniform(-0.01, 0.01)
    drop = {hi: 0.0, lo: 0.0}
    if kind == "both":
        drop = {hi: rng.uniform(0.2, 0.4), lo: rng.uniform(0.3, 0.5)}
    elif kind != "mix":
        drop[kind] = rng.uniform(0.3, 0.5)
    rows = []
    for per, total, share, factor in (("прошлый", total_prev, share_prev, {hi: 1, lo: 1}),
                                      ("текущий", total_curr, share_curr, {s: 1 - drop[s] for s in segs})):
        for seg, sh in ((hi, share), (lo, 1 - share)):
            visitors = round(total * sh)
            rows.append((seg, per, visitors, round(visitors * r[seg] * factor[seg])))
    return rows


@family(code="da.metrics.mix_shift", specialization="data", area="metrics", level=5, fmt="calc",
        space_size=10**9, median_time_s=140)
def mix_shift(rng: random.Random) -> Generated:
    segs = rng.sample(rng.choice(MIX_SEGMENTS), 2)
    kind = rng.choice(("mix", "mix", "both", segs[0], segs[1]))
    while True:
        rows = _mix_rows(rng, kind, tuple(segs))
        rate = {(s, p): b / v for s, p, v, b in rows}
        stable = [s for s in segs if s != kind and kind != "both"]
        tot = {p: sum(b for _, pp, _, b in rows if pp == p) / sum(v for _, pp, v, _ in rows if pp == p)
               for p in ("прошлый", "текущий")}
        if (all(abs(rate[(s, "текущий")] - rate[(s, "прошлый")]) < 0.001 for s in stable)
                and all(rate[(s, "текущий")] - rate[(s, "прошлый")] < -0.005 for s in segs if s not in stable)
                and tot["текущий"] < tot["прошлый"]):
            break
    key_name = "mix" if kind == "mix" else "both" if kind == "both" else "one"
    key = MIX_OPTIONS[key_name].format(seg=kind)
    options = [MIX_OPTIONS["mix"], MIX_OPTIONS["both"], *(MIX_OPTIONS["one"].format(seg=s) for s in segs)]
    table = Table("Трафик и покупки", ("сегмент", "период", "посетители", "покупки"), tuple(rows))
    text = ("Общая конверсия в покупку за текущий период упала по сравнению с прошлым. Данные по двум сегментам — в "
            "таблице. Какое объяснение верно?")
    return mcq(rng, text, key, [o for o in options if o != key], tables=(table,), radicals=("mix_shift", 4))


# --- da.metrics.novelty_effect -------------------------------------------------------------------------------------------
NOVELTY_FEATURES = ("новый дизайн главной", "геймифицированный онбординг", "анимированные кнопки", "новая лента",
                    "тёмная тема по умолчанию", "переработанная корзина")
NOVELTY_CORRECT = (
    "Это эффект новизны: реакция на новое затухает; оценивать по устоявшимся неделям или продлить тест",
    "Похоже на эффект новизны: прирост первых недель завышен; решать по устойчивому уровню",
)
NOVELTY_WRONG = (
    "Прирост первой недели самый точный: тогда пользователи ещё не устали; раскатывать по этой оценке",
    "Падение прироста — признак SRM в группах: результаты эксперимента нужно полностью отбросить",
    "Эффект растёт со временем, поэтому тест надо остановить прямо сейчас и раскатить вариант B на всех",
    "Затухание означает, что вариант B вредит продукту, и его нужно немедленно откатить",
)


@family(code="da.metrics.novelty_effect", specialization="data", area="metrics", level=5, fmt="mcq",
        space_size=len(NOVELTY_FEATURES) * 10**6 * len(NOVELTY_CORRECT) * math.comb(len(NOVELTY_WRONG), 3) * 24,
        median_time_s=110)
def novelty_effect(rng: random.Random) -> Generated:
    weeks = rng.randint(5, 8)
    start = rng.uniform(8, 20)
    floor = rng.uniform(0.5, start / 3)
    lifts = [round(floor + (start - floor) * 0.55**w + rng.uniform(-0.3, 0.3), 1) for w in range(weeks)]
    lifts = sorted(lifts, reverse=True)
    table = Table("Прирост B к A по неделям", ("неделя", "прирост конверсии, %"),
                  tuple((w + 1, max(0.1, x)) for w, x in enumerate(lifts)))
    text = (f"Долгий A/B-тест: вариант B — {rng.choice(NOVELTY_FEATURES)}. Прирост конверсии B к A по неделям — в "
            "таблице. Как правильно интерпретировать результат?")
    return mcq(rng, text, rng.choice(NOVELTY_CORRECT), rng.sample(NOVELTY_WRONG, 3), tables=(table,))
