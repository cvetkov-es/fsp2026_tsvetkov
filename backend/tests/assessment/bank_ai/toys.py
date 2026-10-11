"""Учебные семейства вердиктов по одному на область: тесты формата, сервиса и лаборатории."""
import random

from app.assessment.bank.base import Generated, Table
from app.assessment.bank.verdicts import (
    Mutation,
    ai_family,
    clarify_verdict,
    python_verdict,
    sql_verdict,
)


def toy_python(rng: random.Random, flawed: bool) -> Generated:
    t = rng.randint(1, 10**4)
    return python_verdict(
        rng, flawed, text=f"solve(xs) — сумма элементов больше {t}; пустой список — 0.",
        reference=f"def solve(xs):\n    return sum(x for x in xs if x > {t})",
        mutations=(Mutation(2, f"    return sum(x for x in xs if x >= {t})", cls="boundary"),
                   Mutation(2, f"    return sum(x for x in xs[1:] if x > {t})", cls="dup")),
        cases={"empty": [], "dup": [t + 1, t + 1], "boundary": [t, t + 1]},
        clarify=("Что вернуть для пустого списка?", f"Включать ли {t}?", "Можно ли менять список?", "Какой тип вернуть?"))


def toy_sql(rng: random.Random, flawed: bool) -> Generated:
    n = rng.randint(1, 10**4)
    return sql_verdict(
        rng, flawed, text=f"Сколько строк t со значением не меньше {n}?",
        tables=(Table("t", ("v",), ((n + 1,), (n - 1,))),),
        reference=f"SELECT COUNT(*)\nFROM t\nWHERE v >= {n}",
        mutations=(Mutation(3, f"WHERE v > {n}", witness=(Table("t", ("v",), ((n,),)),)),),
        clarify=(f"Считать ли {n}?", "Вернуть число или строки?", "Нужны ли сами строки?", "Как считать NULL?"))


def toy_clarify(rng: random.Random, flawed: bool) -> Generated:
    k = rng.randint(1, 10**4)
    return clarify_verdict(
        rng, text=f"solve(xs) — {k} лучших значений.", code=f"def solve(xs):\n    return sorted(xs)[-{k}:]",
        language="python", right="Как быть с повторами?", settled=("Порядок?", "Если значений меньше?", "Тип?"),
        input_classes=("empty", "dup"))


TOYS = {"python": toy_python, "sql": toy_sql, "clarify": toy_clarify}


def register_toys(copies: dict[str, int]) -> list[str]:
    """Зарегистрировать учебные семейства (после clear_registry): {"python": 7, …} → коды."""
    codes = []
    for area, n in copies.items():
        for i in range(n):
            code = f"toy.ai.{area}.{i}"
            ai_family(code=code, area=area, space_size=10**6, median_time_s=30)(TOYS[area])
            codes.append(code)
    return codes
