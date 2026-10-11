"""Баллы ФСП и строка для объяснения (процесс 6.2 и 2.7). Чистые функции без БД.

Σ = max(Σ результатов, баллы действующего разряда); f = 1 − exp(−Σ / FSP_SATURATION) — matching.scoring.fsp_f.
Онлайн-отборы — одна строка на дисциплину; командный результат — каждому участнику те же баллы.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.assessment.phrases import ru_plural
from app.config.params import PARAMS, Params

DISCIPLINES = {"algo": "алгоритмическое программирование", "product": "продуктовое программирование",
               "uas": "программирование БАС", "robotics": "программирование робототехники",
               "infosec": "программирование систем ИБ"}
TIER_TITLES = {"winner": "победа", "prize": "призовое место", "finalist": "финал", "online": "онлайн-отбор",
               "participant": "участие"}
RANK_TITLES = {"MS": "МС", "KMS": "КМС", "I": "I разряд", "II": "II разряд", "III": "III разряд"}
RANK_ORDER = ("MS", "KMS", "I", "II", "III")
NOT_COUNTED = {"PRELIMINARY": "предварительный протокол", "ANNULLED": "результат аннулирован",
               "DSQ": "дисквалификация", "DNS": "неявка", "OUT_OF_COMPETITION": "вне конкурса"}


@dataclass(frozen=True)
class FspRes:
    competition_id: str
    competition_title: str
    discipline: str
    stage_type: str  # QUALIFIER | FINAL | SUPERFINAL | SINGLE
    level: str
    date: date
    place: int | None
    field_size: int | None
    team_id: str | None
    team_name: str | None
    team_size: int | None
    status: str  # OK | DSQ | DNS | OUT_OF_COMPETITION
    protocol_status: str  # FINAL | PRELIMINARY | ANNULLED


@dataclass(frozen=True)
class FspRankRec:
    rank: str
    assigned_at: date
    valid_until: date | None


def parse(payload: dict) -> tuple[list[FspRes], list[FspRankRec]]:
    """Ответ API достижений → записи. Любое нарушение формата — ValueError: синхронизация уйдёт в SYNC_STALE."""
    try:
        return _parse(payload)
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"формат ответа API достижений: {type(e).__name__}") from e


def _parse(payload: dict) -> tuple[list[FspRes], list[FspRankRec]]:
    results = []
    for r in payload.get("results") or []:
        team = r.get("team") or {}
        results.append(FspRes(
            competition_id=str(r["competition_id"]), competition_title=str(r["competition_title"]),
            discipline=str(r["discipline"]), stage_type=str(r["stage_type"]), level=str(r.get("level") or ""),
            date=date.fromisoformat(r["date"]), place=r.get("place"), field_size=r.get("field_size"),
            team_id=team.get("id"), team_name=team.get("name"), team_size=team.get("size"),
            status=str(r.get("status") or "OK"), protocol_status=str(r.get("protocol_status") or "FINAL")))
    ranks = [FspRankRec(str(k["rank"]), date.fromisoformat(k["assigned_at"]),
                        date.fromisoformat(k["valid_until"]) if k.get("valid_until") else None)
             for k in payload.get("ranks") or []]
    return results, ranks


def counted(r: FspRes) -> bool:
    """В баллы — только итоговые протоколы и выступления без дисквалификации (исследование 04, §4)."""
    return r.status == "OK" and r.protocol_status == "FINAL"


def not_counted_reason(r: FspRes) -> str | None:
    if counted(r):
        return None
    return NOT_COUNTED.get(r.protocol_status if r.protocol_status != "FINAL" else r.status, "не засчитано")


def tier(r: FspRes) -> str:
    if r.stage_type == "QUALIFIER":
        return "online"
    if r.place == 1:
        return "winner"
    if r.place in (2, 3):
        return "prize"
    if r.stage_type in ("FINAL", "SUPERFINAL"):
        return "finalist"
    return "participant"


def rank_valid(rank: str, valid_until: date | None, today: date) -> bool:
    """МС — пожизненно, остальные разряды — до даты окончания (исследование 04, §1)."""
    return rank == "MS" or (valid_until is not None and valid_until >= today)


def points(results: Sequence[FspRes], ranks: Sequence[FspRankRec], today: date, params: Params = PARAMS) -> float:
    per_tier = {"winner": params.fsp_pts_win, "prize": params.fsp_pts_prize, "finalist": params.fsp_pts_final}
    done = [r for r in results if counted(r)]
    total = sum(per_tier.get(tier(r), 0.0) for r in done)
    total += params.fsp_pts_online * len({r.discipline for r in done if tier(r) == "online"})
    per_rank = {"MS": params.fsp_pts_rank_ms, "KMS": params.fsp_pts_rank_kms, "I": params.fsp_pts_rank_1}
    best = max((per_rank.get(k.rank, 0.0) for k in ranks if rank_valid(k.rank, k.valid_until, today)), default=0.0)
    return max(total, best)


def _starts(n: int) -> str:
    return f"{n} {ru_plural(n, 'старта', 'стартов', 'стартов')}"


def summary(results: Sequence[FspRes], ranks: Sequence[FspRankRec], today: date) -> str | None:
    """Строка для третьей строки объяснения (≤ 300 символов). Нет результатов и разрядов — None, не «0»."""
    done = [r for r in results if counted(r)]
    by_tier = {t: [r for r in done if tier(r) == t] for t in ("winner", "prize", "finalist", "online")}
    parts = [f"{word} {_starts(len(by_tier[t]))}"
             for t, word in (("winner", "победитель"), ("prize", "призёр"), ("finalist", "финалист")) if by_tier[t]]
    online = len({r.discipline for r in by_tier["online"]})
    if online:
        parts.append(f"онлайн-отборы в {online} {ru_plural(online, 'дисциплине', 'дисциплинах', 'дисциплинах')}")
    valid = [k for k in ranks if rank_valid(k.rank, k.valid_until, today)]
    if valid:
        k = min(valid, key=lambda x: RANK_ORDER.index(x.rank) if x.rank in RANK_ORDER else len(RANK_ORDER))
        until = f" до {k.valid_until:%m.%Y}" if k.valid_until and k.rank != "MS" else ""
        parts.append(RANK_TITLES.get(k.rank, k.rank) + until)
    if not parts:
        return None
    line = "ФСП: " + ", ".join(parts)
    teams = sorted((r for r in by_tier["winner"] + by_tier["prize"] if r.team_id),
                   key=lambda r: (r.place or 99, -r.date.toordinal()))
    if teams:
        r = teams[0]
        place = f"{r.place} место" + (f" из {r.field_size}" if r.field_size else "")
        line += f"; в составе команды «{r.team_name}» ({r.team_size} чел., {place})"
    return line[:300]
