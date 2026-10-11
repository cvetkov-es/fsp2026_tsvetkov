import statistics
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.models import Role, User
from app.candidates.models import CandidateProfile, CandidateStack, SkillResult
from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.hiring.votes import status_grade
from app.matching.scoring import to_net
from app.matching.stack_dict import SKILL_TECHS, SPEC_CORE, expand, normalize_many

SPECIALIZATIONS: dict[str, str] = {"backend": "Backend", "frontend": "Frontend", "data": "Data / Analytics"}
GRADE_INFO: dict[str, tuple[str, str]] = {
    "junior": ("Junior", "Решает заранее декомпозированные задачи, учится у команды"),
    "middle": ("Middle", "Самостоятельно решает сложные задачи в своей зоне; обычно 2–4 года опыта"),
    "senior": ("Senior", "Проектирует решения и отвечает за направление; обычно 5+ лет опыта"),
}
DETAIL_FIELDS = ("full_name", "contacts", "experience_years", "formats", "city", "domains",
                 "salary_threshold", "salary_gross_net")


def get_or_create_profile(db: Session, user: User) -> CandidateProfile:
    if user.role != Role.candidate:
        raise AppError(403, "forbidden", "Доступно только кандидатам")
    profile = db.get(CandidateProfile, user.id)
    if profile is None:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    return profile


def update_survey(db: Session, user: User, specialization: str, claimed_grade: str) -> CandidateProfile:
    p = get_or_create_profile(db, user)
    before = (p.specialization, status_grade(p))
    if p.specialization and p.specialization != specialization:
        p.grade_status, p.confirmed_grade, p.status_attempt_id = "not_tested", None, None
        p.theta = p.se = p.s_cache = None
    p.specialization = specialization
    p.claimed_grade = p.confirmed_grade or claimed_grade
    if before[0] is not None and (p.specialization, status_grade(p)) != before:
        p.grade_changed_at = now()  # голоса прежней категории — в архив навсегда (процесс 5)
    p.last_activity_at = now()
    db.commit()
    return p


def update_details(db: Session, user: User, data) -> CandidateProfile:
    p = get_or_create_profile(db, user)
    for f in DETAIL_FIELDS:
        setattr(p, f, getattr(data, f))
    p.last_activity_at = now()
    db.commit()
    return p


def confirmed_techs(specialization: str | None, grade_confirmed: bool, passed_skills: set[str]) -> set[str]:
    out: set[str] = set()
    if grade_confirmed and specialization:
        out |= set(SPEC_CORE[specialization])
    for s in passed_skills:
        out |= set(SKILL_TECHS.get(s, ()))
    return out


def passed_skills(db: Session, user_id) -> set[str]:
    return set(db.scalars(select(SkillResult.skill_code).where(SkillResult.user_id == user_id,
                                                             SkillResult.passed.is_(True))))


def declared_techs(db: Session, user_id) -> list[str]:
    return sorted(db.scalars(select(CandidateStack.tech).where(CandidateStack.user_id == user_id)))


def stack_states(db: Session, p: CandidateProfile) -> dict[str, str]:
    declared = set(declared_techs(db, p.user_id))
    confirmed = confirmed_techs(p.specialization, p.grade_status == "confirmed", passed_skills(db, p.user_id))
    states = {t: ("confirmed" if t in confirmed else "declared") for t in declared}
    states.update({t: "confirmed" for t in confirmed})
    return expand(states)


def set_stack(db: Session, user: User, techs: list[str]) -> tuple[CandidateProfile, list[str]]:
    p = get_or_create_profile(db, user)
    known, unknown = normalize_many(techs)
    db.execute(delete(CandidateStack).where(CandidateStack.user_id == user.id))
    db.add_all(CandidateStack(user_id=user.id, tech=t) for t in known)
    p.last_activity_at = now()
    db.commit()
    return p, unknown


def open_window(db: Session, user: User) -> CandidateProfile:
    p = get_or_create_profile(db, user)
    p.open_until = now() + timedelta(days=PARAMS.open_window_days)
    p.last_activity_at = now()
    db.commit()
    return p


def market_median(db: Session, p: CandidateProfile) -> tuple[int | None, int]:
    grade = p.confirmed_grade or p.claimed_grade
    rows = db.execute(select(CandidateProfile.salary_threshold, CandidateProfile.salary_gross_net).where(
        CandidateProfile.user_id != p.user_id,
        CandidateProfile.specialization == p.specialization,
        (CandidateProfile.confirmed_grade == grade) | (CandidateProfile.claimed_grade == grade),
        CandidateProfile.salary_threshold.is_not(None))).all()
    values = [to_net(v, gn) for v, gn in rows]
    if len(values) < PARAMS.market_min_n:
        return None, len(values)
    return int(statistics.median(values)), len(values)
