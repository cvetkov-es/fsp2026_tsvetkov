from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy.orm import Session

from app.assessment.bank.base import families
from app.assessment.bank.families import load_all
from app.assessment.models import Attempt
from app.assessment.service import ensure_no_active_attempt
from app.auth.deps import require_roles
from app.auth.models import User
from app.candidates.pdf_profile import candidate_view, render
from app.candidates.resume.service import ResumeDraft, build_draft
from app.candidates.schemas import (
    DetailsIn,
    DetailsOut,
    MarketOut,
    OpenWindowOut,
    ProfileOut,
    StackIn,
    StackOut,
    SurveyIn,
)
from app.candidates.service import (
    GRADE_INFO,
    SPECIALIZATIONS,
    declared_techs,
    get_or_create_profile,
    market_median,
    open_window,
    set_stack,
    stack_states,
    update_details,
    update_survey,
)
from app.config.params import PARAMS
from app.db.session import get_db
from app.llm.client import LLM
from app.llm.deps import get_llm
from app.moderation import service as moderation
from app.moderation.schemas import MyCaseOut

router = APIRouter(prefix="/candidate", tags=["candidate"])
candidate = require_roles("candidate")


def _out(db: Session, p) -> ProfileOut:
    status = db.get(Attempt, p.status_attempt_id) if p.status_attempt_id else None
    return ProfileOut(specialization=p.specialization, claimed_grade=p.claimed_grade,
                      grade_status=p.grade_status, confirmed_grade=p.confirmed_grade,
                      status_grade=status.target_grade if status else None)


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(candidate), db: Session = Depends(get_db)) -> ProfileOut:
    p = get_or_create_profile(db, user)
    db.commit()
    return _out(db, p)


@router.put("/profile/survey", response_model=ProfileOut)
def put_survey(data: SurveyIn, user: User = Depends(candidate), db: Session = Depends(get_db)) -> ProfileOut:
    p = get_or_create_profile(db, user)
    if p.specialization and p.specialization != data.specialization:
        ensure_no_active_attempt(db, user)
    return _out(db, update_survey(db, user, data.specialization, data.claimed_grade))


@router.get("/meta")
def meta(_: User = Depends(candidate)) -> dict:
    load_all()
    return {
        # test_available: в банке есть семейства — иначе тест по направлению ещё не открыт
        "specializations": [{"code": c, "title": t, "test_available": bool(families(c))}
                            for c, t in SPECIALIZATIONS.items()],
        "grades": [{"code": c, "title": t, "description": d} for c, (t, d) in GRADE_INFO.items()],
    }


def _details(p) -> DetailsOut:
    return DetailsOut(full_name=p.full_name, contacts=p.contacts or {}, experience_years=p.experience_years,
                      formats=p.formats or [], city=p.city, domains=p.domains or [],
                      salary_threshold=p.salary_threshold, salary_gross_net=p.salary_gross_net,
                      open_until=p.open_until)


@router.get("/cases", response_model=list[MyCaseOut])
def my_cases(user: User = Depends(candidate), db: Session = Depends(get_db)) -> list[dict]:
    """«Мои обращения»: споры, жалобы, возражения по ст. 16 с итогом и текстом модератора."""
    return moderation.my_cases(db, user)


@router.get("/profile/details", response_model=DetailsOut)
def get_details(user: User = Depends(candidate), db: Session = Depends(get_db)) -> DetailsOut:
    p = get_or_create_profile(db, user)
    db.commit()
    return _details(p)


@router.put("/profile/details", response_model=DetailsOut)
def put_details(data: DetailsIn, user: User = Depends(candidate), db: Session = Depends(get_db)) -> DetailsOut:
    return _details(update_details(db, user, data))


def _stack_out(db, p, unknown=()) -> dict:
    return {"items": [{"tech": t, "state": s} for t, s in sorted(stack_states(db, p).items())],
            "declared": declared_techs(db, p.user_id), "unknown": list(unknown)}


@router.get("/profile/stack", response_model=StackOut)
def get_stack(user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return _stack_out(db, get_or_create_profile(db, user))


@router.put("/profile/stack", response_model=StackOut)
def put_stack(data: StackIn, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    p, unknown = set_stack(db, user, data.techs)
    return _stack_out(db, p, unknown)


@router.post("/profile/open-window", response_model=OpenWindowOut)
def post_open_window(user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return {"open_until": open_window(db, user).open_until}


@router.get("/market", response_model=MarketOut)
def market(user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    median, n = market_median(db, get_or_create_profile(db, user))
    return {"median_net": median, "n": n}


@router.post("/profile/resume", response_model=ResumeDraft)
def upload_resume(file: UploadFile, _: User = Depends(candidate), llm: LLM = Depends(get_llm)) -> ResumeDraft:
    """Черновик профиля из PDF. Ничего не сохраняет: кандидат проверяет черновик и сохраняет форму сам."""
    return build_draft(file.file.read(PARAMS.resume_max_mb * 1024 * 1024 + 1), llm)


@router.get("/profile/pdf", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def profile_pdf(user: User = Depends(candidate), db: Session = Depends(get_db)) -> Response:
    pdf = render(candidate_view(db, user))
    db.commit()
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="profile.pdf"'})
