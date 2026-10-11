"""Метрики лаборатории: согласие, ранжирование, неопределённость (исследование 03, §3)."""
import math
import random
from collections.abc import Callable, Sequence


def cohen_kappa(a: Sequence, b: Sequence) -> float:
    """κ Коэна для двух разметок одних и тех же объектов."""
    n = len(a)
    if n == 0:
        return float("nan")
    labels = sorted(set(a) | set(b), key=str)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pe = sum((list(a).count(lb) / n) * (list(b).count(lb) / n) for lb in labels)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def dcg(rels: Sequence[float], k: int) -> float:
    return sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(rels[:k]))


def ndcg_at_k(ranked_rels: Sequence[float], k: int) -> float:
    ideal = dcg(sorted(ranked_rels, reverse=True), k)
    return dcg(ranked_rels, k) / ideal if ideal > 0 else 0.0


def precision_at_k(ranked_rels: Sequence[float], k: int, relevant: float = 2) -> float:
    top = ranked_rels[:k]
    return sum(r >= relevant for r in top) / k if top else 0.0


def mrr(ranked_rels: Sequence[float], relevant: float = 2) -> float:
    return next((1 / (i + 1) for i, r in enumerate(ranked_rels) if r >= relevant), 0.0)


def bootstrap_ci(values: Sequence[float], n: int = 1000, seed: int = 7, alpha: float = 0.05) -> tuple[float, float, float]:
    """Среднее и 95% интервал перцентильным bootstrap по объектам (у нас — по потребностям)."""
    vals = list(values)
    if not vals:
        return (float("nan"),) * 3
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(n))
    return sum(vals) / len(vals), means[int(alpha / 2 * n)], means[int((1 - alpha / 2) * n) - 1]


def kendall_tau(order_a: Sequence, order_b: Sequence) -> float:
    """τ Кендалла между двумя порядками одного набора объектов (O(n²), n ≤ нескольких сотен)."""
    pos_b = {x: i for i, x in enumerate(order_b)}
    items = [x for x in order_a if x in pos_b]
    n = len(items)
    if n < 2:
        return 1.0
    concordant = sum(1 if pos_b[items[i]] < pos_b[items[j]] else -1 for i in range(n) for j in range(i + 1, n))
    return concordant / (n * (n - 1) / 2)


def mean(xs: Sequence[float]) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def quantile(xs: Sequence[float], q: float) -> float:
    s = sorted(xs)
    if not s:
        return float("nan")
    return s[min(len(s) - 1, int(q * len(s)))]


def rate(xs: Sequence, pred: Callable) -> float:
    xs = list(xs)
    return sum(1 for x in xs if pred(x)) / len(xs) if xs else float("nan")
