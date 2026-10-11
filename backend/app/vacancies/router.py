import uuid

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.auth.models import User
from app.db.session import get_db
from app.vacancies import service
from app.vacancies.schemas import (
    AcceptedOut,
    AcceptIn,
    AppliedOut,
    ApplyIn,
    DeclineIn,
    EmployerApplicationOut,
    MyApplicationRowOut,
    VacancyIn,
    VacancyOut,
)

router = APIRouter(tags=["vacancies"])
employer = require_roles("employer")
candidate = require_roles("candidate")


@router.post("/employer/needs/{need_id}/vacancy", status_code=201, response_model=VacancyOut)
def publish(need_id: uuid.UUID, data: VacancyIn, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    return service.publish(db, user, need_id, data)


@router.get("/employer/vacancies", response_model=list[VacancyOut])
def company_vacancies(user: User = Depends(employer), db: Session = Depends(get_db)) -> list[dict]:
    return service.company_vacancies(db, user)


@router.post("/employer/vacancies/{vacancy_id}/close", response_model=VacancyOut)
def close(vacancy_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    return service.close(db, user, vacancy_id)


@router.get("/employer/vacancies/{vacancy_id}/applications", response_model=list[EmployerApplicationOut])
def applications(vacancy_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> list[dict]:
    return service.applications(db, user, vacancy_id)


@router.post("/employer/applications/{application_id}/accept", response_model=AcceptedOut)
def accept(application_id: uuid.UUID, data: AcceptIn | None = Body(default=None), user: User = Depends(employer),
           db: Session = Depends(get_db)) -> dict:
    return service.accept(db, user, application_id, data)


@router.post("/employer/applications/{application_id}/decline", response_model=AppliedOut)
def decline(application_id: uuid.UUID, data: DeclineIn, user: User = Depends(employer),
            db: Session = Depends(get_db)) -> dict:
    return service.decline(db, user, application_id, data)


@router.get("/candidate/vacancies", response_model=list[VacancyOut])
def vacancies(specialization: str | None = None, user: User = Depends(candidate),
              db: Session = Depends(get_db)) -> list[dict]:
    return service.open_vacancies(db, user, specialization)


@router.post("/candidate/vacancies/{vacancy_id}/apply", status_code=201, response_model=AppliedOut)
def apply(vacancy_id: uuid.UUID, data: ApplyIn, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return service.apply(db, user, vacancy_id, data)


@router.get("/candidate/applications", response_model=list[MyApplicationRowOut])
def my_applications(user: User = Depends(candidate), db: Session = Depends(get_db)) -> list[dict]:
    return service.my_applications(db, user)
