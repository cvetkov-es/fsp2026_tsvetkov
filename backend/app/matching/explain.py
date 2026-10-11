"""Объяснение места кандидата: факты и минусы, без ложной точности (процесс v4, 4.3)."""
from bisect import bisect_left
from dataclasses import dataclass, replace
from datetime import datetime

from app.assessment.engine.levels import Grade, grade_rank
from app.assessment.phrases import GRADE_TITLES, ru_plural
from app.common.clock import MSK
from app.config.params import PARAMS
from app.matching.scoring import NeedFacts, Ranked, evaluate_candidate, level, sort_key

NO_FSP = "Истории ФСП нет, навыки оценены по тесту"
FORMAT_TITLES = {"office": "офис", "hybrid": "гибрид", "remote": "удалёнка"}
# Бейдж «Готовность: …» — женский род; «соответствие» остаётся в среднем (level)
READINESS_LEVEL = {"высокое": "высокая", "среднее": "средняя", "низкое": "низкая"}


@dataclass(frozen=True)
class Explanation:
    lines: tuple[str, str, str]
    missing: tuple[str, ...]
    counterfactual: str | None
    readiness_level: str
    readiness_tooltip: str
    fit_level: str


def interview_suffix(c) -> str:
    """Прибавка от собеседований называется открыто (процесс 5); оценки «ниже» наружу не показываются."""
    if c.interview_badge:
        return f" · подтверждено на собеседованиях ({c.interview_positive}) → выше в выдаче"
    return " · положительные оценки собеседований → выше в выдаче" if c.m > 1 else ""


def _grade_line(r: Ranked, need: NeedFacts, percentile: int | None) -> str:
    c = r.c
    if c.grade_status == "confirmed":
        g = GRADE_TITLES[c.confirmed_grade]
        if r.block == 2 or (r.block == 4 and c.confirmed_grade not in need.grades):
            closest = min(need.grades, key=lambda x: abs(grade_rank(Grade(x)) - grade_rank(Grade(c.confirmed_grade))))
            side = "выше" if grade_rank(Grade(c.confirmed_grade)) > grade_rank(Grade(closest)) else "ниже"
            line = f"{g} подтверждён тестом · соседний грейд, на ступень {side} целевого"
        else:
            line = f"{g} подтверждён тестом"
            if percentile is not None:
                line += f" · сильнее {percentile}% категории"
    else:
        line = f"{GRADE_TITLES[c.claimed_grade]} заявлен, тест не подтвердил"
    if c.express:
        line += " · по экспресс-тесту, позиция уточнится"
    return line + interview_suffix(c)


def _stack_line(r: Ranked, need: NeedFacts) -> str:
    st = r.stack
    if not st.known:
        confirmed = sorted(t for t, s in r.c.stack.items() if s == "confirmed")
        return "Стек не указан" + ("; тестом подтверждено: " + ", ".join(confirmed[:6]) if confirmed else "")
    if not need.must:
        return "Стек: " + ", ".join(f"{t} ✓" if s == "confirmed" else t for t, s in sorted(r.c.stack.items())[:6])
    parts = [f"{t} ✓" for t in st.confirmed] + [f"{t} (заявлено)" for t in st.declared]
    line = "Стек: " + (", ".join(parts) if parts else "обязательного стека нет")
    if st.missing:
        line += "; нет: " + ", ".join(st.missing)
    return line


def _salary_phrase(gap: float) -> str:
    """Порог кандидата скрыт: наружу — только уровень расхождения, без процента (процесс 2.2, 6.4)."""
    if gap <= 0:
        return "вилка покрывает ожидания"
    return "вилка немного ниже ожиданий" if gap <= PARAMS.hard_salary_gap else "вилка заметно ниже ожиданий"


def _readiness(r: Ranked) -> tuple[str, str]:
    a = r.accept
    parts = []
    if a.salary_gap is None:
        parts.append("ожидания по зарплате не указаны")
    else:
        parts.append(_salary_phrase(a.salary_gap))
    if a.window_open:
        parts.append(f"окно поиска открыто до {r.c.open_until.astimezone(MSK):%d.%m}")
    else:
        parts.append("окно поиска истекло")
    days = PARAMS.activity_days
    parts.append(f"есть активность за {days} дней" if a.active else f"нет активности дольше {days} дней")
    if a.signal:
        parts.append("кандидат отметил интерес к вашей компании")
    return READINESS_LEVEL[level(a.value)], " · ".join(parts)


def _missing(r: Ranked, need: NeedFacts) -> tuple[str, ...]:
    out = []
    if r.stack.missing:
        out.append("нет: " + ", ".join(r.stack.missing))
    out += [f"{t}: заявлено, не подтверждено" for t in r.stack.declared]
    if r.accept.salary_gap is not None and r.accept.salary_gap > 0:
        out.append(_salary_phrase(r.accept.salary_gap) + " кандидата")
    if r.accept.format is not None and r.accept.format < 1:
        out.append(f"формат: кандидат готов к варианту «{', '.join(FORMAT_TITLES[f] for f in r.c.formats)}», "
                   f"вы ищете «{', '.join(FORMAT_TITLES[f] for f in need.formats)}»")
    if "format" in r.conflicts:
        out.append("формат работы несовместим")
    return tuple(out)


def explain(r: Ranked, need: NeedFacts, percentile: int | None, fsp_summary: str | None) -> Explanation:
    fsp_line = fsp_summary if (fsp_summary and r.c.fsp_visible) else NO_FSP
    rl, tip = _readiness(r)
    return Explanation((_grade_line(r, need, percentile), _stack_line(r, need), fsp_line),
                       _missing(r, need), None, rl, tip, level(r.fit))


def counterfactual(ranked: list[Ranked], idx: int, need: NeedFacts, now: datetime,
                   keys: list | None = None) -> str | None:
    """Какой must, будучи подтверждённым, поднимет кандидата сильнее всего.

    keys — ключи сортировки ranked (список уже отсортирован): позиция ищется бинарным поиском,
    поэтому подборка целиком считается за O(N·k·log N), а не O(N²·k).
    """
    me = ranked[idx]
    candidates = list(me.stack.missing) + list(me.stack.declared)
    if not candidates:
        return None
    keys = keys if keys is not None else [sort_key(o) for o in ranked]
    best: tuple[int, str] | None = None
    for tech in candidates:
        improved = evaluate_candidate(replace(me.c, stack={**me.c.stack, tech: "confirmed"}), need, now)
        if improved is None:
            continue
        k = sort_key(improved)
        new_pos = bisect_left(keys, k) - (1 if keys[idx] < k else 0)  # сколько других окажется выше
        gain = idx - new_pos
        if gain > 0 and (best is None or gain > best[0]):
            best = (gain, tech)
    if best is None:
        return None
    gain, tech = best
    return f"Если подтвердить {tech}, кандидат поднимется на {gain} {ru_plural(gain, 'позицию', 'позиции', 'позиций')}"


def counterfactuals(ranked: list[Ranked], need: NeedFacts, now: datetime) -> list[str | None]:
    keys = [sort_key(o) for o in ranked]
    return [counterfactual(ranked, i, need, now, keys) for i in range(len(ranked))]
