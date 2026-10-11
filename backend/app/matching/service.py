"""Сборка фактов из БД с учётом согласия на распространение и вызов чистого ядра."""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.assessment.models import Attempt
from app.assessment.phrases import GRADE_TITLES
from app.auth.models import Consent, User
from app.candidates.models import CandidateProfile, CandidateStack, SkillResult
from app.candidates.service import confirmed_techs
from app.common.clock import now
from app.common.errors import AppError
from app.contacts.models import Contact, effective_status
from app.employers.models import Need
from app.employers.service import get_need
from app.hiring.votes import VoteStats, holder, vote_stats
from app.junior.rules import age_of, is_minor_age
from app.matching.explain import NO_FSP, counterfactuals, explain, interview_suffix
from app.matching.models import SearchLog, SelectionSnapshot, Shortlist
from app.matching.scoring import (
    CandidateFacts,
    NeedFacts,
    Ranked,
    cell_rank,
    evaluate_candidate,
    rank,
    strength_r,
    to_net,
)
from app.matching.stack_dict import expand

SPEC_LETTER = {"backend": "B", "frontend": "F", "data": "D"}
GRADE_LETTER = {"junior": "J", "middle": "M", "senior": "S"}
BLOCK_TITLES = {2: "Соседние грейды", 3: "Не подтвердили грейд", 4: "Почти подходят"}
FILTER_LABELS = {"techs": "технологии", "skills": "навыки", "has_fsp": "есть достижения ФСП", "formats": "формат"}


@dataclass
class Row:
    facts: CandidateFacts
    profile: CandidateProfile
    visible: dict[str, bool]
    skills: list[str]


def alias(p: CandidateProfile) -> str:
    grade = p.confirmed_grade or p.claimed_grade or "middle"
    return f"{SPEC_LETTER.get(p.specialization, 'X')}-{GRADE_LETTER[grade]}-{p.public_ref[:4].upper()}"


