"""Лаборатория «Работы с ИИ»: три политики на настоящих вердиктах банка (процесс 2.5 и 8).

- «Принимает всё» — не проверяет решение ИИ: всегда «верно», уверенно. Без LLM.
- «Только второй ИИ» — копирует ответ второй модели (LLM_MODEL_AI_POLICY), всегда уверенно.
- «ИИ + проверка запуском» — те же ответы модели, но «уверенно» — только если предложенный ломающий
  вход подтвердился запуском (та же проверка, что у сервера); иначе «неуверенно».

Человек не моделируется: поведение людей без данных выдумывать не будем. Время модели — сумма задержек
ответов без времени на копирование, то есть нижняя граница. Только синтетика, без ПДн.
"""
import random
import statistics
import time
from collections.abc import Callable

from pydantic import Field

from app.assessment.bank.base import Instance, families
from app.assessment.bank.families import load_all
from app.assessment.bank.verdicts import AI_SPEC, INPUT_CLASSES, check_verdict, make_verdict
from app.assessment.engine.ai_verdicts import VerdictResult, evaluate_ai, plan_slots
from app.config.settings import Settings
from app.lab.llm_checks import _model_llm
from app.llm.client import LLMOut, Transport

POLICY_TITLES = {"trust_all": "Принимает всё", "llm_only": "Только второй ИИ",
                 "llm_verified": "ИИ + проверка запуском"}
POLICY_SYSTEM = (
    "Ты проверяешь решение, которое предложил ИИ-ассистент. Ответь verdict: ok — решение верно; defect — "
    "в решении ошибка; clarify — требование неоднозначно и его нужно уточнить. Для defect укажи line — номер "
    "строки с ошибкой (строки пронумерованы с 1) и ломающий вход: для Python — input_class из списка классов, "
    "для SQL — rows: данные таблиц {имя: [[значения колонок]]}, на которых решение даёт неверный результат. "
    "Для clarify укажи clarify — номер варианта уточнения (с 1).")


class PolicyOut(LLMOut):
    verdict: str = Field(pattern="^(ok|defect|clarify)$")
    line: int | None = None
    input_class: str | None = None
    rows: dict[str, list[list[str | int | float | None]]] | None = None
    clarify: int | None = None


def render_verdict(inst: Instance) -> str:
    p = inst.public()["prompt"]
    code = "\n".join(f"{i:>3}  {ln}" for i, ln in enumerate((p["code"] or "").split("\n"), start=1))
    parts = [f"Требование: {p['text']}", f"Решение ({p['language']}):\n{code}"]
    for tb in p.get("tables") or ():
        parts.append(f"Таблица {tb['name']}({', '.join(tb['columns'])}), пример данных:\n"
                     + "\n".join(map(str, tb["rows"])))
    if p.get("input_classes"):
        parts.append("Классы ломающего входа: " + "; ".join(f"{c} — {INPUT_CLASSES[c]}" for c in p["input_classes"]))
    parts.append("Варианты уточнения:\n" + "\n".join(f"{i}) {o}" for i, o in enumerate(p["clarify"], start=1)))
    return "\n\n".join(parts)


def _to_response(out: PolicyOut) -> dict:
    r = out.model_dump(exclude_none=True)
    if out.clarify is not None:
        r["clarify"] = out.clarify - 1  # у модели варианты с 1, у проверки — с 0
    return r


def sample_attempts(attempts: int, seed: int) -> list[list[Instance]]:
    """Попытки как у кандидата: тот же план мест и доля дефектных; семейства — без повторов в попытке."""
    load_all()
    by_area: dict[str, list[str]] = {}
    for f in families(AI_SPEC):
        by_area.setdefault(f.area, []).append(f.code)
    rng = random.Random(seed)
    out = []
    for _ in range(attempts):
        used: set[str] = set()
        insts = []
        for slot in plan_slots(rng):
            code = rng.choice(sorted(set(by_area[slot.area]) - used))
            used.add(code)
            insts.append(make_verdict(code, rng.randrange(10**9), slot.flawed))
        out.append(insts)
    return out


def _summary(evals: list) -> dict:
    return {"pass_rate": sum(bool(e.passed) for e in evals) / len(evals),
            "accuracy": statistics.fmean(e.accuracy for e in evals),
            "miss_weighted": statistics.fmean(e.miss_weighted for e in evals),
            "false_reject": statistics.fmean(e.false_reject for e in evals),
            "minutes": statistics.median(e.minutes for e in evals)}


def _score(insts: list[Instance], responses: list[dict | None], confident: Callable[[Instance, dict], bool],
           elapsed_s: float):
    results = []
    for inst, r in zip(insts, responses, strict=True):
        ok = r is not None and check_verdict(inst.answer, r)  # данные от модели — как от кандидата: в подпроцессе
        results.append(VerdictResult(inst.answer["truth"], r["verdict"] if r else None,
                                     r is not None and confident(inst, r), ok))
    return evaluate_ai(results, time_over=False, elapsed_s=elapsed_s)


def _verified(inst: Instance, r: dict) -> bool:
    """«Проверка запуском»: уверенно — только дефект, чей ломающий вход действительно ломает решение."""
    return r["verdict"] == "defect" and check_verdict(inst.answer, r)


def ai_policies(transport: Transport | None, settings: Settings, attempts: int = 5, seed: int = 7) -> dict:
    sample = sample_attempts(attempts, seed)
    trust = [_score(a, [{"verdict": "ok"}] * len(a), lambda i, r: True, 0) for a in sample]
    rows = [{"key": "trust_all", "title": POLICY_TITLES["trust_all"], **_summary(trust)}]
    model = settings.llm_model_ai_policy
    if transport is None:
        return {"attempts": attempts, "model": model, "llm": "skipped", "policies": rows}
    llm = _model_llm(transport, settings, model)
    only, verified = [], []
    for a in sample:
        responses, spent = [], 0.0
        for inst in a:
            t = time.perf_counter()
            res = llm.json("offline", POLICY_SYSTEM, render_verdict(inst), PolicyOut)
            spent += time.perf_counter() - t
            responses.append(None if res is None else _to_response(res[0]))
        only.append(_score(a, responses, lambda i, r: True, spent))
        verified.append(_score(a, responses, _verified, spent))
    rows += [{"key": "llm_only", "title": POLICY_TITLES["llm_only"], **_summary(only)},
             {"key": "llm_verified", "title": POLICY_TITLES["llm_verified"], **_summary(verified)}]
    return {"attempts": attempts, "model": model, "llm": "ok", "policies": rows}
