import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.assessment.engine.levels import Grade, grade_rank
from app.config.params import PARAMS, Params

NDFL = PARAMS.ndfl  # имя сохранено: его импортирует контакт (план 05)


def to_net(amount: int | None, gross_net: str) -> int | None:
    if amount is None:
        return None
    return amount if gross_net == "net" else round(amount * (1 - NDFL))


def fsp_f(points: float, params: Params = PARAMS) -> float:
    return 1 - math.exp(-points / params.fsp_saturation)


@dataclass(frozen=True)
class CandidateFacts:
    ref: str
    specialization: str
    grade_status: str  # confirmed | not_confirmed | not_tested
    confirmed_grade: str | None
    claimed_grade: str | None
    theta: float
    se: float
    s: float
    fsp_f: float = 0.0
    fsp_visible: bool = True
    m: float = 1.0  # множитель собеседований (процесс 5), из hiring.votes.vote_stats
    interview_positive: int = 0  # действующих «соответствует» и «выше»
    interview_badge: bool = False
    stack: dict[str, str] = field(default_factory=dict)  # tech -> confirmed | declared (уже с implies)
    stack_declared: bool = True  # False — кандидат не заявил ни одной технологии: стек «не указан»
    formats: tuple[str, ...] = ()
    city: str | None = None
    salary_threshold_net: int | None = None
    open_until: datetime | None = None
    last_activity_at: datetime | None = None
    signal_to_company: bool = False
    confirmed_at: datetime | None = None
    express: bool = False
    minor: bool = False  # 14–17 лет с согласием представителя: только стажировка и каникулы (2.10)


@dataclass(frozen=True)
class NeedFacts:
    specialization: str
    grades: tuple[str, ...]
    must: tuple[str, ...]
    nice: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()
    salary_to_net: int | None = None
    employment: str = "full"  # full | internship | vacation


@dataclass(frozen=True)
class StackScore:
    value: float
    confirmed: tuple[str, ...]
    declared: tuple[str, ...]
    missing: tuple[str, ...]
    known: bool


@dataclass(frozen=True)
class AcceptScore:
    value: float
    salary: float | None
    salary_gap: float | None  # >0 — вилка ниже порога на эту долю
    format: float | None
    window_open: bool
    active: bool
    signal: bool


@dataclass(frozen=True)
class Ranked:
    c: CandidateFacts
    block: int
    subblock: int
    score: float
    fit: float
    r: float
    stack: StackScore
    accept: AcceptScore
    conflicts: tuple[str, ...]


def strength_r(c: CandidateFacts, params: Params = PARAMS) -> float:
    f = c.fsp_f if c.fsp_visible else 0.0
    return c.s * (1 + params.fsp_weight * f) * c.m


def stack_score(c: CandidateFacts, need: NeedFacts, params: Params = PARAMS) -> StackScore:
    if not c.stack or not c.stack_declared:
        return StackScore(params.stack_unknown, (), (), (), False)
    conf = tuple(t for t in need.must if c.stack.get(t) == "confirmed")
    decl = tuple(t for t in need.must if c.stack.get(t) == "declared")
    miss = tuple(t for t in need.must if t not in c.stack)
    base = ((len(conf) + len(decl) * params.stack_declared) / len(need.must)
            if need.must else params.stack_unknown)
    nice_share = sum(1 for t in need.nice if t in c.stack) / len(need.nice) if need.nice else 0.0
    return StackScore(min(1.0, base + params.nice_bonus * nice_share), conf, decl, miss, True)


def _format_component(cf: tuple[str, ...], nf: tuple[str, ...], params: Params) -> float | str | None:
    if not cf or not nf:
        return None
    if set(cf) & set(nf):
        return 1.0
    if "hybrid" in cf or "hybrid" in nf:
        return params.format_compatible
    return "conflict"


def _salary_gap(c: CandidateFacts, need: NeedFacts) -> float | None:
    if not c.salary_threshold_net or not need.salary_to_net:
        return None
    return (c.salary_threshold_net - need.salary_to_net) / c.salary_threshold_net


