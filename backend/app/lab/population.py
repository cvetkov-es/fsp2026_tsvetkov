"""Синтетическая популяция со скрытой истиной (исследование 03, §3a).

Истина (θ, реальный стек, реальные ожидания) известна только лаборатории. Ранжирование видит то же, что
и в продукте: результат симулированного теста, заявленный и подтверждённый стек, ФСП, условия.
"""
import math
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.assessment.bank.areas import AREAS
from app.assessment.engine.levels import GRADE_ORDER, Grade, Thresholds
from app.assessment.engine.rules import AttemptConfig, Decision
from app.assessment.engine.simulate import simulate_attempt, synthetic_bank
from app.config.params import PARAMS
from app.matching.scoring import CandidateFacts, NeedFacts, fsp_f
from app.matching.stack_dict import SKILL_TECHS, SPEC_CORE, SPEC_POOL, expand

SPECS = ("backend", "frontend", "data")
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)  # фиксированное «сейчас»: прогон воспроизводим
MEDIAN_NET = {"junior": 100_000, "middle": 200_000, "senior": 330_000}
FORMATS = ("office", "hybrid", "remote")


def thresholds() -> Thresholds:
    return Thresholds.from_params(PARAMS)


def true_grade(theta: float, t: Thresholds) -> str | None:
    """Истинный грейд — старший, чей порог θ превышает; ниже Junior — None."""
    grade = None
    for g in GRADE_ORDER:
        if theta >= t.cut(g):
            grade = g.value
    return grade


@dataclass
class Person:
    ref: str
    spec: str
    theta: float
    claimed: str
    techs: frozenset[str]          # что человек реально знает
    declared: frozenset[str]       # что заявил (с преувеличениями и пропусками)
    skills: frozenset[str]         # пройденные навыки
    threshold_net: int | None
    formats: tuple[str, ...]
    city: str
    fsp_f: float
    farmer: bool                   # «фармер» онлайн-отборов: много участий, но по таблице 6.2 — одна строка на дисциплину
    open_window: bool
    active: bool
    facts: CandidateFacts | None = None
    decision: str | None = None
    extra: dict = field(default_factory=dict)


def _claimed(theta: float, t: Thresholds, rng: random.Random) -> str:
    """Самооценка: истинный грейд, но каждый пятый ошибается на ступень (чаще вверх)."""
    g = true_grade(theta, t) or "junior"
    i = [x.value for x in GRADE_ORDER].index(g)
    r = rng.random()
    if r < 0.14:
        i = min(2, i + 1)
    elif r < 0.20:
        i = max(0, i - 1)
    return GRADE_ORDER[i].value


def make_people(n: int, seed: int, spec: str | None = None) -> list[Person]:
    rng = random.Random(seed)
    t = thresholds()
    people = []
    for i in range(n):
        sp = spec or SPECS[i % len(SPECS)]
        has_fsp = rng.random() < 0.25
        farmer = has_fsp and rng.random() < 0.2
        # Опорный грейд равномерно, θ вокруг его порога; участники ФСП в среднем немного сильнее, фармеры — слабее
        base = rng.choice(GRADE_ORDER)
        theta = t.cut(base) + rng.gauss(0.35, 0.7) + (0.15 if has_fsp else 0) - (0.6 if farmer else 0)
        pool = list(SPEC_POOL[sp])
        techs = set(SPEC_CORE[sp]) | set(rng.sample(pool, rng.randint(4, 8)))
        declared = set(techs)
        if rng.random() < 0.3:
            declared |= set(rng.sample([x for x in pool if x not in techs] or pool, rng.randint(1, 2)))
        if rng.random() < 0.2 and len(declared) > 3:
            declared.discard(rng.choice(sorted(declared - set(SPEC_CORE[sp])) or sorted(declared)))
        skills = set()
        if rng.random() < 0.35:
            fits = [s for s, ts in SKILL_TECHS.items() if set(ts) & techs]
            if fits:
                skills.add(rng.choice(fits))
        g_true = true_grade(theta, t) or "junior"
        threshold = None if rng.random() < 0.25 else int(round(
            MEDIAN_NET[g_true] * math.exp(rng.gauss(0, 0.25)) / 5000) * 5000)
        people.append(Person(
            ref=f"p{seed}-{i:05d}", spec=sp, theta=theta, claimed=_claimed(theta, t, rng),
            techs=frozenset(techs), declared=frozenset(declared), skills=frozenset(skills), threshold_net=threshold,
            formats=tuple(rng.sample(FORMATS, rng.randint(1, 2))), city=rng.choice(("Москва", "Казань", "Томск")),
            fsp_f=((round(fsp_f(PARAMS.fsp_pts_online * rng.randint(1, 2)), 3) if farmer
                    else round(min(0.95, max(0.1, rng.gauss(0.5, 0.15))), 2)) if has_fsp else 0.0),
            farmer=farmer, open_window=rng.random() < 0.7, active=rng.random() < 0.75))
    return people


