"""Модель Раша (1PL) и EAP-оценка способности на фиксированной сетке."""
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

GRID = np.linspace(-6.0, 6.0, 241)


@dataclass(frozen=True)
class Response:
    b: float
    correct: bool


def p_correct(theta, b: float):
    return 1.0 / (1.0 + np.exp(-(np.asarray(theta, dtype=float) - b)))


def log_prior(mean: float, sd: float) -> np.ndarray:
    return -0.5 * ((GRID - mean) / sd) ** 2


def log_lik(b: float, correct: bool) -> np.ndarray:
    p = p_correct(GRID, b)
    return np.log(p) if correct else np.log1p(-p)


def normalize(logw: np.ndarray) -> np.ndarray:
    w = np.exp(logw - logw.max())
    return w / w.sum()


def posterior(prior_mean: float, prior_sd: float, responses: Sequence[Response]) -> np.ndarray:
    logw = log_prior(prior_mean, prior_sd)
    for r in responses:
        logw = logw + log_lik(r.b, r.correct)
    return normalize(logw)


def eap(w: np.ndarray) -> tuple[float, float]:
    mean = float((GRID * w).sum())
    sd = float(np.sqrt(((GRID - mean) ** 2 * w).sum()))
    return mean, sd


def prob_above(w: np.ndarray, cut: float) -> float:
    """P(θ ≥ cut). Каждая точка сетки — ячейка шириной h; ячейка, в которую попал порог,
    учитывается долей выше порога. Иначе пороги (b + 0.708) не совпадают с узлами сетки и
    вероятность смещается на ~1 п.п. против кандидата."""
    h = GRID[1] - GRID[0]
    frac = np.clip((GRID + h / 2 - cut) / h, 0.0, 1.0)
    return float((w * frac).sum())
