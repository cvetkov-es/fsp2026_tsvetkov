"""LLM в лаборатории — только синтетика, без ПДн (процесс 3.6 шаг 4 и 8; исследование 03, §3d).

- Решатель банка: две модели разных семейств решают экземпляры; если обе расходятся с ключом — ключ под
  подозрением (ручная проверка). Бейзлайн — случайный ответ на выбор, номер строки и порядок.
- Судья подбора: модель видит две анонимные карточки для потребности в случайном порядке, без баллов,
  и выбирает лучшую. Судья — другая модель, чем перефразирование объяснений.
"""
import json
import random

from pydantic import Field

from app.assessment.bank.base import Instance, families
from app.assessment.bank.canon import is_correct
from app.assessment.bank.families import load_all
from app.assessment.bank.verdicts import AI_SPEC
from app.config.params import PARAMS
from app.config.settings import Settings
from app.lab.population import NOW, make_needs, make_people, observe, thresholds
from app.lab.rubric import relevance
from app.llm.breaker import CircuitBreaker
from app.llm.client import LLM, LLMOut, Transport
from app.llm.config import route
from app.matching.explain import explain
from app.matching.scoring import evaluate_candidate, rank

SOLVER_SYSTEM = ("Реши задание на собеседовании для ИТ-специалиста. Подумай, затем дай только итоговый ответ "
                 "в поле answer строкой, в формате из подсказки к ответу. Варианты и шаги пронумерованы с 1.")
JUDGE_SYSTEM = ("Ты опытный технический рекрутер. Даны потребность компании и два анонимных кандидата A и B. "
                "Выбери, кто лучше подходит для приглашения на собеседование. Ответ — better: A или B.")


class SolverOut(LLMOut):
    answer: str = Field(max_length=2000)


class JudgeOut(LLMOut):
    better: str = Field(pattern="^[AB]$")


def _model_llm(transport: Transport, base: Settings, model: str) -> LLM:
    s = base.model_copy(update={"llm_profile": "dev", "llm_model_runtime": model})
    return LLM(transport, s, CircuitBreaker(PARAMS.llm_cb_errors, PARAMS.llm_cb_cooldown_min))


def render(inst: Instance) -> str:
    p = inst.public()["prompt"]
    parts = [p["text"]]
    if p.get("code"):
        parts.append(f"```{p.get('language') or ''}\n{p['code']}\n```")
    for tb in p.get("tables") or ():
        parts.append(f"Таблица {tb['name']}: {', '.join(tb['columns'])}\n" + "\n".join(map(str, tb["rows"])))
    if p.get("options"):
        parts.append("Варианты:\n" + "\n".join(f"{i}) {o}" for i, o in enumerate(p["options"], start=1)))
    if p.get("steps"):
        parts.append("Шаги:\n" + "\n".join(f"{i}) {o}" for i, o in enumerate(p["steps"], start=1)))
    if p.get("answer_hint"):
        parts.append(f"Формат ответа: {p['answer_hint']}")
    return "\n\n".join(parts)


def to_response(inst: Instance, answer: str):
    """Ответ модели — в формат, который принимает проверка кандидата (выбор у модели нумеруется с 1)."""
    if inst.kind == "choice":
        return int(answer.strip().split()[0].rstrip(").")) - 1
    if inst.kind == "rows":
        return json.loads(answer)
    return answer


def _random_response(inst: Instance, rng: random.Random):
    p = inst.public()["prompt"]
    if inst.kind == "choice":
        return rng.randrange(len(p["options"]))
    if inst.kind == "order":
        steps = list(range(1, len(p["steps"]) + 1))
        rng.shuffle(steps)
        return steps
    if inst.kind == "line":
        return rng.randint(1, max(1, len((p.get("code") or "").splitlines())))
    return None


