"""Выбор следующего задания: уровень по θ̂, области по кругу, randomesque с весом 1/(1+показы)."""
import hashlib
import hmac
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FamilyRef:
    code: str
    area: str
    level: int
    b: float
    exposure: int = 0


def _hseed(secret: bytes, *parts: str) -> int:
    # Префикс длины: части с «|» внутри не могут склеиться в чужой набор частей
    msg = "|".join(f"{len(p)}:{p}" for p in parts)
    digest = hmac.new(secret, msg.encode(), hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big")


def selection_rng(secret: bytes, attempt_id: str, seq: int) -> random.Random:
    return random.Random(_hseed(secret, "select", attempt_id, str(seq)))


def instance_seed(secret: bytes, candidate_id: str, attempt_id: str, family_code: str) -> int:
    return _hseed(secret, "instance", candidate_id, attempt_id, family_code)


def _levels_by_distance(theta: float, band: Sequence[int], b_levels: Sequence[float]) -> list[int]:
    return sorted(band, key=lambda lv: (abs(b_levels[lv - 1] - theta), lv))


def target_level(theta: float, band: Sequence[int], b_levels: Sequence[float]) -> int:
    return _levels_by_distance(theta, band, b_levels)[0]


def choose_next(
    *,
    families: Sequence[FamilyRef],
    areas: Sequence[str],
    used_in_attempt: set[str],
    area_counts: Mapping[str, int],
    seen: set[str],
    band: Sequence[int],
    theta: float,
    b_levels: Sequence[float],
    rng: random.Random,
    k: int,
) -> FamilyRef | None:
    area_order = sorted(areas, key=lambda a: (area_counts.get(a, 0), rng.random()))
    level_order = _levels_by_distance(theta, band, b_levels)
    for allow_seen in (False, True):
        pool = [
            f for f in families
            if f.code not in used_in_attempt and f.level in band and (allow_seen or f.code not in seen)
        ]
        if not pool:
            continue
        for area in area_order:
            for lv in level_order:
                cands = sorted((f for f in pool if f.area == area and f.level == lv),
                               key=lambda f: (abs(f.b - theta), f.code))
                if cands:
                    top = cands[:k]
                    return rng.choices(top, weights=[1.0 / (1 + f.exposure) for f in top], k=1)[0]
    return None