def load_rows(db: Session, specialization: str | None = None, company_id=None, user_ids=None) -> list[Row]:
    # импорт внутри функции: initiative.signals импортирует matching.service
    from app.initiative.signals import active_signal_users

    signaled = active_signal_users(db, company_id, now()) if company_id else set()
    stmt = (select(CandidateProfile, Attempt.decided_at, Attempt.express)
            .outerjoin(Attempt, Attempt.id == CandidateProfile.status_attempt_id)
            .where(CandidateProfile.grade_status.in_(("confirmed", "not_confirmed"))))
    if specialization:
        stmt = stmt.where(CandidateProfile.specialization == specialization)
    if user_ids is not None:
        stmt = stmt.where(CandidateProfile.user_id.in_(user_ids))
    data = db.execute(stmt).all()
    ids = [p.user_id for p, _, _ in data]
    born = {uid: (bd, by) for uid, bd, by in db.execute(select(User.id, User.birth_date, User.birth_year).where(User.id.in_(ids)))}
    today = now().date()
    # По возрастанию времени: при нескольких активных согласиях побеждает последнее (смена пресета)
    consents = {c.user_id: c for c in db.scalars(select(Consent).where(
        Consent.user_id.in_(ids), Consent.type == "distribution", Consent.revoked_at.is_(None))
        .order_by(Consent.granted_at))}
    stacks: dict = {}
    for s in db.scalars(select(CandidateStack).where(CandidateStack.user_id.in_(ids))):
        stacks.setdefault(s.user_id, set()).add(s.tech)
    skills: dict = {}
    for s in db.scalars(select(SkillResult).where(SkillResult.user_id.in_(ids), SkillResult.passed.is_(True))):
        skills.setdefault(s.user_id, set()).add(s.skill_code)
    # Голоса — при чтении (ленивые статусы): вступление в силу не ждёт worker
    votes = vote_stats(db, {p.user_id: holder(p) for p, _, _ in data}, now())
    rows = []
    for p, decided_at, express in data:
        consent = consents.get(p.user_id)
        if consent is None:
            continue
        minor = is_minor_age(age_of(*born.get(p.user_id, (None, None)), today))
        if minor and p.guardian_consent_at is None:  # профиль несовершеннолетнего — черновик до согласия представителя
            continue
        fields = (consent.scope or {}).get("fields", {})
        vis = {k: fields.get(k) == "allow" for k in ("city", "fsp_achievements", "stack", "experience",
                                                     "work_format", "skills")}
        passed = skills.get(p.user_id, set()) if vis["skills"] else set()
        vs = votes.get(p.user_id, VoteStats())
        conf = confirmed_techs(p.specialization, p.grade_status == "confirmed", passed)
        declared = stacks.get(p.user_id, set())
        states = {t: ("confirmed" if t in conf else "declared") for t in declared} if vis["stack"] else {}
        if vis["stack"]:
            states.update({t: "confirmed" for t in conf})
        facts = CandidateFacts(
            ref=p.public_ref, specialization=p.specialization, grade_status=p.grade_status,
            confirmed_grade=p.confirmed_grade, claimed_grade=p.claimed_grade, theta=p.theta or 0.0,
            se=p.se or 1.0, s=p.s_cache or 0.0, fsp_f=p.fsp_f or 0.0,
            fsp_visible=vis["fsp_achievements"] and p.fsp_status not in ("NOT_LINKED", "CONSENT_REVOKED"),
            m=vs.m, interview_positive=vs.positive,
            interview_badge=vs.badge(), stack=expand(states), stack_declared=bool(declared),
            formats=tuple(p.formats or ()) if vis["work_format"] else (),
            city=p.city if vis["city"] else None, salary_threshold_net=to_net(p.salary_threshold, p.salary_gross_net),
            open_until=p.open_until, last_activity_at=p.last_activity_at, confirmed_at=decided_at,
            express=bool(express), signal_to_company=p.user_id in signaled, minor=minor)
        rows.append(Row(facts, p, vis, sorted(passed)))
    return rows


def need_facts(n: Need) -> NeedFacts:
    return NeedFacts(n.specialization, tuple(n.grades), tuple(n.must), tuple(n.nice), tuple(n.formats),
                     to_net(n.salary_to, n.gross_net), n.employment)


def _percentiles(rows: list[Row]) -> dict[str, int]:
    """«Сильнее N% категории» — только среди подтвердивших тот же грейд: не подтвердившие не завышают N."""
    confirmed = [r for r in rows if r.facts.grade_status == "confirmed"]
    by_cell: dict = {}
    for r in confirmed:
        by_cell.setdefault((r.facts.specialization, r.facts.confirmed_grade), []).append(strength_r(r.facts))
    out = {}
    for r in confirmed:
        vals = by_cell[(r.facts.specialization, r.facts.confirmed_grade)]
        mine = strength_r(r.facts)
        out[r.facts.ref] = round(100 * sum(1 for v in vals if v < mine) / (len(vals) - 1)) if len(vals) > 1 else None
    return out


