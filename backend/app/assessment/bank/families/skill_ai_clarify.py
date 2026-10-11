"""«Работа с ИИ»: неоднозначные требования (область clarify). Верный ответ — «нужно уточнить» и вопрос,
без ответа на который решение нельзя признать ни верным, ни неверным. Каталог — план 07a3, задача 7.

Решение реализует одно из толкований и выглядит правдоподобно. Код этих семейств не исполняется.
"""
import random
from datetime import date, timedelta

from app.assessment.bank.base import Generated, Table
from app.assessment.bank.verdicts import ai_family, clarify_verdict

SCORES = ("баллов", "оценок", "результатов", "ставок", "очков", "рейтингов", "откликов", "голосов",
          "показов", "лайков")


@ai_family(code="ai.clarify.top_k_duplicates", area="clarify", space_size=10**5, median_time_s=45)
def top_k_duplicates(rng: random.Random, flawed: bool) -> Generated:
    k, low, noun = rng.randint(2, 9), rng.randint(0, 50), rng.choice(SCORES)
    var = rng.choice(("s", "x", "v"))
    return clarify_verdict(
        rng,
        text=(f"Функция solve(xs) возвращает {k} наибольших {noun} из списка xs по убыванию. "
              f"Значения меньше {low} не учитываются. Если подходящих значений меньше {k} — вернуть все."),
        code=(f"def solve(xs):\n"
              f"    kept = [{var} for {var} in xs if {var} >= {low}]\n"
              f"    return sorted(kept, reverse=True)[:{k}]"),
        language="python",
        right="Считать ли повторяющиеся значения отдельно (например, 9 и 9 — два места)?",
        settled=("В каком порядке вернуть значения?", f"Что вернуть, если подходящих значений меньше {k}?",
                 f"Учитывать ли значения меньше {low}?"),
        input_classes=("empty", "dup", "negative", "boundary"))


# --- ai.clarify.round_half ------------------------------------------------------------------
PRICE_ARGS = ("price", "amount", "cost", "value")


@ai_family(code="ai.clarify.round_half", area="clarify", space_size=99_000 * len(PRICE_ARGS) * 24, median_time_s=40)
def round_half(rng: random.Random, flawed: bool) -> Generated:
    cap, arg = rng.randint(1000, 99_999), rng.choice(PRICE_ARGS)
    return clarify_verdict(
        rng,
        text=(f"Функция solve({arg}) возвращает цену в целых рублях (целое число). Цена положительная и не больше "
              f"{cap} ₽, может быть с копейками; копейки отбрасывать нельзя — нужно округление."),
        code=f"def solve({arg}):\n    return round({arg})",
        language="python",
        right="Как округлять ровно половину рубля (например, 2,50 ₽)?",
        settled=("Может ли цена быть отрицательной?", "Вернуть число или строку?", "Можно ли просто отбросить копейки?"),
        input_classes=("empty", "negative", "boundary"))


# --- ai.clarify.active_last_month -----------------------------------------------------------
USERS = ("id", "blocked", "last_seen")


@ai_family(code="ai.clarify.active_last_month", area="clarify", space_size=365 * 10**4, median_time_s=50)
def active_last_month(rng: random.Random, flawed: bool) -> Generated:
    d = date(2025, 1, 1) + timedelta(days=rng.randrange(365))
    sample = tuple((i, rng.choice((0, 0, 1)), (d - timedelta(days=rng.randint(0, 50))).isoformat())
                   for i in range(1, rng.randint(5, 9)))
    return clarify_verdict(
        rng,
        text=(f"Сколько пользователей были активны за последний месяц на дату {d.isoformat()}? Заблокированных "
              "(blocked = 1) не считать; каждого пользователя — один раз."),
        # граница — готовой датой: запрос переносим между SQLite и PostgreSQL, открыт только вопрос о «месяце»
        code=f"SELECT COUNT(*)\nFROM users\nWHERE blocked = 0 AND last_seen >= '{(d - timedelta(days=30)).isoformat()}'",
        language="sql",
        right="Последний месяц — это 30 дней или календарный месяц?",
        settled=("На какую дату считать?", "Считать ли заблокированных?", "Считать пользователя один раз или по входам?"),
        tables=(Table("users", USERS, sample),))


