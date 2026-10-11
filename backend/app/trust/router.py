import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.auth.models import User
from app.db.session import get_db
from app.employers.router import company_out
from app.employers.schemas import CompanyOut
from app.fsp.http import get_fsp_http
from app.trust import service

router = APIRouter(tags=["trust"])
employer = require_roles("employer")


class InnIn(BaseModel):
    inn: str = Field(min_length=10, max_length=14)


class L3In(BaseModel):
    comment: str = Field(default="", max_length=1000)


@router.post("/employer/company/verify-domain", response_model=CompanyOut)
def verify_domain(user: User = Depends(employer), db: Session = Depends(get_db)) -> CompanyOut:
    c = service.verify_domain(db, user)
    return company_out(c, service.l3_pending(db, c))


@router.post("/employer/company/verify-inn", response_model=CompanyOut)
def verify_inn(data: InnIn, user: User = Depends(employer), db: Session = Depends(get_db),
               http: httpx.Client = Depends(get_fsp_http)) -> CompanyOut:
    c = service.verify_inn(db, user, data.inn, http)
    return company_out(c, service.l3_pending(db, c))


@router.post("/employer/company/l3-request", response_model=CompanyOut)
def l3_request(data: L3In, user: User = Depends(employer), db: Session = Depends(get_db)) -> CompanyOut:
    c = service.request_l3(db, user, data.comment)
    return company_out(c, True)
