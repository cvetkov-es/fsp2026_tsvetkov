"""Спрос как обратная связь (процесс 2.9): агрегат при ≥ DEMAND_MIN_EMPLOYERS компаниях, с задержкой DEMAND_DELAY."""
from collections import Counter
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assessment.phrases import GRADE_TITLES
from app.assessment.skills import SKILLS
from app.auth.models import User
from app.candidates.service import get_or_create_profile, passed_skills, stack_states
from app.common.clock import now
from app.config.params import PARAMS
from app.employers.models import Need
from app.hiring.votes import status_grade
from app.matching.stack_dict import SKILL_TECHS

SPEC_TITLES = {"backend": "Backend", "frontend": "Frontend", "data": "Data / Analytics"}
TOP = 5
TECH_SKILL = {t: code for code, techs in SKILL_TECHS.items() if code in SKILLS for t in techs}


def demand_for(db: Session, user: User) -> dict:
    p = get_or_create_profile(db, user)
    grade = status_grade(p)
    base = {"category": None, "enough": False, "companies": None, "min_companies": PARAMS.demand_min_employers,
            "window_days": PARAMS.demand_window_days, "top": [], "skills": []}
    if not p.specialization or not grade:
        return base
    base["category"] = f"{SPEC_TITLES.get(p.specialization, p.specialization)} · {GRADE_TITLES[grade]}"
    t = now()
    latest = t - timedelta(days=PARAMS.demand_delay_days)
    earliest = latest - timedelta(days=PARAMS.demand_window_days)
    needs = [n for n in db.scalars(select(Need).where(
        Need.status == "active", Need.specialization == p.specialization,
        Need.created_at <= latest, Need.created_at > earliest)) if grade in n.grades]
    companies = len({n.company_id for n in needs})
    if companies < PARAMS.demand_min_employers:
        return base
    counts = Counter(tech for n in needs for tech in set(n.must) | set(n.nice))
    states = stack_states(db, p)
    top = [{"tech": tech, "share": round(c / len(needs), 2), "state": states.get(tech, "missing"),
            "skill": TECH_SKILL.get(tech)} for tech, c in counts.most_common(TOP)]
    passed = passed_skills(db, user.id)
    skills: dict[str, float] = {}
    for x in top:
        if x["skill"] and x["state"] != "confirmed" and x["skill"] not in passed:
            skills[x["skill"]] = max(skills.get(x["skill"], 0.0), x["share"])
    return base | {"enough": True, "companies": companies, "top": top,
                   "skills": [{"code": c, "title": SKILLS[c].title, "share": s}
                              for c, s in sorted(skills.items(), key=lambda kv: -kv[1])]}
