"""Проверки конвейера банка (процесс 3.6, техдизайн 5.1)."""
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.assessment.bank.base import Family
from app.assessment.bank.canon import is_correct
from app.config.params import PARAMS, Params

BACKEND_DIR = Path(__file__).resolve().parents[3]

_PROBE = (
    "import json, sys\n"
    "from app.assessment.bank.families import load_all\n"
    "from app.assessment.bank.base import REGISTRY\n"
    "load_all()\n"
    "f = REGISTRY[sys.argv[1]]\n"
    "print(json.dumps([f.make(s).key() for s in (1, 2, 3)], ensure_ascii=False, sort_keys=True, default=str))\n"
)


@dataclass
class CheckReport:
    code: str
    ok: bool
    unique_prompt_share: float
    distinct_answers: int
    space_size: int
    deterministic: bool
    hash_seed_stable: bool
    radicals_stable: bool
    keys_roundtrip: bool
    space_estimate: float = 0.0
    errors: list[str] = field(default_factory=list)


def estimate_space(m: int, distinct: int) -> float:
    """Размер пространства по числу различных экземпляров среди m случайных (задача о днях рождения).

    Повторов нет — берём нижнюю 95%-границу m²/6 (P(0 повторов) = e^(−m²/2N) ≥ 0.05).
    Иначе решаем distinct = N·(1 − e^(−m/N)) относительно N.
    """
    if distinct >= m:
        return m * m / 6
    lo, hi = float(distinct), 1e15
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if mid * -math.expm1(-m / mid) < distinct:
            lo = mid
        else:
            hi = mid
    return lo


def _probe(code: str, hash_seed: int) -> str:
    env = {**os.environ, "PYTHONHASHSEED": str(hash_seed)}
    out = subprocess.run([sys.executable, "-c", _PROBE, code], capture_output=True, text=True,
                         env=env, cwd=BACKEND_DIR, check=True, timeout=120)
    return out.stdout


def _dump(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _roundtrip(inst) -> bool:
    if inst.kind == "verdict":  # ключ вердикта — не ответ: проверяется эталонным ответом (bank.verdicts)
        from app.assessment.bank.verdicts import roundtrip
        return roundtrip(inst)
    return is_correct(inst, inst.answer)


def check_family(f: Family, params: Params = PARAMS, subprocess_probe: bool = True) -> CheckReport:
    n = params.gen_check_instances
    insts = [f.make(10_000 + s) for s in range(n)]
    unique = len({_dump(i.public()) for i in insts}) / n
    distinct = len({_dump(i.answer) for i in insts})
    deterministic = all(f.make(s).key() == f.make(s).key() for s in range(5))
    radicals_stable = len({i.radicals for i in insts}) == 1
    roundtrip = all(_roundtrip(i) for i in insts)
    # Объявленному space_size не доверяем: меряем по реальным экземплярам
    m = params.gen_space_sample
    space_est = estimate_space(m, len({_dump(f.make(20_000 + s).public()) for s in range(m)}))

    errors = []
    hash_stable = True
    if subprocess_probe:
        try:
            hash_stable = _probe(f.code, 0) == _probe(f.code, 4242)
            if not hash_stable:
                errors.append("результат зависит от PYTHONHASHSEED")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            hash_stable = False
            errors.append(f"проверка в подпроцессе не выполнилась: {type(e).__name__}")
    if unique < params.gen_unique_share:
        errors.append(f"уникальных prompt {unique:.2f} < {params.gen_unique_share}")
    if f.space_size < params.gen_space_min:
        errors.append(f"объявленное пространство {f.space_size} < {params.gen_space_min}")
    if space_est < params.gen_space_min:
        errors.append(f"оценка пространства {space_est:.0f} < {params.gen_space_min}")
    if distinct < params.gen_min_distinct_answers:
        errors.append(f"различных ответов {distinct} < {params.gen_min_distinct_answers}")
    if not deterministic:
        errors.append("генерация недетерминирована")
    if not radicals_stable:
        errors.append("радикалы различаются между экземплярами")
    if not roundtrip:
        errors.append("ключ не проходит собственную проверку")
    return CheckReport(
        code=f.code, ok=not errors, unique_prompt_share=unique, distinct_answers=distinct,
        space_size=f.space_size, deterministic=deterministic, hash_seed_stable=hash_stable,
        radicals_stable=radicals_stable, keys_roundtrip=roundtrip, space_estimate=space_est,
        errors=errors,
    )
