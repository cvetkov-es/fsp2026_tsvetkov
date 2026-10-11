import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import current_user, require_roles
from app.auth.models import User
from app.db.session import get_db
from app.employers import service
from app.employers.need_parse import NeedDraft, NeedTextIn, parse_need_text
from app.employers.schemas import CompanyIn, CompanyOut, NeedIn, NeedOut
from app.llm.client import LLM
from app.llm.deps import get_llm
from app.matching.stack_dict import TECHS
from app.trust.service import l3_pending

router = APIRouter(tags=["employer"])
employer = require_roles("employer")


def company_out(c, l3_pending: bool = False) -> CompanyOut:
    return CompanyOut(id=str(c.id), name=c.name, description=c.description, industry=c.industry,
                      contacts=c.contacts or {}, trust_level=c.trust_level, domain=c.domain, legal_name=c.legal_name,
                      l3_pending=l3_pending)


def need_out(n) -> NeedOut:
    return NeedOut(id=str(n.id), status=n.status, title=n.title, specialization=n.specialization,
                   grades=n.grades, must=n.must, nice=n.nice, formats=n.formats, city=n.city,
                   salary_from=n.salary_from, salary_to=n.salary_to, gross_net=n.gross_net,
                   contact_method=n.contact_method, raw_text=n.raw_text, employment=n.employment)


@router.get("/employer/company", response_model=CompanyOut | None)
def get_company(user: User = Depends(employer), db: Session = Depends(get_db)):
    c = service.employer_company(db, user)
    return company_out(c, l3_pending(db, c)) if c else None


@router.put("/employer/company", response_model=CompanyOut)
def put_company(data: CompanyIn, user: User = Depends(employer), db: Session = Depends(get_db)):
    return company_out(service.upsert_company(db, user, data))


@router.get("/employer/needs", response_model=list[NeedOut])
def list_needs(user: User = Depends(employer), db: Session = Depends(get_db)):
    return [need_out(n) for n in service.list_needs(db, user)]


@router.post("/employer/needs", status_code=201, response_model=NeedOut)
def create_need(data: NeedIn, user: User = Depends(employer), db: Session = Depends(get_db)):
    return need_out(service.create_need(db, user, data))


@router.post("/employer/needs/parse", response_model=NeedDraft)
def parse_need(data: NeedTextIn, user: User = Depends(employer), db: Session = Depends(get_db),
               llm: LLM = Depends(get_llm)) -> NeedDraft:
    """Черновик формы из текста вакансии. Ничего не сохраняет: работодатель проверяет поля и сохраняет форму."""
    service.require_company(db, user)
    return parse_need_text(data.text, llm)


@router.get("/employer/needs/{need_id}", response_model=NeedOut)
def get_need(need_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)):
    return need_out(service.get_need(db, user, need_id))


@router.put("/employer/needs/{need_id}", response_model=NeedOut)
def update_need(need_id: uuid.UUID, data: NeedIn, user: User = Depends(employer), db: Session = Depends(get_db)):
    return need_out(service.update_need(db, user, need_id, data))


@router.post("/employer/needs/{need_id}/close", response_model=NeedOut)
def close_need(need_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)):
    return need_out(service.close_need(db, user, need_id))


@router.get("/stack/dictionary", tags=["stack"])
def stack_dictionary(_: User = Depends(current_user)) -> list[dict]:
    return [{"canonical": t.canonical, "category": t.category, "synonyms": list(t.synonyms)} for t in TECHS.values()]
