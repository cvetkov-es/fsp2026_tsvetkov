"""«Работа с ИИ» (процесс 2.5, ⚑3): план вердиктов попытки, выбор семейства и правило «подтверждено».

Чистые функции, без БД и без исполнения кода: верен ли каждый ответ, решает bank.verdicts.check_verdict.

Правило: точность ≥ AI_PASS_ACCURACY, взвешенная доля пропусков ≤ AI_PASS_MISS, все вердикты — за AI_MINUTES.
Пропуск — принятое («верно») дефектное или неоднозначное решение; при уверенности «высокая» он весит
AI_CONFIDENT_ERROR_WEIGHT. Ложный брак — отклонённое верное решение: метрика для отчёта, в правило не входит.
"""
import math
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Literal

from app.config.params import PARAMS, Params

AI_AREAS = ("python", "sql", "clarify")
Truth = Literal["ok", "defect", "ambiguous"]
VerdictKind = Literal["ok", "defect", "clarify"]


@dataclass(frozen=True)
class Slot:
    area: str  # python | sql | clarify
    flawed: bool  # у clarify всегда True: требование неоднозначно


def plan_slots(rng: random.Random, params: Params = PARAMS) -> list[Slot]:
    """AI_VERDICTS мест: AI_AMBIGUOUS неоднозначных, AI_SQL на SQL, остальные — Python.

    Доля дефектных и неоднозначных — случайная в пределах AI_DEFECT_SHARE и не объявляется."""
    n = params.ai_verdicts
    lo, hi = params.ai_defect_share
    n_flawed = rng.randint(math.ceil(lo * n), math.floor(hi * n))
    code_areas = ["sql"] * params.ai_sql + ["python"] * (n - params.ai_ambiguous - params.ai_sql)
    defects = set(rng.sample(range(len(code_areas)), n_flawed - params.ai_ambiguous))
    slots = [Slot(a, i in defects) for i, a in enumerate(code_areas)] + [Slot("clarify", True)] * params.ai_ambiguous
    rng.shuffle(slots)
    return slots


def slots_needed(params: Params = PARAMS) -> dict[str, int]:
    """Сколько семейств каждой области нужно на одну попытку (иначе банк не готов)."""
    return {"python": params.ai_verdicts - params.ai_ambiguous - params.ai_sql, "sql": params.ai_sql,
            "clarify": params.ai_ambiguous}


@dataclass(frozen=True)
class VerdictRef:
    code: str
    area: str
    b: float = 0.0
    exposure: int = 0


def choose_verdict(refs: Sequence[VerdictRef], area: str, used: set[str], seen: set[str],
                   rng: random.Random) -> VerdictRef | None:
    """Семейство области: не из этой попытки, сначала невиданные кандидатом; вес 1/(1+показы) по всему пулу.

    Свой выбор, а не choose_next: у вердиктов нет уровней, и randomesque по коду брал бы три первых по алфавиту."""
    for allow_seen in (False, True):
        pool = sorted((r for r in refs if r.area == area and r.code not in used and (allow_seen or r.code not in seen)),
                      key=lambda r: r.code)
        if pool:
            return rng.choices(pool, weights=[1.0 / (1 + r.exposure) for r in pool], k=1)[0]
    return None


@dataclass(frozen=True)
class VerdictResult:
    truth: Truth
    verdict: VerdictKind | None  # None — нет ответа (время вышло или ответ не разобран)
    confident: bool
    correct: bool


@dataclass(frozen=True)
class AiEvaluation:
    status: Literal["in_progress", "finished"]
    passed: bool | None
    n: int
    answered: int
    correct: int
    accuracy: float
    miss_weighted: float
    false_reject: float
    minutes: int
    in_time: bool

    def metrics(self) -> dict:
        d = asdict(self)
        d.pop("status")
        return {k: round(v, 3) if isinstance(v, float) else v for k, v in d.items()}


def evaluate_ai(results: Sequence[VerdictResult], *, time_over: bool, elapsed_s: float,
                params: Params = PARAMS) -> AiEvaluation:
    n = params.ai_verdicts
    answered = [r for r in results if r.verdict is not None]
    correct = sum(r.correct for r in results)
    flawed = [r for r in results if r.truth != "ok"]
    good = [r for r in results if r.truth == "ok"]
    miss = sum(params.ai_confident_error_weight if r.confident else 1.0 for r in flawed if r.verdict == "ok")
    miss_weighted = min(1.0, miss / len(flawed)) if flawed else 0.0
    false_reject = sum(r.verdict in ("defect", "clarify") for r in good) / len(good) if good else 0.0
    in_time = len(answered) == n and not time_over
    finished = len(results) >= n or time_over
    accuracy = correct / n
    passed = (in_time and accuracy >= params.ai_pass_accuracy and miss_weighted <= params.ai_pass_miss) if finished else None
    return AiEvaluation("finished" if finished else "in_progress", passed, n, len(answered), correct, accuracy,
                        miss_weighted, false_reject, max(1, math.ceil(elapsed_s / 60)), in_time)
