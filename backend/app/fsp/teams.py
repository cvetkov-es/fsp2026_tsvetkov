"""Найм команды целиком (процесс 4.5): призовые команды ФСП с ≥ TEAM_MIN_ON_PLATFORM участниками на платформе."""
from collections import defaultdict
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.params import PARAMS
from app.fsp.models import FspResult
from app.fsp.points import DISCIPLINES
from app.matching.service import alias, load_rows


def prize_teams(db: Session, specialization: str | None = None) -> list[dict]:
    rows = {r.profile.user_id: r for r in load_rows(db) if r.facts.fsp_visible}
    if len(rows) < PARAMS.team_min_on_platform:
        return []
    results = list(db.scalars(select(FspResult).where(FspResult.user_id.in_(rows), FspResult.team_id.is_not(None))))
    teams_of: dict = defaultdict(set)
    members: dict = defaultdict(set)
    best: dict = {}
    for r in results:
        teams_of[r.user_id].add(r.team_id)
        if r.counted and r.tier in ("winner", "prize"):
            members[r.team_id].add(r.user_id)
            best.setdefault(r.team_id, r)
    out = []
    for team_id, users in members.items():
        if len(users) < PARAMS.team_min_on_platform:
            continue
        ids = sorted(users, key=str)
        if specialization and not any(rows[u].facts.specialization == specialization for u in ids):
            continue
        pairs = list(combinations(ids, 2))
        r = best[team_id]
        out.append({
            "team_id": team_id, "team_name": r.team_name, "competition_title": r.competition_title,
            "discipline_title": DISCIPLINES.get(r.discipline, r.discipline), "date": r.date, "place": r.place,
            "field_size": r.field_size, "tier": r.tier, "team_size": r.team_size, "on_platform": len(ids),
            "cohesion": round(sum(len(teams_of[a] & teams_of[b]) for a, b in pairs) / len(pairs), 1),
            "members": [{"ref": rows[u].facts.ref, "alias": alias(rows[u].profile),
                         "specialization": rows[u].facts.specialization,
                         "grade": rows[u].facts.confirmed_grade or rows[u].facts.claimed_grade,
                         "grade_status": rows[u].facts.grade_status, "minor": rows[u].facts.minor} for u in ids],
        })
    return sorted(out, key=lambda t: (t["tier"] != "winner", t["place"] or 99, -t["on_platform"],
                                      -t["date"].toordinal()))