def observe(people: list[Person], seed: int, express: bool = False) -> list[Person]:
    """Прогоняет каждому тест движком и собирает то, что видит ранжирование продукта."""
    t = thresholds()
    banks = {sp: synthetic_bank(AREAS[sp]) for sp in SPECS}
    for k, p in enumerate(people):
        cap = PARAMS.express_max if express else PARAMS.test_max
        ev = simulate_attempt(p.theta, AttemptConfig(Grade(p.claimed), t, cap, express), banks[p.spec],
                              AREAS[p.spec], rng_seed=seed * 1_000_003 + k)
        confirmed = ev.decision == Decision.confirmed
        p.decision = "confirmed" if confirmed else "not_confirmed"
        conf_techs = (set(SPEC_CORE[p.spec]) if confirmed else set()) | {
            x for s in p.skills for x in SKILL_TECHS[s] if x in p.techs}
        states = {x: ("confirmed" if x in conf_techs else "declared") for x in p.declared}
        states.update({x: "confirmed" for x in conf_techs})
        p.facts = CandidateFacts(
            ref=p.ref, specialization=p.spec, grade_status=p.decision,
            confirmed_grade=p.claimed if confirmed else None, claimed_grade=p.claimed, theta=ev.theta, se=ev.se,
            s=ev.s, fsp_f=p.fsp_f, stack=expand(states), stack_declared=True, formats=p.formats, city=p.city,
            salary_threshold_net=p.threshold_net,
            open_until=NOW + timedelta(days=5) if p.open_window else NOW - timedelta(days=3),
            last_activity_at=NOW - timedelta(days=3 if p.active else 60), express=express)
        p.extra["n_items"] = ev.n_answered
    return people


@dataclass(frozen=True)
class SynthNeed:
    key: str
    facts: NeedFacts


def make_needs(k: int, seed: int) -> list[SynthNeed]:
    rng = random.Random(seed + 17)
    out = []
    for i in range(k):
        sp = SPECS[i % len(SPECS)]
        grades = tuple(sorted(rng.sample(["junior", "middle", "senior"], rng.choice((1, 1, 2))),
                              key=["junior", "middle", "senior"].index))
        pool = [x for x in SPEC_POOL[sp] if x not in SPEC_CORE[sp]]
        must = tuple(rng.sample(list(SPEC_CORE[sp])[:2] + pool, rng.randint(2, 3)))
        nice = tuple(rng.sample([x for x in pool if x not in must], 1))
        top = max(grades, key=["junior", "middle", "senior"].index)
        fork_to = int(MEDIAN_NET[top] * rng.uniform(0.9, 1.3) / 5000) * 5000
        out.append(SynthNeed(f"n{seed}-{i:03d}", NeedFacts(sp, grades, must, nice, tuple(rng.sample(FORMATS, rng.randint(1, 2))),
                                                         fork_to)))
    return out
