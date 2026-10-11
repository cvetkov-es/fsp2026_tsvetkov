import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.auth.models import User
from app.db.session import get_db
from app.initiative import demand, signals
from app.initiative.schemas import CompaniesOut, DemandOut, InterestOut, SignalOut

router = APIRouter(tags=["initiative"])
candidate = require_roles("candidate")
employer = require_roles("employer")


@router.get("/candidate/companies", response_model=CompaniesOut)
def companies(user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return signals.companies_for_candidate(db, user)


@router.post("/candidate/companies/{company_id}/signal", status_code=201, response_model=SignalOut)
def send(company_id: uuid.UUID, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return signals.send_signal(db, user, company_id)


@router.delete("/candidate/signals/{signal_id}", response_model=SignalOut)
def withdraw(signal_id: uuid.UUID, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return signals.withdraw_signal(db, user, signal_id)


@router.get("/employer/interest", response_model=list[InterestOut])
def interest(user: User = Depends(employer), db: Session = Depends(get_db)) -> list[dict]:
    return signals.company_interest(db, user)


@router.get("/candidate/demand", response_model=DemandOut)
def candidate_demand(user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return demand.demand_for(db, user)
