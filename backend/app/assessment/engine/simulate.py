"""Симуляция попытки по истинному θ (для тестов и лаборатории валидации)."""
import random
from collections import Counter
from collections.abc import Callable, Sequence

from app.assessment.engine.irt import p_correct
from app.assessment.engine.levels import PHASE1_BAND, PHASE2_BAND, Grade
from app.assessment.engine.rules import AttemptConfig, Evaluation, ItemResult, evaluate
from app.assessment.engine.selection import FamilyRef, choose_next, selection_rng
from app.config.params import PARAMS


def synthetic_bank(areas: Sequence[str], per_cell: int = PARAMS.families_per_cell_cut,
                   b_levels: Sequence[float] = PARAMS.b_levels) -> list[FamilyRef]:
    return [FamilyRef(f"{a}-{lv}-{i}", a, lv, b_levels[lv - 1])
            for a in areas for lv in range(1, 6) for i in range(per_cell)]


def simulate_attempt(true_theta: float, cfg: AttemptConfig, bank: Sequence[FamilyRef],
                     areas: Sequence[str], rng_seed: int, secret: bytes = b"sim",
                     p_answer: Callable[[FamilyRef], float] | None = None) -> Evaluation:
    """p_answer — вероятность верного ответа на семейство; по умолчанию модель Раша от true_theta.
    Лаборатория подменяет её, например, для эксперимента «утечка»."""
    answer_rng = random.Random(rng_seed)
    attempt_id = f"sim-{rng_seed}"
    items: list[ItemResult] = []
    used: set[str] = set()
    counts: Counter[str] = Counter()
    while True:
        ev = evaluate(cfg, items)
        if ev.status in ("finished", "awaiting_continue"):
            return ev
        phase = 1 if ev.status == "phase1" else 2
        band = PHASE1_BAND[Grade(cfg.target)] if phase == 1 else PHASE2_BAND[Grade(cfg.target)]
        seq = len(items) + 1
        f = choose_next(families=bank, areas=areas, used_in_attempt=used, area_counts=counts,
                        seen=set(), band=band, theta=ev.theta, b_levels=cfg.params.b_levels,
                        rng=selection_rng(secret, attempt_id, seq), k=cfg.params.randomesque_k)
        if f is None:
            return ev
        p = p_answer(f) if p_answer else float(p_correct(true_theta, f.b))
        correct = answer_rng.random() < p
        items.append(ItemResult(seq, f.code, f.area, f.level, f.b, correct, phase))
        used.add(f.code)
        counts[f.area] += 1
