"""Семантические проверки семейств «Работы с ИИ»: формат вердикта и независимые оракулы."""
import copy
import random
from collections.abc import Callable, Iterable

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.canon import canonical
from app.assessment.bank.families import load_all
from app.assessment.bank.sql_isolated import run_payload
from app.assessment.bank.verdicts import (
    _CASE_BUILTINS,
    AI_SPEC,
    INPUT_CLASSES,
    make_verdict,
    roundtrip,
)

load_all()
SEEDS = range(40)


def codes(area: str) -> list[str]:
    return sorted(c for c, f in REGISTRY.items() if f.specialization == AI_SPEC and f.area == area)


def assert_verdict_form(code: str) -> None:
    """Ключ проходит самопроверку; вид задания одинаков для верного и дефектного решения."""
    for s in SEEDS:
        ok, bad = make_verdict(code, s, False), make_verdict(code, s, True)
        assert roundtrip(ok) and roundtrip(bad)
        for inst in (ok, bad):
            p = inst.public()["prompt"]
            assert len(p["clarify"]) == 4 and len(set(p["clarify"])) == 4
            assert set(p["input_classes"]) <= set(INPUT_CLASSES)
            assert p["language"] in ("python", "sql") and p["text"] and p["code"]
        po, pb = ok.public()["prompt"], bad.public()["prompt"]
        assert po["input_classes"] == pb["input_classes"] and sorted(po["clarify"]) == sorted(pb["clarify"])
        assert po["text"] == pb["text"]  # дефект — только в решении
        if bad.answer["truth"] == "defect":
            assert 1 <= bad.answer["line"] <= len(pb["code"].split("\n"))
            assert po["code"].split("\n")[bad.answer["line"] - 1] != pb["code"].split("\n")[bad.answer["line"] - 1]


def solve_fn(code: str) -> Callable:
    ns: dict = {"__builtins__": _CASE_BUILTINS}
    exec(compile(code, "<test>", "exec"), ns)  # noqa: S102 — только код банка
    return ns["solve"]


def _call(f: Callable, x):
    try:
        return f(copy.deepcopy(x))
    except Exception as e:  # noqa: BLE001
        return f"<ошибка {type(e).__name__}>"


def assert_python_oracle(code: str, parse: Callable[[str], dict], oracle: Callable[[dict, object], object],
                         inputs: Callable[[dict, random.Random], Iterable]) -> None:
    """Верное решение совпадает с независимым оракулом на своих входах; дефектное — хоть на одном расходится."""
    for s in SEEDS:
        rng = random.Random(s)
        for flawed in (False, True):
            p = make_verdict(code, s, flawed).public()["prompt"]
            params, f = parse(p["text"]), solve_fn(p["code"])
            diffs = [x for x in inputs(params, rng) if _call(f, x) != oracle(params, copy.deepcopy(x))]
            assert bool(diffs) == flawed, (code, s, flawed, p["code"], diffs[:3])


def assert_sql_oracle(code: str, parse: Callable[[str], dict], oracle: Callable[[dict, dict], list],
                      datasets: Callable[[dict, random.Random], Iterable[dict]]) -> None:
    """Эталон совпадает с оракулом на случайных данных; дефект расходится с оракулом на данных-свидетеле."""
    for s in SEEDS:
        rng = random.Random(s)
        for flawed in (False, True):
            inst = make_verdict(code, s, flawed)
            sql, params = inst.answer["sql"], parse(inst.public()["prompt"]["text"])
            for data in datasets(params, rng):
                ref = run_payload({"schema": sql["schema"], "data": data, "queries": [sql["reference"]]})[0]
                assert ref is not None and canonical("rows", ref) == canonical("rows", oracle(params, data)), (code, data)
            if flawed:
                w = {name: rows for name, _cols, rows in sql["witness"]}
                shown = run_payload({"schema": sql["schema"], "data": w, "queries": [sql["shown"]]})[0]
                assert shown is None or canonical("rows", shown) != canonical("rows", oracle(params, w))
            else:
                assert sql["shown"] == sql["reference"]


def assert_clarify(code: str, right: str) -> None:
    """Неоднозначное требование при любом flawed; верный вопрос — объявленный семейством."""
    for s in SEEDS:
        for flawed in (False, True):
            inst = make_verdict(code, s, flawed)
            assert inst.answer["truth"] == "ambiguous"
            assert inst.public()["prompt"]["clarify"][inst.answer["clarify"]] == right