def solver_check(transport: Transport, settings: Settings, per_spec: int = 5, seed: int = 1) -> dict:
    load_all()
    rng = random.Random(seed)
    solvers = {"a": settings.llm_model_solver_a, "b": settings.llm_model_solver_b}
    llms = {k: _model_llm(transport, settings, m) for k, m in solvers.items()}
    rows = []
    groups = {spec: families(spec) for spec in ("backend", "frontend", "data")}
    # навыки — одной группой; вердикты «Работы с ИИ» — свой формат, их проверяет раздел ai_skill_policies
    groups["skills"] = [f for f in families() if f.specialization.startswith("skill:") and f.specialization != AI_SPEC]
    for fams in groups.values():
        for f in rng.sample(fams, min(per_spec, len(fams))):
            inst = f.make(rng.randrange(10**9))
            row = {"family": f.code, "kind": inst.kind}
            for k, llm in llms.items():
                res = llm.json("offline", SOLVER_SYSTEM, render(inst), SolverOut)
                try:
                    row[k] = None if res is None else is_correct(inst, to_response(inst, res[0].answer))
                except (ValueError, IndexError):
                    row[k] = False
            rnd = _random_response(inst, rng)
            row["random"] = None if rnd is None else is_correct(inst, rnd)
            rows.append(row)
    answered = [r for r in rows if r["a"] is not None and r["b"] is not None]
    return {"models": solvers, "n": len(rows),
            "agree_a": sum(bool(r["a"]) for r in answered) / len(answered) if answered else None,
            "agree_b": sum(bool(r["b"]) for r in answered) / len(answered) if answered else None,
            "random_baseline": (lambda xs: sum(xs) / len(xs) if xs else None)([r["random"] for r in rows if r["random"] is not None]),
            "suspect_keys": [r["family"] for r in answered if not r["a"] and not r["b"]], "rows": rows}


def _card_text(p, need) -> str:
    r = evaluate_candidate(p.facts, need, NOW)
    e = explain(r, need, None, None)
    return "\n".join([*e.lines, *(f"нет: {m}" for m in e.missing)])


def judge_check(transport: Transport, settings: Settings, pairs: int = 40, seed: int = 3) -> dict:
    judge = settings.llm_model_judge
    if judge == route("runtime", settings)[0].name:
        raise ValueError("LLM-судья должен быть другой моделью, чем перефразирование объяснений")
    llm = _model_llm(transport, settings, judge)
    t = thresholds()
    rng = random.Random(seed)
    people = observe(make_people(240, seed + 3000), seed + 3000)
    needs = make_needs(9, seed + 3000)
    rows = []
    attempts = 0
    while len(rows) < pairs and attempts < pairs * 3 and llm.breaker.allow():
        attempts += 1
        n = rng.choice(needs).facts
        ranked = rank((p.facts for p in people if p.spec == n.specialization), n, NOW)
        pos = {r.c.ref: i for i, r in enumerate(ranked)}
        pool = [p for p in people if p.ref in pos]
        a, b = rng.sample(pool, 2)
        ra, rb = relevance(a, n, t), relevance(b, n, t)
        if ra == rb:
            continue
        first, second = (a, b) if rng.random() < 0.5 else (b, a)
        need_text = f"{n.specialization}, грейды: {', '.join(n.grades)}, обязательно: {', '.join(n.must)}"
        res = llm.json("offline", JUDGE_SYSTEM, f"Потребность: {need_text}\n\nA:\n{_card_text(first, n)}\n\nB:\n{_card_text(second, n)}", JudgeOut)
        if res is None:
            continue  # сбой одного вызова — пробуем другую пару; breaker остановит при серии сбоев
        picked = first if res[0].better == "A" else second
        truth = a if ra > rb else b
        ours = a if pos[a.ref] < pos[b.ref] else b
        rows.append({"judge_vs_truth": picked is truth, "judge_vs_ours": picked is ours, "ours_vs_truth": ours is truth})
    k = len(rows)
    return {"model": judge, "pairs": k,
            "judge_agrees_with_truth": sum(r["judge_vs_truth"] for r in rows) / k if k else None,
            "judge_agrees_with_ours": sum(r["judge_vs_ours"] for r in rows) / k if k else None,
            "ours_agrees_with_truth": sum(r["ours_vs_truth"] for r in rows) / k if k else None}