def card(row: Row, ranked: Ranked | None, need: NeedFacts | None, pct: int | None,
         cf: str | None = None, pinned: bool = False, mismatch: str | None = None) -> dict:
    f, p = row.facts, row.profile
    grade = f.confirmed_grade or f.claimed_grade
    out = {"ref": f.ref, "alias": alias(p), "grade": grade, "grade_status": f.grade_status,
           "block": ranked.block if ranked else None, "stack": [{"tech": t, "state": s} for t, s in sorted(f.stack.items())],
           "skills": row.skills, "experience_years": p.experience_years if row.visible["experience"] else None,
           "formats": list(f.formats), "city": f.city, "conflicts": list(ranked.conflicts) if ranked else [],
           "pinned": pinned, "express": f.express, "filter_mismatch": mismatch,
           "interview_badge": f"Подтверждено на собеседованиях ({f.interview_positive})" if f.interview_badge else None,
           "signal": f.signal_to_company, "minor": f.minor}
    if ranked and need:
        e = explain(ranked, need, pct, p.fsp_summary)
        out.update(fit_level=e.fit_level, readiness={"level": e.readiness_level, "tooltip": e.readiness_tooltip},
                   explanation={"lines": list(e.lines), "missing": list(e.missing), "counterfactual": cf})
    else:
        fsp = p.fsp_summary if f.fsp_visible and p.fsp_summary else NO_FSP
        line1 = (f"{GRADE_TITLES[grade]} подтверждён тестом" if f.grade_status == "confirmed"
                 else f"{GRADE_TITLES[grade]} заявлен, тест не подтвердил")
        if pct is not None and f.grade_status == "confirmed":
            line1 += f" · сильнее {pct}% категории"
        line1 += interview_suffix(f)
        out.update(fit_level=None, readiness=None,
                   explanation={"lines": [line1, "Стек: " + (", ".join(sorted(f.stack)[:6]) or "не указан"), fsp],
                                "missing": [], "counterfactual": None})
    return out


@dataclass(frozen=True)
class Filters:
    techs: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    has_fsp: bool = False
    formats: tuple[str, ...] = ()

    def active(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v}

    def without(self, key: str) -> "Filters":
        return Filters(**{**self.__dict__, key: (False if key == "has_fsp" else ())})


def mismatch_reason(row: Row, flt: Filters) -> str | None:
    f = row.facts
    missing = [t for t in flt.techs if t not in f.stack]
    if missing:
        return "не проходит: нет " + ", ".join(missing)
    if [s for s in flt.skills if s not in row.skills]:
        return "не проходит: навыки не подтверждены"
    if flt.has_fsp and not (f.fsp_visible and f.fsp_f > 0):
        return "не проходит: нет достижений ФСП"
    if flt.formats and not set(flt.formats) & set(f.formats):
        return "не проходит: формат"
    return None


def _previous_refs(db: Session, need_id) -> list[str] | None:
    snap = db.get(SelectionSnapshot, need_id)
    return list(snap.refs) if snap else None


