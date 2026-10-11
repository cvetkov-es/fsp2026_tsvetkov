"""Полный прогон лаборатории: отчёт reports/validation.json, 4 числа и 2 графика для страницы (процесс 8)."""
import logging
import math
import time

from app.common.clock import now
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.lab.ai_policies import ai_policies
from app.lab.calibration import calibration
from app.lab.llm_checks import judge_check, solver_check
from app.lab.market import market
from app.lab.matching_validation import validate_matching
from app.lab.test_validation import validate_test
from app.llm.client import openai_transport

log = logging.getLogger("lab")
MATCHING_PEOPLE_MAX, MATCHING_NEEDS = 900, 30
# Облегчённая фиксированная часть для прогонов из интерфейса: кривая решений и «утечка» не зависят
# от размера популяции и съедают больше половины короткого прогона. Прогон `make validate` считает полно.
LIGHT_TEST = {"oc_per_point": 60, "leak_n": 150}
RANKER_TITLES = {"ours": "Наше ранжирование", "stack_keywords": "Ключевые слова стека", "self_description": "Самоописание",
                 "test_only": "Только тест", "fsp_only": "Только ФСП", "random": "Случайно",
                 "no_fsp": "без ФСП", "no_stack": "без стека", "no_accept": "без готовности",
                 "no_confirmation": "без подтверждений", "no_blocks": "без блоков"}


def _llm_sections(seed: int) -> dict:
    s = get_settings()
    transport = openai_transport(s)
    if transport is None:
        return {"solver": {"skipped": "нет ключа LLM"}, "judge": {"skipped": "нет ключа LLM"}}
    out = {}
    for name, fn in (("solver", lambda: solver_check(transport, s, seed=seed)),
                     ("judge", lambda: judge_check(transport, s, seed=seed))):
        try:
            out[name] = fn()
        except Exception as e:  # сеть или провайдер — раздел отчёта, а не падение всего прогона
            log.warning("lab llm %s: %s", name, e)
            out[name] = {"error": type(e).__name__}
    return out


def _ai_section(seed: int, with_llm: bool) -> dict:
    """«Работа с ИИ»: «Принимает всё» считается всегда, политики со второй моделью — только с ключом LLM."""
    s = get_settings()
    try:
        return ai_policies(openai_transport(s) if with_llm else None, s, seed=seed)
    except Exception as e:  # раздел отчёта, а не падение всего прогона
        log.warning("lab ai policies: %s", e)
        return {"error": type(e).__name__}


def sanitize(x):
    """NaN и ±∞ (пустая корзина на малой популяции) → None: JSONB и JSON-ответ API их не принимают."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: sanitize(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [sanitize(v) for v in x]
    return x


def _f(v, spec: str) -> str:
    """Число для подписи; пустая корзина (NaN или None) — прочерк, а не «nan%»."""
    return "—" if v is None or (isinstance(v, float) and not math.isfinite(v)) else format(v, spec)


def headline(test: dict, matching: dict) -> list[dict]:
    rk = matching["rankers"]
    best = max((k for k in rk if k != "ours"), key=lambda k: rk[k]["all"]["ndcg"]["mean"])
    ours = rk["ours"]["all"]["ndcg"]
    leak = test["leak"]
    return [
        {"key": "accuracy_far", "title": "Верные решения теста", "value": test["accuracy_far"], "format": "percent",
         "note": f"если |θ − порог| ≥ 0.5; у самого порога {_f(test['accuracy_near'], '.0%')} — зона неопределённости теста"},
        {"key": "retest", "title": "Повторный тест даёт то же решение", "value": test["retest_agreement"],
         "format": "percent", "note": f"κ = {_f(test['retest_kappa'], '.2f')}; вдали от порога κ стремится к 1"},
        {"key": "ndcg", "title": "Качество подборки, nDCG@10", "value": ours["mean"], "format": "number",
         "note": f"95% ДИ {_f(ours['ci_low'], '.2f')}–{_f(ours['ci_high'], '.2f')}; лучший бейзлайн «{RANKER_TITLES[best]}»: "
                 f"{_f(rk[best]['all']['ndcg']['mean'], '.2f')}"},
        {"key": "leak", "title": "Ложные подтверждения при утечке трети банка", "value": leak["generated_bank_false_positive"],
         "format": "percent", "note": f"у статичного банка {_f(leak['static_bank_false_positive'], '.0%')}, "
                                      f"у кандидата без доступа к утечке {_f(leak['honest_false_positive'], '.0%')}"},
    ]


def charts(test: dict, matching: dict) -> dict:
    bars = [{"key": k, "title": RANKER_TITLES[k], **{m: v for m, v in r["all"]["ndcg"].items()}, "group": "ranker"}
            for k, r in matching["rankers"].items()]
    bars += [{"key": k, "title": RANKER_TITLES[k], **v, "group": "ablation"} for k, v in matching["ablation"].items()]
    return {"oc_curve": test["oc_curve"], "ndcg_bars": bars}


def run_all(n: int = PARAMS.lab_max_pop, seed: int = 2026, with_llm: bool = True, light: bool = False) -> dict:
    started = time.perf_counter()
    test = validate_test(n, seed, **(LIGHT_TEST if light else {}))
    matching = validate_matching(min(n, MATCHING_PEOPLE_MAX), MATCHING_NEEDS, seed)
    report = {
        "version": 1, "generated_at": now().isoformat(), "population": n, "seed": seed,
        "headline": headline(test, matching), "charts": charts(test, matching),
        "test": test, "matching": matching, "calibration": calibration(seed), "market": market(seed),
        "llm": _llm_sections(seed) if with_llm else {"solver": {"skipped": "без LLM"}, "judge": {"skipped": "без LLM"}},
        "ai_skill_policies": _ai_section(seed, with_llm),
    }
    report["duration_s"] = round(time.perf_counter() - started, 1)
    return sanitize(report)