def accept(c: CandidateFacts, need: NeedFacts, now: datetime, params: Params = PARAMS) -> AcceptScore:
    comps: list[float] = []
    gap = _salary_gap(c, need)
    salary = None
    if gap is not None:
        salary = 1.0 if gap <= 0 else max(0.0, 1 - gap / params.hard_salary_gap)
        comps.append(salary)
    fmt = _format_component(c.formats, need.formats, params)
    fmt_val = fmt if isinstance(fmt, float) else (0.0 if fmt == "conflict" else None)
    if fmt_val is not None:
        comps.append(fmt_val)
    window_open = c.open_until is not None and c.open_until >= now
    comps.append(1.0 if window_open else params.window_expired)
    active = c.last_activity_at is not None and now - c.last_activity_at <= timedelta(days=params.activity_days)
    comps.append(1.0 if active else params.activity_none)
    value = sum(comps) / len(comps)
    if c.signal_to_company:
        low = gap is not None and gap > params.hard_salary_gap
        value = max(value, params.signal_floor_low if low else params.signal_floor_ok)
    return AcceptScore(value, salary, gap, fmt if isinstance(fmt, float) else None, window_open, active,
                       c.signal_to_company)


def hard_conflicts(c: CandidateFacts, need: NeedFacts, st: StackScore, params: Params = PARAMS) -> tuple[str, ...]:
    out = []
    if st.known and len(st.missing) >= 2:
        out.append("must")
    if _format_component(c.formats, need.formats, params) == "conflict":
        out.append("format")
    gap = _salary_gap(c, need)
    if gap is not None and gap > params.hard_salary_gap:
        out.append("salary")
    return tuple(out)


def base_block(c: CandidateFacts, need: NeedFacts) -> tuple[int, int] | None:
    targets = [grade_rank(Grade(g)) for g in need.grades]
    if c.grade_status == "confirmed" and c.confirmed_grade:
        r = grade_rank(Grade(c.confirmed_grade))
        if r in targets:
            return 1, -r
        if min(abs(r - t) for t in targets) == 1:
            return 2, -r
        return None
    if c.grade_status == "not_confirmed" and c.claimed_grade in need.grades:
        return 3, -grade_rank(Grade(c.claimed_grade))
    return None


def fit(c: CandidateFacts, need: NeedFacts, st: StackScore, params: Params = PARAMS) -> float:
    r_hat = strength_r(c, params) / params.r_max
    penalty = params.must_missing_penalty if st.known and len(st.missing) == 1 else 1.0
    return (params.fit_w_stack * st.value + params.fit_w_r * r_hat) * penalty


def score(fit_value: float, accept_value: float, params: Params = PARAMS) -> float:
    return fit_value * (params.score_base + (1 - params.score_base) * accept_value)


def evaluate_candidate(c: CandidateFacts, need: NeedFacts, now: datetime, params: Params = PARAMS) -> Ranked | None:
    if c.minor and need.employment == "full":  # несовершеннолетний не попадает ни в один блок, даже в «Почти подходят»
        return None
    bb = base_block(c, need)
    if bb is None:
        return None
    st = stack_score(c, need, params)
    acc = accept(c, need, now, params)
    conf = hard_conflicts(c, need, st, params)
    f = fit(c, need, st, params)
    return Ranked(c, 4 if conf else bb[0], bb[1], score(f, acc.value, params), f, strength_r(c, params),
                  st, acc, conf)


def sort_key(r: Ranked):
    conf_at = r.c.confirmed_at.timestamp() if r.c.confirmed_at else float("inf")
    f = r.c.fsp_f if r.c.fsp_visible else 0.0
    return (r.block, r.subblock, -round(r.score, 9), -r.c.theta, -f, conf_at, r.c.ref)


def rank(cands: Iterable[CandidateFacts], need: NeedFacts, now: datetime, params: Params = PARAMS) -> list[Ranked]:
    out = [x for c in cands if (x := evaluate_candidate(c, need, now, params)) is not None]
    return sorted(out, key=sort_key)


def cell_rank(cands: Iterable[CandidateFacts], grade: str, params: Params = PARAMS) -> list[CandidateFacts]:
    cands = list(cands)

    def key(c):
        return (-strength_r(c, params), -c.theta, c.ref)

    conf = sorted((c for c in cands if c.grade_status == "confirmed" and c.confirmed_grade == grade), key=key)
    unconf = sorted((c for c in cands if c.grade_status == "not_confirmed" and c.claimed_grade == grade
                     and c.confirmed_grade is None), key=key)
    return conf + unconf


def level(x: float) -> str:
    return "высокое" if x >= 0.66 else "среднее" if x >= 0.4 else "низкое"