def selection(db: Session, user: User, need_id, flt: Filters) -> dict:
    n = get_need(db, user, need_id)
    need = need_facts(n)
    rows = load_rows(db, n.specialization, n.company_id)
    pct = _percentiles(rows)
    t = now()
    by_ref = {r.facts.ref: r for r in rows}

    def run(fl: Filters) -> list[Ranked]:
        return rank((r.facts for r in rows if mismatch_reason(r, fl) is None), need, t)

    ranked = run(flt)
    cfs = counterfactuals(ranked, need, t)
    pinned = {uid for uid in db.scalars(select(Shortlist.user_id).where(Shortlist.need_id == n.id))}
    statuses = {c.user_id: effective_status(c, t)
                for c in db.scalars(select(Contact).where(Contact.need_id == n.id).order_by(Contact.created_at))}
    blocks: dict[int, list] = {}
    for i, rk in enumerate(ranked):
        row = by_ref[rk.c.ref]
        blocks.setdefault(rk.block, []).append(
            card(row, rk, need, pct.get(rk.c.ref), cfs[i],
                 pinned=row.profile.user_id in pinned) | {"contact_status": statuses.get(row.profile.user_id)})
    grades_title = ", ".join(GRADE_TITLES[g] for g in n.grades)
    out_blocks = [{"block": b, "title": f"Подтверждённые: {grades_title}" if b == 1 else BLOCK_TITLES[b],
                   "items": items} for b, items in sorted(blocks.items())]
    shortlist = []
    for row in rows:
        if row.profile.user_id in pinned:
            rk = evaluate_candidate(row.facts, need, t)
            shortlist.append(card(row, rk, need, pct.get(row.facts.ref), pinned=True,
                                  mismatch=mismatch_reason(row, flt))
                             | {"contact_status": statuses.get(row.profile.user_id)})
    current = [rk.c.ref for rk in ranked if rk.block <= 3]
    prev_refs = _previous_refs(db, n.id)
    prev = prev_refs or []
    removed = [{"ref": ref, "alias": alias(by_ref[ref].profile),
                "reason": mismatch_reason(by_ref[ref], flt) or "больше не проходит по условиям потребности"}
               for ref in prev if ref not in current and ref in by_ref]
    # Первое открытие — сравнивать не с чем, диф не показываем
    diff = None if prev_refs is None else {"added": len([r for r in current if r not in prev]), "removed": removed}
    # upsert: два параллельных первых открытия (две вкладки, несколько воркеров) не падают на PK
    ins = pg_insert(SelectionSnapshot).values(need_id=n.id, refs=current, at=t)
    db.execute(ins.on_conflict_do_update(index_elements=[SelectionSnapshot.need_id],
                                         set_={"refs": ins.excluded.refs, "at": ins.excluded.at}))
    suggestions = []
    if not current:
        for key in flt.active():
            gain = len([rk for rk in run(flt.without(key)) if rk.block <= 3])
            if gain:
                suggestions.append({"filter": key, "label": f"снять «{FILTER_LABELS[key]}»", "gain": gain})
    db.add(SearchLog(need_id=n.id, company_id=n.company_id,
                     filters={k: list(v) if isinstance(v, tuple) else v for k, v in flt.active().items()}))
    db.commit()
    # «Вилка в ожиданиях у X из Y» (процесс 4.4): агрегат по всей подборке без раскрытия самих порогов
    with_threshold = [rk for rk in ranked if rk.c.salary_threshold_net]
    fork_fit = {"fit": sum(1 for rk in with_threshold if need.salary_to_net >= rk.c.salary_threshold_net),
                "total": len(with_threshold)}
    return {"blocks": out_blocks, "shortlist": shortlist, "diff": diff, "suggestions": suggestions,
            "fork_fit": fork_fit}


def map_cells(db: Session) -> list[dict]:
    rows = load_rows(db)
    cells: dict = {}
    for r in rows:
        f = r.facts
        grade = f.confirmed_grade or f.claimed_grade
        cell = cells.setdefault((f.specialization, grade), {"specialization": f.specialization, "grade": grade,
                                                            "confirmed": 0, "unconfirmed": 0})
        cell["confirmed" if f.grade_status == "confirmed" else "unconfirmed"] += 1
    return sorted(cells.values(), key=lambda c: (c["specialization"], ["junior", "middle", "senior"].index(c["grade"])))


def cell(db: Session, spec: str, grade: str) -> list[dict]:
    rows = load_rows(db, spec)
    pct = _percentiles(rows)
    by_ref = {r.facts.ref: r for r in rows}
    return [card(by_ref[f.ref], None, None, pct.get(f.ref)) for f in cell_rank((r.facts for r in rows), grade)]


def _profile_by_ref(db: Session, ref: str) -> CandidateProfile:
    p = db.scalar(select(CandidateProfile).where(CandidateProfile.public_ref == ref))
    if p is None:
        raise AppError(404, "candidate_not_found", "Кандидат не найден")
    return p


def pin(db: Session, user: User, need_id, ref: str) -> None:
    n = get_need(db, user, need_id)
    p = _profile_by_ref(db, ref)
    if db.get(Shortlist, (n.id, p.user_id)) is None:
        db.add(Shortlist(need_id=n.id, user_id=p.user_id))
    db.commit()


def unpin(db: Session, user: User, need_id, ref: str) -> None:
    n = get_need(db, user, need_id)
    p = _profile_by_ref(db, ref)
    row = db.get(Shortlist, (n.id, p.user_id))
    if row:
        db.delete(row)
    db.commit()
