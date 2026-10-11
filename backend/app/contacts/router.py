import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.deps import current_user, require_roles
from app.auth.models import User
from app.candidates.models import CandidateProfile
from app.contacts import service
from app.contacts.models import Contact
from app.contacts.schemas import (
    AcceptIn,
    CompanyBrief,
    ContactOut,
    CounterIn,
    CounterResponseIn,
    DeclineIn,
    EmployerInvitationOut,
    InvitationOut,
    InviteDraftOut,
    InviteIn,
    MessageIn,
    MessageOut,
    QuotaOut,
)
from app.db.session import get_db
from app.employers.models import Company, Need
from app.employers.service import get_need, require_company
from app.groups.service import group_brief
from app.matching.scoring import to_net
from app.matching.service import alias

router = APIRouter(tags=["contacts"])
employer = require_roles("employer")
candidate = require_roles("candidate")


def invitation_out(db: Session, c: Contact) -> dict:
    return {"id": str(c.id), "status": c.status, "version": c.version,
            "company": service.company_brief(db.get(Company, c.company_id)), "need_title": db.get(Need, c.need_id).title,
            "salary_from": c.salary_from, "salary_to": c.salary_to, "gross_net": c.gross_net,
            "salary_to_net": to_net(c.salary_to, c.gross_net), "description": c.description, "why_you": c.why_you,
            "next_step": c.next_step, "contact_method": c.contact_method, "expires_at": c.expires_at,
            "counter_amount": c.counter_amount, "counter_expires_at": c.counter_expires_at,
            "created_at": c.created_at, "chat_open": service.chat_open(db, c), "hours_per_week": c.hours_per_week,
            "group": group_brief(db, c)}


def employer_out(db: Session, c: Contact, p: CandidateProfile) -> dict:
    return {"id": str(c.id), "status": c.status, "version": c.version, "ref": p.public_ref, "alias": alias(p),
            "salary_from": c.salary_from, "salary_to": c.salary_to, "gross_net": c.gross_net,
            "expires_at": c.expires_at, "counter_amount": c.counter_amount, "counter_comment": c.counter_comment,
            "counter_expires_at": c.counter_expires_at, "decline_reason": service.decline_title(c.decline_reason),
            "created_at": c.created_at, "chat_open": service.chat_open(db, c), "viewed": c.viewed_at is not None,
            "hours_per_week": c.hours_per_week}


# --- работодатель

@router.get("/employer/needs/{need_id}/invitations/draft", response_model=InviteDraftOut)
def invite_draft(need_id: uuid.UUID, ref: str = Query(min_length=4, max_length=12), user: User = Depends(employer),
                 db: Session = Depends(get_db)) -> dict:
    return service.invite_draft(db, user, need_id, ref)


@router.post("/employer/needs/{need_id}/invitations", status_code=201, response_model=EmployerInvitationOut)
def send_invitation(need_id: uuid.UUID, data: InviteIn, user: User = Depends(employer),
                    db: Session = Depends(get_db)) -> dict:
    c = service.invite(db, user, need_id, data)
    return employer_out(db, c, db.get(CandidateProfile, c.user_id))


@router.get("/employer/needs/{need_id}/invitations", response_model=list[EmployerInvitationOut])
def need_invitations(need_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> list:
    return [employer_out(db, c, p) for c, p in service.need_invitations(db, user, need_id)]


@router.get("/employer/needs/{need_id}/quota", response_model=QuotaOut)
def need_quota(need_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    used, limit = service.quota(db, get_need(db, user, need_id), require_company(db, user))
    db.commit()
    return {"used": used, "limit": limit}


@router.post("/employer/invitations/{contact_id}/counter-response", response_model=EmployerInvitationOut)
def counter_response(contact_id: uuid.UUID, data: CounterResponseIn, user: User = Depends(employer),
                     db: Session = Depends(get_db)) -> dict:
    c = service.respond_counter(db, user, contact_id, data)
    return employer_out(db, c, db.get(CandidateProfile, c.user_id))


@router.post("/employer/invitations/{contact_id}/withdraw", response_model=EmployerInvitationOut)
def withdraw(contact_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    c = service.withdraw(db, user, contact_id)
    return employer_out(db, c, db.get(CandidateProfile, c.user_id))


# --- кандидат

@router.get("/candidate/invitations", response_model=list[InvitationOut])
def my_invitations(user: User = Depends(candidate), db: Session = Depends(get_db)) -> list:
    return [invitation_out(db, c) for c in service.my_invitations(db, user)]


@router.get("/candidate/invitations/{contact_id}", response_model=InvitationOut)
def view_invitation(contact_id: uuid.UUID, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return invitation_out(db, service.view(db, user, contact_id))


@router.post("/candidate/invitations/{contact_id}/accept", response_model=InvitationOut)
def accept(contact_id: uuid.UUID, data: AcceptIn, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return invitation_out(db, service.accept(db, user, contact_id, data))


@router.post("/candidate/invitations/{contact_id}/decline", response_model=InvitationOut)
def decline(contact_id: uuid.UUID, data: DeclineIn, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return invitation_out(db, service.decline(db, user, contact_id, data))


@router.post("/candidate/invitations/{contact_id}/counter", response_model=InvitationOut)
def counter(contact_id: uuid.UUID, data: CounterIn, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return invitation_out(db, service.counter(db, user, contact_id, data))


@router.post("/candidate/invitations/{contact_id}/revoke", response_model=InvitationOut)
def revoke(contact_id: uuid.UUID, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return invitation_out(db, service.revoke(db, user, contact_id))


@router.get("/candidate/blocks", response_model=list[CompanyBrief])
def blocks(user: User = Depends(candidate), db: Session = Depends(get_db)) -> list:
    return [service.company_brief(c) for c in service.blocked_companies(db, user)]


@router.put("/candidate/blocks/{company_id}", status_code=204)
def block(company_id: uuid.UUID, user: User = Depends(candidate), db: Session = Depends(get_db)) -> Response:
    service.block(db, user, company_id)
    return Response(status_code=204)


@router.delete("/candidate/blocks/{company_id}", status_code=204)
def unblock(company_id: uuid.UUID, user: User = Depends(candidate), db: Session = Depends(get_db)) -> Response:
    service.unblock(db, user, company_id)
    return Response(status_code=204)


# --- обе стороны

@router.get("/contacts/{contact_id}", response_model=ContactOut)
def contact_page(contact_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return service.contact_page(db, user, contact_id)


@router.get("/contacts/{contact_id}/messages", response_model=list[MessageOut])
def contact_messages(contact_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list:
    return service.contact_messages(db, user, contact_id)


@router.post("/contacts/{contact_id}/messages", status_code=201, response_model=MessageOut)
def post_message(contact_id: uuid.UUID, data: MessageIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> dict:
    return service.post_message(db, user, contact_id, data.text)