# --- ai.clarify.revenue_month --------------------------------------------------------------
ORDER_COLS = ("id", "created_at", "paid_at", "amount")
MONTHS = tuple(f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1, 13))


@ai_family(code="ai.clarify.revenue_month", area="clarify", space_size=len(MONTHS) * 10**5, median_time_s=50)
def revenue_month(rng: random.Random, flawed: bool) -> Generated:
    month = rng.choice(MONTHS)
    first = date.fromisoformat(f"{month}-01")
    rows = []
    for i in range(1, rng.randint(6, 9)):
        created = first + timedelta(days=rng.randint(0, 27))
        lag = rng.randint(3, 10) if i <= 2 else rng.randint(0, 6)  # в примере есть оплаты уже в следующем месяце
        paid = created + timedelta(days=lag) if i != 1 else first + timedelta(days=27 + lag)
        rows.append((i, created.isoformat(), paid.isoformat(), round(rng.uniform(100, 9000), 2)))
    return clarify_verdict(
        rng,
        text=f"Какова выручка за {month} в рублях? Все заказы в таблице оплачены; сумму округлить до рубля.",
        code=f"SELECT ROUND(SUM(amount))\nFROM orders\nWHERE substr(created_at, 1, 7) = '{month}'",
        language="sql",
        right="Относить заказ к месяцу по дате создания или по дате оплаты?",
        settled=("За какой месяц считать?", "Учитывать ли неоплаченные заказы?", "Округлять ли сумму?"),
        tables=(Table("orders", ORDER_COLS, tuple(rows)),))


# --- ai.clarify.same_email ------------------------------------------------------------------
DOMAINS = ("mail.ru", "corp.ru", "yandex.ru", "example.com", "fsp.org", "team.dev")


@ai_family(code="ai.clarify.same_email", area="clarify", space_size=491 * len(DOMAINS) * 24 * 2, median_time_s=40)
def same_email(rng: random.Random, flawed: bool) -> Generated:
    n, domain = rng.randint(10, 500), rng.choice(DOMAINS)
    arg = rng.choice(("emails", "addrs"))
    return clarify_verdict(
        rng,
        text=(f"Функция solve({arg}) проверяет, есть ли повторы среди первых {n} адресов почты (домен — {domain}), "
              "и возвращает True или False. Адреса уже без пробелов по краям. Для пустого списка — False."),
        code=f"def solve({arg}):\n    {arg} = {arg}[:{n}]\n    return len(set({arg})) < len({arg})",
        language="python",
        right="Считать ли адреса с разным регистром (Anna@x.ru и anna@x.ru) одним адресом?",
        settled=("Что вернуть — True/False или список повторов?", "Что вернуть для пустого списка?",
                 "Убирать ли пробелы по краям?"),
        input_classes=("empty", "dup", "unicode"))


# --- ai.clarify.age_leap_day ----------------------------------------------------------------
@ai_family(code="ai.clarify.age_leap_day", area="clarify", space_size=3 * 365 * 8 * 24, median_time_s=55)
def age_leap_day(rng: random.Random, flawed: bool) -> Generated:
    today = date(2025, 1, 1) + timedelta(days=rng.randrange(3 * 365))
    min_age = rng.randint(14, 21)
    t = (today.year, today.month, today.day)
    return clarify_verdict(
        rng,
        text=(f"Функция solve(birth) возвращает число полных лет на {today:%d.%m.%Y}; даты — кортежи (год, месяц, день). "
              f"Дата рождения не позже этой даты. Если полных лет меньше {min_age} — вернуть 0."),
        code=(f"def solve(birth):\n"
              f"    today = {t}\n"
              f"    y = today[0] - birth[0] - ((today[1], today[2]) < (birth[1], birth[2]))\n"
              f"    return y if y >= {min_age} else 0"),
        language="python",
        right="Когда исполняется год у родившихся 29 февраля в невисокосный год — 28 февраля или 1 марта?",
        settled=("На какую дату считать возраст?", "Считать полные годы или округлять?",
                 f"Что вернуть, если лет меньше {min_age}?"),
        input_classes=("boundary", "empty"))
