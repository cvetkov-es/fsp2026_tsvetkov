import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.auth.models import User
from app.candidates.pdf_profile import employer_view, render
from app.common.clock import MSK, now
from app.db.session import get_db
from app.employers.service import require_company
from app.llm.client import LLM
from app.llm.deps import get_llm
from app.matching import service
from app.matching.schemas import CellOut, MapOut, SelectionOut, SummaryOut
from app.matching.stack_dict import normalize_many
from app.matching.summary import candidate_card, summary

router = APIRouter(prefix="/employer", tags=["matching"])
employer = require_roles("employer")


def _split(v: str | None) -> tuple[str, ...]:
    return tuple(x.strip() for x in (v or "").split(",") if x.strip())


@router.get("/map", response_model=MapOut)
def get_map(user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    require_company(db, user)
    return {"cells": service.map_cells(db)}


@router.get("/map/{spec}/{grade}", response_model=CellOut)
def get_cell(spec: Literal["backend", "frontend", "data"], grade: Literal["junior", "middle", "senior"],
             user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    require_company(db, user)
    return {"items": service.cell(db, spec, grade)}


@router.get("/needs/{need_id}/selection", response_model=SelectionOut)
def get_selection(need_id: uuid.UUID, techs: str | None = Query(None), skills: str | None = Query(None),
                  has_fsp: bool = False, formats: str | None = Query(None),
                  user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    known, _ = normalize_many(_split(techs))
    flt = service.Filters(tuple(known), _split(skills), has_fsp, _split(formats))
    return service.selection(db, user, need_id, flt)


@router.put("/needs/{need_id}/shortlist/{ref}", status_code=204)
def put_pin(need_id: uuid.UUID, ref: str, user: User = Depends(employer), db: Session = Depends(get_db)) -> Response:
    service.pin(db, user, need_id, ref)
    return Response(status_code=204)


@router.delete("/needs/{need_id}/shortlist/{ref}", status_code=204)
def delete_pin(need_id: uuid.UUID, ref: str, user: User = Depends(employer), db: Session = Depends(get_db)) -> Response:
    service.unpin(db, user, need_id, ref)
    return Response(status_code=204)


@router.get("/needs/{need_id}/candidates/{ref}/summary", response_model=SummaryOut)
def get_summary(need_id: uuid.UUID, ref: str, user: User = Depends(employer), db: Session = Depends(get_db),
                llm: LLM = Depends(get_llm)) -> dict:
    return summary(db, user, need_id, ref, llm)


@router.get("/needs/{need_id}/candidates/{ref}/pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def get_candidate_pdf(need_id: uuid.UUID, ref: str, user: User = Depends(employer),
                      db: Session = Depends(get_db)) -> Response:
    card, _, need_title = candidate_card(db, user, need_id, ref)
    pdf = render(employer_view(card, need_title, f"{now().astimezone(MSK):%d.%m.%Y}"))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{card["alias"]}.pdf"'})
