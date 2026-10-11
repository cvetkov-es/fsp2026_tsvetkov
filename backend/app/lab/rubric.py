"""Рубрика «истинной пригодности» 0–3 от лица работодателя (исследование 03, §3a).

Написана отдельно от формулы ранжирования и видит только скрытую истину: настоящий θ (через истинный грейд),
настоящий стек, настоящие ожидания. Ни s, ни f, ни заявленный стек здесь не используются.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.assessment.engine.levels import Thresholds
from app.lab.population import Person, true_grade

if TYPE_CHECKING:  # только тип потребности: формула ранжирования рубрике не нужна
    from app.matching.scoring import NeedFacts

ORDER = ("junior", "middle", "senior")


def _formats_ok(cand: tuple[str, ...], need: tuple[str, ...]) -> bool:
    if not cand or not need:
        return True
    return bool(set(cand) & set(need)) or "hybrid" in cand or "hybrid" in need


def relevance(p: Person, need: NeedFacts, t: Thresholds) -> int:
    g = true_grade(p.theta, t)
    if g is None:
        return 0
    dist = min(abs(ORDER.index(g) - ORDER.index(x)) for x in need.grades)
    if dist >= 2 or not _formats_ok(p.formats, need.formats):
        return 0
    share = sum(1 for x in need.must if x in p.techs) / len(need.must) if need.must else 1.0
    if share < 0.5:
        return 0
    score = 3
    if dist == 1 or share < 1:
        score = min(score, 1)
    if p.threshold_net and need.salary_to_net:
        gap = (p.threshold_net - need.salary_to_net) / p.threshold_net
        if gap > 0.2:
            score = min(score, 1)
        elif gap > 0:
            score = min(score, 2)
    if not (p.open_window and p.active):
        score = min(score, 2)
    return score
