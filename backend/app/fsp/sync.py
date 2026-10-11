"""Синхронизация достижений: API ФСП → снимок → fsp_results / fsp_ranks → f и статус профиля (процесс 2.7)."""
import logging
import uuid
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.models import ExternalIdentity, User
from app.candidates.models import CandidateProfile
from app.common.clock import now
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.fsp.http import server_url
from app.fsp.models import FspRank, FspResult, FspSnapshot, OidcPending, OidcState
from app.fsp.points import (
    DISCIPLINES,
    RANK_TITLES,
    TIER_TITLES,
    counted,
    not_counted_reason,
    parse,
    points,
    rank_valid,
    summary,
    tier,
)
from app.matching.scoring import fsp_f

log = logging.getLogger("fsp")
FSP_PROVIDER = "fsp_id"


def fetch_achievements(http: httpx.Client, access_token: str) -> dict:
    r = http.get(server_url(f"{get_settings().fsp_achievements_url}/athletes/me/achievements"),
                 headers={"Authorization": f"Bearer {access_token}"})
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("ответ API достижений — не объект")
    return data


def _profile(db: Session, user_id: uuid.UUID) -> CandidateProfile:
    p = db.get(CandidateProfile, user_id)
    if p is None:
        p = CandidateProfile(user_id=user_id)
        db.add(p)
        db.flush()
    return p


def _identity(db: Session, user_id: uuid.UUID) -> ExternalIdentity | None:
    return db.scalar(select(ExternalIdentity).where(ExternalIdentity.user_id == user_id,
                                                    ExternalIdentity.provider == FSP_PROVIDER))


def apply_snapshot(db: Session, user_id: uuid.UUID, payload: dict, today: date | None = None) -> CandidateProfile:
    today = today or now().date()
    results, ranks = parse(payload)
    snap = FspSnapshot(user_id=user_id, status="ok", payload=payload)
    db.add(snap)
    db.flush()
    db.execute(delete(FspResult).where(FspResult.user_id == user_id))
    db.execute(delete(FspRank).where(FspRank.user_id == user_id))
    db.add_all(FspResult(
        user_id=user_id, snapshot_id=snap.id, competition_id=r.competition_id, competition_title=r.competition_title,
        discipline=r.discipline, stage_type=r.stage_type, level=r.level, date=r.date, place=r.place,
        field_size=r.field_size, team_id=r.team_id, team_name=r.team_name, team_size=r.team_size, tier=tier(r),
        counted=counted(r), note=not_counted_reason(r)) for r in results)
    db.add_all(FspRank(user_id=user_id, rank=k.rank, assigned_at=k.assigned_at, valid_until=k.valid_until)
               for k in ranks)
    p = _profile(db, user_id)
    p.fsp_status = "LINKED" if results or ranks else "LINKED_EMPTY"
    p.fsp_f = fsp_f(points(results, ranks, today))
    p.fsp_summary = summary(results, ranks, today)
    if ident := _identity(db, user_id):
        ident.last_sync_at = now()
    return p


def sync(db: Session, http: httpx.Client, user_id: uuid.UUID, access_token: str) -> str:
    try:
        payload = fetch_achievements(http, access_token)
        parse(payload)  # формат проверяется до записи: битый ответ ФСП — тот же SYNC_STALE, а не 500
    except (httpx.HTTPError, ValueError) as e:
        log.warning("fsp sync failed for %s: %s", user_id, type(e).__name__)
        db.add(FspSnapshot(user_id=user_id, status="error", payload=None))
        p = _profile(db, user_id)
        p.fsp_status = "SYNC_STALE"  # fsp_results, f и строка — из последнего удачного снимка
        return p.fsp_status
    return apply_snapshot(db, user_id, payload).fsp_status


def unlink(db: Session, user: User) -> None:
    """Отвязка — это отзыв согласия: данные ФСП удаляются, f = 0, статус CONSENT_REVOKED (исследование 04, §3).

    У аккаунта без пароля FSP ID — единственный способ входа: связь остаётся, данные — нет. Повторный вход их не
    возвращает; вернуть можно только явной привязкой в профиле.
    """
    for model in (FspResult, FspRank, FspSnapshot):
        db.execute(delete(model).where(model.user_id == user.id))
    if ident := _identity(db, user.id):
        if user.password_hash:
            db.delete(ident)
        else:
            ident.last_sync_at = None
    p = _profile(db, user.id)
    p.fsp_status, p.fsp_f, p.fsp_summary = "CONSENT_REVOKED", 0.0, None
    audit(db, user.id, "fsp.unlink", "user", str(user.id))
    db.commit()


def fsp_view(db: Session, user: User) -> dict:
    """ФСП в кабинете кандидата (процесс 2.7): уровни, онлайн-отборы одной строкой, разряды со сроком."""
    p = _profile(db, user.id)
    today = now().date()
    rows = list(db.scalars(select(FspResult).where(FspResult.user_id == user.id)
                           .order_by(FspResult.date.desc(), FspResult.id)))
    ranks = list(db.scalars(select(FspRank).where(FspRank.user_id == user.id).order_by(FspRank.assigned_at.desc())))
    ident = _identity(db, user.id)
    online = [r for r in rows if r.tier == "online" and r.counted]
    db.commit()
    return {
        "status": p.fsp_status, "summary": p.fsp_summary, "last_sync_at": ident.last_sync_at if ident else None,
        "login_via_fsp": ident is not None and not user.password_hash,
        "results": [{"competition_title": r.competition_title, "discipline_title": DISCIPLINES.get(r.discipline, r.discipline),
                     "date": r.date, "place": r.place, "field_size": r.field_size, "tier": r.tier,
                     "tier_title": TIER_TITLES[r.tier], "team_name": r.team_name, "team_size": r.team_size,
                     "counted": r.counted, "note": r.note} for r in rows if not (r.tier == "online" and r.counted)],
        "online": {"count": len(online), "disciplines": len({r.discipline for r in online})},
        "ranks": [{"rank": k.rank, "title": RANK_TITLES.get(k.rank, k.rank), "valid_until": k.valid_until,
                   "valid": rank_valid(k.rank, k.valid_until, today)} for k in ranks],
    }


def purge_fsp_temp(db: Session, t: datetime) -> int:
    """Worker: state и «билеты» старше OIDC_TTL_MIN; снимки сверх FSP_SNAPSHOTS_KEEP, кроме того, на котором стоят
    fsp_results (иначе каскад удалил бы результаты при долгой недоступности ФСП)."""
    stale = t - timedelta(minutes=PARAMS.oidc_ttl_min)
    n = db.execute(delete(OidcState).where(OidcState.created_at < stale)).rowcount
    n += db.execute(delete(OidcPending).where(OidcPending.created_at < stale)).rowcount
    ranked = select(FspSnapshot.id, func.row_number().over(
        partition_by=FspSnapshot.user_id, order_by=FspSnapshot.fetched_at.desc()).label("rn")).subquery()
    n += db.execute(delete(FspSnapshot).where(
        FspSnapshot.id.in_(select(ranked.c.id).where(ranked.c.rn > PARAMS.fsp_snapshots_keep)),
        FspSnapshot.id.not_in(select(FspResult.snapshot_id)))).rowcount
    return n
