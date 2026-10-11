"""Мок ресурсного API достижений ФСП: GET /athletes/me/achievements (исследование 04, §3)."""
import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.mocks.fsp.fixtures import payload_for
from app.mocks.fsp.keys import bearer_claims

router = APIRouter(prefix="/api/v1")
SCOPE = "fsp:achievements.read"


@router.get("/athletes/me/achievements")
def achievements(response: Response, authorization: Annotated[str, Header()] = "",
                 db: Session = Depends(get_db)) -> dict:
    claims = bearer_claims(db, authorization)
    if SCOPE not in str(claims.get("scope", "")).split():
        raise HTTPException(403, f"Нужен scope {SCOPE}")
    payload = payload_for(claims["sub"])
    response.headers["ETag"] = '"' + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16] + '"'
    return payload
