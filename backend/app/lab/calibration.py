"""Калибровка порогов методом контрастных групп на симуляции (процесс 5 и 3.3).

Экспертный порог Middle смещён относительно «рыночного» на SHIFT. Работодатели голосуют «соответствует
или выше» / «ниже» по истинному θ кандидата. По голосам и θ̂ оценивается порог (логистическая регрессия),
затем байесовское сжатие к экспертному: cut = (n·cut_obs + n0·cut_expert) / (n + n0), n0 = CALIB_MIN_N.
"""
import math
import random

from app.assessment.engine.levels import Grade
from app.config.params import PARAMS
from app.lab.metrics import mean
from app.lab.population import thresholds

SHIFT = 0.3  # рынок строже эксперта на 0.3 логита
SE = 0.45  # типичная погрешность θ̂ после полного теста
SLOPE = 1.7  # крутизна мнения работодателя вокруг рыночного порога


def _logit_cut(x: list[float], y: list[int]) -> float | None:
    """Порог −a/b логистической регрессии y ~ σ(a + b·x), метод Ньютона."""
    a, b = 0.0, 1.0
    for _ in range(30):
        ga = gb = haa = hab = hbb = 0.0
        for xi, yi in zip(x, y, strict=True):
            p = 1 / (1 + math.exp(-max(-30.0, min(30.0, a + b * xi))))
            w = p * (1 - p)
            ga += yi - p
            gb += (yi - p) * xi
            haa += w
            hab += w * xi
            hbb += w * xi * xi
        det = haa * hbb - hab * hab
        if det <= 1e-9:
            return None
        a += (hbb * ga - hab * gb) / det
        b += (haa * gb - hab * ga) / det
    return -a / b if b > 1e-6 else None


def calibration(seed: int, sizes: tuple[int, ...] = (30, 100, 300), replicates: int = 200) -> dict:
    cut_expert = thresholds().cut(Grade.middle)
    cut_true = cut_expert + SHIFT
    rng = random.Random(seed)
    rows = []
    for n in sizes:
        applied = n >= PARAMS.calib_min_n  # продукт калибрует порог, только набрав CALIB_MIN_N голосов в ячейке
        err_obs, err_cal = [], []
        for _ in range(replicates):
            # Голоса есть только у приглашённых, а приглашают сильнее порога: выборка смещена вверх
            theta = [cut_expert + rng.gauss(0.4, 0.6) for _ in range(n)]
            est = [t + rng.gauss(0, SE) for t in theta]
            votes = [int(rng.random() < 1 / (1 + math.exp(-SLOPE * (t - cut_true)))) for t in theta]
            obs = _logit_cut(est, votes)
            if obs is None:
                continue
            n0 = PARAMS.calib_min_n
            cal = (n * obs + n0 * cut_expert) / (n + n0) if applied else cut_expert
            err_obs.append(abs(obs - cut_true))
            err_cal.append(abs(cal - cut_true))
        rows.append({"n": n, "expert_error": SHIFT, "observed_error": mean(err_obs), "calibrated_error": mean(err_cal),
                     "applied": applied})
    return {"shift": SHIFT, "calib_min_n": PARAMS.calib_min_n, "by_n": rows}
