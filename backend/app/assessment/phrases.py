GRADE_TITLES = {"junior": "Junior", "middle": "Middle", "senior": "Senior"}


def ru_plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    return {1: one, 2: few, 3: few, 4: few}.get(n % 10, many)


def result_phrase(target: str, decision: str, correct: int, total: int, correct_above: int) -> str:
    head = f"{GRADE_TITLES[target]} {'подтверждён' if decision == 'confirmed' else 'не подтверждён'}"
    phrase = f"{head} · решено {correct} из {total}"
    if correct_above:
        phrase += f", из них {correct_above} {ru_plural(correct_above, 'задание', 'задания', 'заданий')} уровня выше"
    return phrase


def skill_phrase(title: str, decision: str, correct: int, total: int) -> str:
    return f"Навык «{title}» {'подтверждён' if decision == 'confirmed' else 'не подтверждён'} · решено {correct} из {total}"


def ai_phrase(decision: str, m: dict) -> str:
    """«Работа с ИИ: подтверждено · верных вердиктов 11 из 12 · 7 мин» (процесс 2.5, без рода)."""
    head = "подтверждено" if decision == "confirmed" else "не подтверждено"
    tail = f"{m['minutes']} мин" if m["in_time"] else "время вышло"
    return f"Работа с ИИ: {head} · верных ответов {m['correct']} из {m['n']} · {tail}"
