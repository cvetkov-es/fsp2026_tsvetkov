"""Сервис попыток: склейка БД и чистого ядра (rules, selection, cooldowns).

Конкурентность: каждая операция кандидата сначала берёт FOR UPDATE на строку его профиля
(`_lock_profile`), потом — на попытку. Так старт, ответы и ленивое автозакрытие одного
кандидата выполняются строго по очереди, а порядок блокировок всегда один: профиль → попытка.
"""
import math
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.assessment.bank.areas import AREAS
from app.assessment.bank.base import REGISTRY
from app.assessment.bank.canon import CanonError, canonical
from app.assessment.bank.verdicts import AI_SPEC, check_verdict, make_verdict, parse_response
from app.assessment.bank_sync import ensure_thresholds, sync_bank
from app.assessment.engine.ai_verdicts import (
    VerdictRef,
    VerdictResult,
    choose_verdict,
    evaluate_ai,
    plan_slots,
    slots_needed,
)
from app.assessment.engine.cooldowns import (
    Availability,
    GradeAttemptRecord,
    grade_test_availability,
    skill_test_availability,
)
from app.assessment.engine.levels import PHASE1_BAND, PHASE2_BAND, Grade, Thresholds, grade_rank
from app.assessment.engine.rules import (
    AttemptConfig,
    Decision,
    Evaluation,
    ItemResult,
    autoclose,
    evaluate,
    strength,
)
from app.assessment.engine.selection import FamilyRef, choose_next, instance_seed, selection_rng
from app.assessment.engine.skill import SKILL_BAND, evaluate_skill
from app.assessment.models import Attempt, AttemptItem, ItemFamilyRow, ThresholdsRow
from app.assessment.phrases import ai_phrase, result_phrase, skill_phrase
from app.assessment.schemas import AnswerIn, SkillStartIn, StartIn
from app.assessment.skills import AI_SKILL_CODE, CATALOG, SKILLS, skill_code, skill_spec
from app.auth.consents import ConsentType, record_consent
from app.auth.models import Consent, User
from app.candidates.models import CandidateProfile, SkillResult
from app.candidates.service import declared_techs, get_or_create_profile, passed_skills
from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.hiring.votes import holder, status_grade, unlocks_higher_test
from app.matching.stack_dict import SKILL_TECHS, expand

GRACE_S = 5  # сетевой запас к лимиту времени на задание


def _secret() -> bytes:
    return get_settings().secret_key.encode()


# ---------- пороги и конфигурация ----------

def _to_thresholds(row: ThresholdsRow) -> Thresholds:
    return Thresholds(row.version, row.cut_j, row.cut_m, row.cut_s, row.virtual_gap)


def thresholds_for(db: Session, version: str) -> Thresholds:
    ensure_thresholds(db)
    return _to_thresholds(db.get(ThresholdsRow, version))


def current_thresholds(db: Session) -> Thresholds:
    ensure_thresholds(db)
    row = db.scalars(select(ThresholdsRow).order_by(ThresholdsRow.created_at.desc())).first()
    return _to_thresholds(row)


def _cfg(db: Session, a: Attempt) -> AttemptConfig:
    return AttemptConfig(Grade(a.target_grade), thresholds_for(db, a.thresholds_version),
                         a.item_cap, a.express)


def _items(db: Session, a: Attempt) -> list[AttemptItem]:
    return list(db.scalars(select(AttemptItem).where(AttemptItem.attempt_id == a.id)
                           .order_by(AttemptItem.seq)))


def _results(items: list[AttemptItem]) -> list[ItemResult]:
    return [ItemResult(i.seq, i.family_code, i.area, i.level, i.b, bool(i.correct), i.phase)
            for i in items if i.answered_at is not None]


def _open(items: list[AttemptItem]) -> AttemptItem | None:
    return next((i for i in items if i.answered_at is None), None)


def _lock_profile(db: Session, user: User) -> CandidateProfile:
    get_or_create_profile(db, user)
    return db.scalars(select(CandidateProfile).where(CandidateProfile.user_id == user.id)
                      .with_for_update().execution_options(populate_existing=True)).one()


def _load(db: Session, user: User, attempt_id: uuid.UUID, lock: bool = False) -> Attempt:
    stmt = select(Attempt).where(Attempt.id == attempt_id, Attempt.user_id == user.id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    a = db.scalar(stmt)
    if a is None:
        raise AppError(404, "attempt_not_found", "Попытка не найдена")
    return a


# ---------- профиль и решения ----------

def _apply_to_profile(db: Session, a: Attempt, p: CandidateProfile) -> None:
    before = (p.specialization, status_grade(p))
    _apply_decision(a, p)
    if (p.specialization, status_grade(p)) != before:
        p.grade_changed_at = now()  # голоса прежней категории — в архив навсегда (процесс 5)


def _apply_decision(a: Attempt, p: CandidateProfile) -> None:
    target = Grade(a.target_grade)
    if a.decision == Decision.confirmed:
        p.confirmed_grade, p.grade_status, p.status_attempt_id = target.value, "confirmed", a.id
    elif p.confirmed_grade is None or Grade(p.confirmed_grade) == target:
        # первый провал или повторная сдача подтверждённого грейда — статус по последней попытке
        p.confirmed_grade, p.grade_status, p.status_attempt_id = None, "not_confirmed", a.id
    # провал теста на другой грейд при наличии подтверждённого не меняет подтверждённый
    p.claimed_grade = p.confirmed_grade or target.value
    p.last_activity_at = now()


def _refresh_profile_cache(db: Session, p: CandidateProfile, a: Attempt) -> None:
    if p.status_attempt_id != a.id or a.theta is None:
        return
    cur, g = current_thresholds(db), Grade(a.target_grade)
    p.theta, p.se = a.theta, a.se
    p.s_cache = strength(a.theta, a.se, cur.cut(g), cur.next_cut(g), PARAMS.se_penalty)


def _record_eval(db: Session, a: Attempt, ev: Evaluation, p: CandidateProfile) -> None:
    a.theta, a.se, a.p_confirm, a.s = ev.theta, ev.se, ev.p_confirm, ev.s
    if ev.decision is not None and a.decision is None:
        a.decision, a.decided_at_n, a.border, a.decided_at = ev.decision.value, ev.decided_at, ev.border, now()
        _apply_to_profile(db, a, p)
    if ev.status == "finished" and a.status == "in_progress":
        a.status, a.finished_at, a.confident = "completed", now(), ev.confident
    _refresh_profile_cache(db, p, a)


def _expired_at(a: Attempt) -> datetime:
    """Момент, когда попытка закрылась бы при немедленной проверке.

    Ленивое закрытие должно давать тот же результат, что и мгновенное: иначе кулдаун
    отсчитывался бы от дня, когда кандидат случайно вернулся.
    """
    return a.last_activity_at + timedelta(hours=PARAMS.attempt_autoclose_hours)


def apply_autoclose(db: Session, a: Attempt, p: CandidateProfile) -> None:
    """Вызывающий держит блокировку профиля (_lock_profile)."""
    if a.status != "in_progress":
        return
    if a.kind == "skill":
        if _is_ai(a):
            items = _items(db, a)
            deadline = _ai_deadline(a, items)
            if deadline is not None and now() >= deadline + timedelta(seconds=GRACE_S):
                _finish_ai(db, a, items, True, deadline)  # как при мгновенном закрытии: в момент дедлайна
                return
        if now() >= _expired_at(a):
            a.status, a.finished_at = "incomplete", _expired_at(a)  # навык без решения: ни результата, ни кулдауна
        return
    items = _items(db, a)
    res = _results(items)
    r = autoclose(_cfg(db, a), res, a.last_activity_at, now())
    if r is None:
        return
    at = _expired_at(a)
    if r.outcome == "completed":
        a.status, a.finished_at, a.confident = "completed", at, False
    elif r.outcome == "autoclosed":
        ev = evaluate(_cfg(db, a), res)
        a.theta, a.se, a.p_confirm, a.s = ev.theta, ev.se, ev.p_confirm, ev.s
        a.decision, a.border, a.decided_at, a.decided_at_n = r.decision.value, True, at, len(res)
        a.status, a.finished_at = "autoclosed", at
        _apply_to_profile(db, a, p)
        _refresh_profile_cache(db, p, a)
    else:
        a.status, a.finished_at = "incomplete", at


def _autoclose_user(db: Session, user: User, p: CandidateProfile) -> None:
    """Вызывающий держит блокировку профиля (_lock_profile)."""
    for a in db.scalars(select(Attempt).where(Attempt.user_id == user.id, Attempt.status == "in_progress")
                        .with_for_update().execution_options(populate_existing=True)):
        apply_autoclose(db, a, p)


def _active_grade_attempt(db: Session, user: User) -> Attempt | None:
    return db.scalar(select(Attempt).where(Attempt.user_id == user.id, Attempt.kind == "grade",
                                           Attempt.status == "in_progress"))


def ensure_no_active_attempt(db: Session, user: User) -> None:
    """Смена специализации посреди попытки записала бы результат в чужую категорию."""
    p = _lock_profile(db, user)
    _autoclose_user(db, user, p)
    if _active_grade_attempt(db, user) is not None:
        db.commit()
        raise AppError(409, "attempt_in_progress", "Сначала завершите начатый тест")


# ---------- доступность и старт ----------

def grade_availability(db: Session, user: User, p: CandidateProfile, target: str) -> Availability:
    stmt = select(Attempt).where(Attempt.user_id == user.id, Attempt.kind == "grade",
                                 Attempt.decision.is_not(None))
    history = [
        GradeAttemptRecord(Grade(a.target_grade), a.decided_at, Decision(a.decision), a.confident)
        for a in db.scalars(stmt)
        if p.cooldown_reset_at is None or a.decided_at > p.cooldown_reset_at
    ]
    confirmed = Grade(p.confirmed_grade) if p.confirmed_grade else None
    unlock = unlocks_higher_test(db, user.id, holder(p) if p.grade_status == "confirmed" else None, now())
    return grade_test_availability(Grade(target), history, confirmed, unlock, now())


def availability_all(db: Session, user: User) -> dict[str, Availability]:
    p = _lock_profile(db, user)
    _autoclose_user(db, user, p)
    db.commit()
    return {g: grade_availability(db, user, p, g) for g in ("junior", "middle", "senior")}


def _has_rules_consent(db: Session, user: User) -> bool:
    return db.scalar(select(Consent.id).where(
        Consent.user_id == user.id, Consent.type == ConsentType.automated_rules.value,
        Consent.revoked_at.is_(None))) is not None


def start_attempt(db: Session, user: User, data: StartIn) -> Attempt:
    p = _lock_profile(db, user)
    if not p.specialization:
        raise AppError(409, "survey_required", "Сначала выберите специализацию и грейд")
    if not (data.accept_rules and data.pledge):
        raise AppError(422, "rules_required", "Нужно принять правила теста и обязательство")
    if not _family_rows(db, p.specialization):
        raise AppError(409, "bank_unavailable", "Тест по этому направлению пока готовится")
    if not _has_rules_consent(db, user):
        record_consent(db, user.id, ConsentType.automated_rules)
    _autoclose_user(db, user, p)
    active = _active_grade_attempt(db, user)
    if active is not None:
        if active.target_grade == data.target_grade:
            db.commit()
            return active
        db.commit()
        raise AppError(409, "attempt_in_progress", "Сначала завершите начатый тест")
    if p.confirmed_grade and grade_rank(Grade(data.target_grade)) < grade_rank(Grade(p.confirmed_grade)):
        db.commit()
        raise AppError(409, "grade_below_confirmed", "Этот грейд ниже уже подтверждённого")
    av = grade_availability(db, user, p, data.target_grade)
    if not av.allowed:
        db.commit()
        raise AppError(409, "cooldown", "Пересдача пока недоступна",
                       av.available_at.isoformat() if av.available_at else None)
    a = Attempt(user_id=user.id, kind="grade", specialization=p.specialization,
                target_grade=data.target_grade, express=data.express,
                item_cap=PARAMS.express_max if data.express else PARAMS.test_max,
                extra_time=data.extra_time, thresholds_version=current_thresholds(db).version,
                started_at=now(), last_activity_at=now())
    db.add(a)
    db.commit()
    return a


# ---------- состояние для API ----------

def _result(a: Attempt, answered: list[AttemptItem]) -> dict | None:
    if a.decision is None:
        return None
    correct = sum(1 for i in answered if i.correct)
    above = sum(1 for i in answered if i.correct and i.phase == 2)
    return {"decision": a.decision,
            "phrase": result_phrase(a.target_grade, a.decision, correct, len(answered), above),
            "reliability": a.p_confirm, "border": a.border, "confident": a.confident,
            "express": a.express}


def _item_out(open_item: AttemptItem | None) -> dict | None:
    if open_item is None:
        return None
    pub = open_item.instance["public"]
    elapsed = (now() - open_item.presented_at).total_seconds()
    return {"seq": open_item.seq, "phase": open_item.phase, "kind": pub["kind"], "prompt": pub["prompt"],
            "time_limit_s": open_item.time_limit_s,
            "remaining_s": max(0, math.ceil(open_item.time_limit_s - elapsed)),
            "presented_at": open_item.presented_at}


def _skill_state(db: Session, a: Attempt) -> dict:
    items = _items(db, a)
    answered = [i for i in items if i.answered_at is not None]
    stage = "phase1" if a.status == "in_progress" else "incomplete" if a.status == "incomplete" else "finished"
    result, ai = None, None
    if _is_ai(a):
        ai, result = _ai_state(db, a, items)
    elif a.decision is not None:
        title = SKILLS[skill_code(a.specialization)].title
        result = {"decision": a.decision,
                  "phrase": skill_phrase(title, a.decision, sum(1 for i in answered if i.correct), len(answered)),
                  "reliability": a.p_confirm, "border": False, "confident": False, "express": False}
    return {"id": str(a.id), "target_grade": "skill", "skill_code": skill_code(a.specialization), "ai": ai,
            "express": False, "status": a.status, "stage": stage,
            "n_answered": len(answered), "phase2_total": 0, "phase2_answered": 0,
            "bank_exhausted": a.bank_exhausted, "item": _item_out(_open(items) if a.status == "in_progress" else None),
            "result": result}


def attempt_state(db: Session, a: Attempt) -> dict:
    if a.kind == "skill":
        return _skill_state(db, a)
    items = _items(db, a)
    ev = evaluate(_cfg(db, a), _results(items))
    answered = [i for i in items if i.answered_at is not None]
    if a.status == "in_progress":
        stage = ev.status
    else:
        stage = "incomplete" if a.status == "incomplete" else "finished"
    item = _item_out(_open(items) if a.status == "in_progress" else None)
    return {"id": str(a.id), "target_grade": a.target_grade, "express": a.express, "status": a.status,
            "stage": stage, "n_answered": len(answered), "phase2_total": ev.phase2_total,
            "phase2_answered": sum(1 for i in answered if i.phase == 2),
            "bank_exhausted": a.bank_exhausted, "item": item, "result": _result(a, answered)}


def get_attempt_state(db: Session, user: User, attempt_id: uuid.UUID) -> dict:
    p = _lock_profile(db, user)
    a = _load(db, user, attempt_id, lock=True)
    apply_autoclose(db, a, p)
    db.commit()
    return attempt_state(db, a)


# ---------- выдача и ответы ----------

def _family_rows(db: Session, specialization: str) -> list[ItemFamilyRow]:
    stmt = (select(ItemFamilyRow).where(ItemFamilyRow.specialization == specialization,
                                        ItemFamilyRow.status == "active")
            .execution_options(populate_existing=True))
    rows = list(db.scalars(stmt))
    if not rows or any(r.code not in REGISTRY for r in rows):
        sync_bank(db)
        rows = list(db.scalars(stmt))
    return [r for r in rows if r.code in REGISTRY]


def _close_exhausted(db: Session, a: Attempt, p: CandidateProfile, ev: Evaluation) -> None:
    a.bank_exhausted = True
    a.theta, a.se, a.p_confirm, a.s = ev.theta, ev.se, ev.p_confirm, ev.s
    if a.decision is None and ev.n_answered < PARAMS.n_min_decide:
        # Как при автозакрытии: без N_MIN_DECIDE ответов решения нет — ни статуса, ни кулдауна
        a.status, a.finished_at = "incomplete", now()
        return
    if a.decision is None:
        d = Decision.confirmed if ev.p_confirm >= 0.5 else Decision.not_confirmed
        a.decision, a.border, a.decided_at, a.decided_at_n = d.value, True, now(), ev.n_answered
        _apply_to_profile(db, a, p)
    a.status, a.finished_at, a.confident = "completed", now(), False
    _refresh_profile_cache(db, p, a)


def _bump_exposure(db: Session, code: str) -> None:
    # SET x = x + 1 на стороне БД: параллельные показы одного семейства не теряют инкремент
    db.execute(update(ItemFamilyRow).where(ItemFamilyRow.code == code)
               .values(exposure_count=ItemFamilyRow.exposure_count + 1)
               .execution_options(synchronize_session=False))


def _present(db: Session, user: User, a: Attempt, items: list[AttemptItem], areas: tuple[str, ...],
             band: tuple[int, ...], theta: float, phase: int) -> bool:
    """Выбрать семейство, создать экземпляр и показать. False — подходящих семейств не осталось."""
    rows = _family_rows(db, a.specialization)
    refs = [FamilyRef(r.code, r.area, r.level, r.b, r.exposure_count) for r in rows]
    seen = _seen_families(db, user, a)
    seq = len(items) + 1
    ref = choose_next(families=refs, areas=areas, used_in_attempt={i.family_code for i in items},
                      area_counts=Counter(i.area for i in items), seen=seen, band=band, theta=theta,
                      b_levels=PARAMS.b_levels, rng=selection_rng(_secret(), str(a.id), seq), k=PARAMS.randomesque_k)
    if ref is None:
        return False
    fam = REGISTRY[ref.code]
    seed = instance_seed(_secret(), str(user.id), str(a.id), ref.code)
    inst = fam.make(seed)
    factor = PARAMS.item_time_factor * ((1 + PARAMS.extra_time) if a.extra_time else 1)
    db.add(AttemptItem(attempt_id=a.id, seq=seq, phase=phase, family_code=ref.code, area=ref.area,
                       level=ref.level, b=ref.b, seed=str(seed), instance=inst.key(),
                       time_limit_s=math.ceil(fam.median_time_s * factor), presented_at=now()))
    if not a.synthetic:
        _bump_exposure(db, ref.code)
    a.last_activity_at = now()
    return True


def present_next(db: Session, user: User, attempt_id: uuid.UUID) -> Attempt:
    p = _lock_profile(db, user)
    a = _load(db, user, attempt_id, lock=True)
    apply_autoclose(db, a, p)
    if a.status != "in_progress":
        db.commit()
        return a
    items = _items(db, a)
    if _open(items) is not None:
        db.commit()
        return a
    if _is_ai(a):
        _present_ai(db, user, a, items)
        db.commit()
        return a
    if a.kind == "skill":
        ev_skill = evaluate_skill(_results(items))
        if ev_skill.status == "in_progress" and not _present(
                db, user, a, items, SKILLS[skill_code(a.specialization)].areas, SKILL_BAND, ev_skill.theta, 1):
            a.bank_exhausted, a.status, a.finished_at = True, "incomplete", now()  # без решения и кулдауна
        db.commit()
        return a
    cfg = _cfg(db, a)
    ev = evaluate(cfg, _results(items))
    if ev.status in ("finished", "awaiting_continue"):
        db.commit()
        return a
    phase = 1 if ev.status == "phase1" else 2
    band = (PHASE1_BAND if phase == 1 else PHASE2_BAND)[cfg.target]
    if not _present(db, user, a, items, AREAS[a.specialization], band, ev.theta, phase):
        _close_exhausted(db, a, p, ev)
    db.commit()
    return a


def _matches(kind: str, stored, response) -> bool:
    if response is None:
        return False
    try:
        return canonical(kind, response) == canonical(kind, stored)
    except (CanonError, TypeError, ValueError, KeyError, OverflowError):
        return False


def submit_answer(db: Session, user: User, attempt_id: uuid.UUID, data: AnswerIn) -> Attempt:
    p = _lock_profile(db, user)
    a = _load(db, user, attempt_id, lock=True)
    apply_autoclose(db, a, p)
    if a.status != "in_progress":
        db.commit()
        raise AppError(409, "attempt_closed", "Попытка уже завершена")
    items = _items(db, a)
    item = next((i for i in items if i.seq == data.seq), None)
    if item is None:
        db.commit()
        raise AppError(404, "item_not_found", "Задание не найдено")
    if item.answered_at is not None:
        db.commit()
        return a  # повторная отправка: состояние не меняется
    t = now()
    elapsed = (t - item.presented_at).total_seconds()
    timed_out = elapsed > item.time_limit_s + GRACE_S
    kind = item.instance["public"]["kind"]
    if kind == "verdict":  # SQL-вердикт исполняет запросы на данных кандидата — в отдельном процессе
        item.correct = (not timed_out) and check_verdict(item.instance["answer"], data.response)
    else:
        item.correct = (not timed_out) and _matches(kind, item.instance["answer"], data.response)
    item.answered_at, item.time_ms, item.timed_out = t, int(elapsed * 1000), timed_out
    item.response, item.events = data.response, data.events
    a.last_activity_at = t
    p.last_activity_at = t
    if _is_ai(a):
        _record_ai(db, a, items)
    elif a.kind == "skill":
        _record_skill(db, a, items)
    else:
        _record_eval(db, a, evaluate(_cfg(db, a), _results(items)), p)
    db.commit()
    return a


def _record_skill(db: Session, a: Attempt, items: list[AttemptItem]) -> None:
    """Навык не трогает грейд и кэш ранжирования: только skill_results (их читают стек и подборка)."""
    ev = evaluate_skill(_results(items))
    a.theta, a.se, a.p_confirm = ev.theta, ev.se, ev.p_pass
    if ev.status != "finished":
        return
    a.decision, a.decided_at, a.decided_at_n = ev.decision.value, now(), ev.n_answered
    a.status, a.finished_at = "completed", now()
    db.add(SkillResult(user_id=a.user_id, skill_code=skill_code(a.specialization),
                       passed=ev.decision == Decision.confirmed, attempt_id=a.id,
                       metrics={"theta": round(ev.theta, 3), "se": round(ev.se, 3), "p_pass": round(ev.p_pass, 3),
                                "correct": sum(1 for i in items if i.correct), "n": ev.n_answered}))


def extend_express(db: Session, user: User, attempt_id: uuid.UUID) -> Attempt:
    p = _lock_profile(db, user)
    a = _load(db, user, attempt_id, lock=True)
    apply_autoclose(db, a, p)
    if a.kind != "grade":
        db.commit()
        raise AppError(409, "not_extendable", "Продолжить можно только экспресс-тест без решения")
    ev = evaluate(_cfg(db, a), _results(_items(db, a)))
    if a.status != "in_progress" or not a.express or ev.status != "awaiting_continue":
        db.commit()
        raise AppError(409, "not_extendable", "Продолжить можно только экспресс-тест без решения")
    a.express, a.item_cap = False, PARAMS.test_max
    db.commit()
    return a


def list_attempts(db: Session, user: User) -> list[dict]:
    p = _lock_profile(db, user)
    _autoclose_user(db, user, p)
    db.commit()
    attempts = list(db.scalars(select(Attempt).where(Attempt.user_id == user.id, Attempt.kind == "grade")
                               .order_by(Attempt.started_at.desc())))
    answered: dict[uuid.UUID, list[AttemptItem]] = defaultdict(list)
    for i in db.scalars(select(AttemptItem).where(AttemptItem.attempt_id.in_([a.id for a in attempts]),
                                                  AttemptItem.answered_at.is_not(None))):
        answered[i.attempt_id].append(i)
    out = []
    for a in attempts:
        res = _result(a, answered[a.id])
        out.append({"id": str(a.id), "target_grade": a.target_grade, "express": a.express,
                    "status": a.status, "decision": a.decision, "phrase": res["phrase"] if res else None,
                    "started_at": a.started_at, "finished_at": a.finished_at})
    return out


# ---------- навыки ----------

def skill_availability(db: Session, user: User, p: CandidateProfile, code: str) -> Availability:
    """Пересдача навыка — через COOLDOWN_SKILL после завершённой попытки (процесс 2.6); сброс демо учитывается."""
    stmt = (select(Attempt.finished_at).where(Attempt.user_id == user.id, Attempt.kind == "skill",
                                              Attempt.specialization == skill_spec(code), Attempt.status == "completed")
            .order_by(Attempt.finished_at.desc()).limit(1))
    last = db.scalar(stmt)
    if last is not None and p.cooldown_reset_at is not None and last <= p.cooldown_reset_at:
        last = None
    return skill_test_availability(last, now())


def _skill_bank_ready(code: str, rows: list[ItemFamilyRow]) -> bool:
    return _ai_bank_ready(rows) if code == AI_SKILL_CODE else bool(rows)


def _active_skill_attempt(db: Session, user: User) -> Attempt | None:
    return db.scalar(select(Attempt).where(Attempt.user_id == user.id, Attempt.kind == "skill",
                                           Attempt.status == "in_progress"))


def start_skill_attempt(db: Session, user: User, code: str, data: SkillStartIn) -> Attempt:
    if code not in CATALOG:
        raise AppError(404, "skill_not_found", "Навык не найден")
    p = _lock_profile(db, user)
    if not (data.accept_rules and data.pledge):
        raise AppError(422, "rules_required", "Нужно принять правила теста и обязательство")
    spec = skill_spec(code)
    if not _skill_bank_ready(code, _family_rows(db, spec)):
        raise AppError(409, "bank_unavailable", "Тест навыка пока готовится")
    if not _has_rules_consent(db, user):
        record_consent(db, user.id, ConsentType.automated_rules)
    _autoclose_user(db, user, p)
    if code in passed_skills(db, user.id):
        db.commit()
        raise AppError(409, "skill_already_confirmed", "Навык уже подтверждён")
    active = _active_skill_attempt(db, user)
    if active is not None:
        db.commit()
        if active.specialization == spec:
            return active
        raise AppError(409, "attempt_in_progress", "Сначала завершите начатый тест навыка")
    av = skill_availability(db, user, p, code)
    if not av.allowed:
        db.commit()
        raise AppError(409, "cooldown", "Пересдача навыка пока недоступна",
                       av.available_at.isoformat() if av.available_at else None)
    a = Attempt(user_id=user.id, kind="skill", specialization=spec, target_grade="skill", express=False,
                item_cap=PARAMS.ai_verdicts if code == AI_SKILL_CODE else PARAMS.skill_len, extra_time=data.extra_time,
                thresholds_version=current_thresholds(db).version, started_at=now(), last_activity_at=now())
    db.add(a)
    db.commit()
    return a


def skills_overview(db: Session, user: User) -> list[dict]:
    p = _lock_profile(db, user)
    _autoclose_user(db, user, p)
    passed = passed_skills(db, user.id)
    # с подразумеваемыми: заявленный TypeScript рекомендует «Основы фронтенда» через JavaScript
    declared = set(expand({t: "declared" for t in declared_techs(db, user.id)}))
    out = []
    for code, s in CATALOG.items():
        attempts = list(db.scalars(select(Attempt).where(Attempt.user_id == user.id, Attempt.kind == "skill",
                                                         Attempt.specialization == skill_spec(code))))
        active = next((a for a in attempts if a.status == "in_progress"), None)
        done = any(a.status == "completed" for a in attempts)
        av = skill_availability(db, user, p, code)
        techs = list(SKILL_TECHS.get(code, ()))
        status = "passed" if code in passed else "failed" if done else "not_taken"
        out.append({"code": code, "title": s.title, "summary": s.summary, "techs": techs, "status": status,
                    "available": av.allowed and status != "passed", "available_at": av.available_at,
                    "active_attempt_id": str(active.id) if active else None,
                    "recommended": status != "passed" and bool(set(techs) & declared),
                    "bank_ready": _skill_bank_ready(code, _family_rows(db, skill_spec(code))),
                    "format": "ai" if code == AI_SKILL_CODE else "test",
                    "items": PARAMS.ai_verdicts if code == AI_SKILL_CODE else PARAMS.skill_len,
                    "minutes": PARAMS.ai_minutes if code == AI_SKILL_CODE else None})
    db.commit()
    return out


# ---------- «Работа с ИИ» (процесс 2.5, ⚑3) ----------

def _is_ai(a: Attempt) -> bool:
    return a.kind == "skill" and a.specialization == AI_SPEC


def _ai_seconds(a: Attempt) -> float:
    return PARAMS.ai_minutes * 60 * ((1 + PARAMS.extra_time) if a.extra_time else 1)


def _ai_deadline(a: Attempt, items: list[AttemptItem]) -> datetime | None:
    """Общий таймер — от показа первого вердикта: он открывается сразу после «Начать»."""
    return items[0].presented_at + timedelta(seconds=_ai_seconds(a)) if items else None


def _ai_bank_ready(rows: list[ItemFamilyRow]) -> bool:
    have = Counter(r.area for r in rows)
    return all(have[area] >= n for area, n in slots_needed().items())


def _seen_families(db: Session, user: User, a: Attempt) -> set[str]:
    return set(db.scalars(select(AttemptItem.family_code).join(Attempt, Attempt.id == AttemptItem.attempt_id)
                          .where(Attempt.user_id == user.id, Attempt.id != a.id)))


def _ai_results(items: list[AttemptItem]) -> list[VerdictResult]:
    out = []
    for i in items:
        if i.answered_at is None:
            continue
        r = None if i.timed_out else parse_response(i.response)
        out.append(VerdictResult(i.instance["answer"]["truth"], r.verdict if r else None,
                                 r is None or r.confidence == "high", bool(i.correct)))
    return out


def _finish_ai(db: Session, a: Attempt, items: list[AttemptItem], time_over: bool, at: datetime) -> None:
    """Итог попытки. Ни одного ответа — попытка не засчитана: ни результата, ни кулдауна."""
    answered = [i for i in items if i.answered_at is not None]
    if not answered:
        a.status, a.finished_at = "incomplete", at
        return
    end = at if time_over else max(i.answered_at for i in answered)
    ev = evaluate_ai(_ai_results(items), time_over=time_over,
                     elapsed_s=(end - items[0].presented_at).total_seconds())
    a.decision = (Decision.confirmed if ev.passed else Decision.not_confirmed).value
    a.decided_at, a.decided_at_n, a.p_confirm = at, ev.answered, ev.accuracy
    a.status, a.finished_at = "completed", at
    db.add(SkillResult(user_id=a.user_id, skill_code=AI_SKILL_CODE, passed=bool(ev.passed), attempt_id=a.id,
                       metrics=ev.metrics()))


def _present_ai(db: Session, user: User, a: Attempt, items: list[AttemptItem]) -> None:
    deadline = _ai_deadline(a, items)
    if deadline is not None and now() >= deadline:
        _finish_ai(db, a, items, True, deadline)
        return
    seq = len(items) + 1
    slot = plan_slots(selection_rng(_secret(), str(a.id), 0))[seq - 1]  # план попытки: seq 0 — не номер вердикта
    refs = [VerdictRef(r.code, r.area, r.b, r.exposure_count) for r in _family_rows(db, AI_SPEC)]
    ref = choose_verdict(refs, slot.area, {i.family_code for i in items}, _seen_families(db, user, a),
                         selection_rng(_secret(), str(a.id), seq))
    if ref is None:
        a.bank_exhausted, a.status, a.finished_at = True, "incomplete", now()
        return
    seed = instance_seed(_secret(), str(user.id), str(a.id), ref.code)
    inst = make_verdict(ref.code, seed, slot.flawed)
    left = (deadline - now()).total_seconds() if deadline else _ai_seconds(a)
    db.add(AttemptItem(attempt_id=a.id, seq=seq, phase=1, family_code=ref.code, area=ref.area, level=2, b=ref.b,
                       seed=str(seed), instance=inst.key(), time_limit_s=max(1, math.ceil(left)), presented_at=now()))
    if not a.synthetic:
        _bump_exposure(db, ref.code)
    a.last_activity_at = now()


def _record_ai(db: Session, a: Attempt, items: list[AttemptItem]) -> None:
    deadline = _ai_deadline(a, items)
    # число вердиктов — то, с которым попытка началась (item_cap); PARAMS попытки менять на ходу нельзя:
    # план мест plan_slots тоже считается из них при каждом показе
    if sum(1 for i in items if i.answered_at is not None) >= a.item_cap:
        _finish_ai(db, a, items, False, now())
    elif deadline is not None and now() >= deadline:
        _finish_ai(db, a, items, True, deadline)


def _ai_state(db: Session, a: Attempt, items: list[AttemptItem]) -> tuple[dict, dict | None]:
    """Прогресс для экрана теста и итог с метриками (их пишет _finish_ai в skill_results)."""
    deadline = _ai_deadline(a, items)
    left = (max(0, math.ceil((deadline - now()).total_seconds()))
            if deadline is not None and a.status == "in_progress" else None)
    progress = {"total": PARAMS.ai_verdicts, "time_left_s": left, "minutes": PARAMS.ai_minutes,
                "sql_max_rows": PARAMS.sql_input_max_rows, "pass_accuracy": PARAMS.ai_pass_accuracy,
                "pass_miss": PARAMS.ai_pass_miss, "cooldown_days": PARAMS.cooldown_skill_days}
    if a.decision is None:
        return progress, None
    m = db.scalar(select(SkillResult.metrics).where(SkillResult.attempt_id == a.id))
    return progress, {"decision": a.decision, "phrase": ai_phrase(a.decision, m), "reliability": None,
                      "border": False, "confident": False, "express": False, "ai": m}
