"""Вердикты навыка «Работа с ИИ» (процесс 2.5, ⚑3): формат задания, ключ и проверка ответа.

Задание — требование и решение, которое «предложил ИИ-ассистент» (решения собраны из шаблонов, чтобы
ключи были неоспоримы). Решение верно, содержит дефект ровно в одной строке или требование неоднозначно.
Ответ кандидата: «верно»; «неверно» + строка + ломающий вход; «нужно уточнить» + вариант уточнения;
и уверенность «низкая / высокая».

- Python: ломающий вход выбирается из закрытого списка классов. Какие классы ломают решение, считается
  исполнением эталона и показанного кода на представителях классов (исполняется только наш код).
- SQL: ломающий вход — данные, которые вводит кандидат. Эталон и показанный запрос исполняются на них
  в отдельном процессе с таймаутом (техдизайн 5.2).
"""
import copy
import json
import logging
import math
import random
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.assessment.bank.base import Generated, Instance, Prompt, Table, family
from app.assessment.bank.canon import canonical
from app.assessment.bank.sql_isolated import run_payload
from app.common.subproc import child_limits, safe_env
from app.config.params import PARAMS

log = logging.getLogger("assessment.verdicts")
AI_SPEC = "skill:ai"
INPUT_CLASSES: dict[str, str] = {
    "empty": "Пустой ввод", "none": "None или NULL", "dup": "Дубликаты",
    "negative": "Отрицательное число", "boundary": "Граница диапазона", "unicode": "Юникод",
}
CELL_MAX = 40  # символов в ячейке данных кандидата
SQL_MEM_MB = 256  # предел памяти подпроцесса, который исполняет эталон и решение на данных кандидата
BACKEND_DIR = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class VerdictPrompt(Prompt):
    """text — требование, code — решение, tables — схема и пример данных (SQL)."""
    input_classes: tuple[str, ...] = ()  # Python: какие классы ломающего входа можно выбрать
    clarify: tuple[str, ...] = ()  # закрытый список уточнений — у каждого вердикта, иначе вид задания выдаёт ответ


@dataclass(frozen=True)
class Mutation:
    """Дефект: строка эталона `line` (с 1) заменяется на `code`."""
    line: int
    code: str
    cls: str | None = None  # Python: класс входа, который дефект обязан ломать (проверяется при генерации)
    witness: tuple[Table, ...] = ()  # SQL: данные, на которых эталон и дефект расходятся; кандидату не видны


# ---------- исполнение нашего кода ----------

_CASE_BUILTINS = {
    "len": len, "range": range, "sum": sum, "sorted": sorted, "min": min, "max": max, "list": list,
    "dict": dict, "set": set, "tuple": tuple, "str": str, "int": int, "float": float, "bool": bool,
    "enumerate": enumerate, "zip": zip, "abs": abs, "round": round, "any": any, "all": all,
    "isinstance": isinstance, "reversed": reversed, "ValueError": ValueError,
}


class Reps(tuple):
    """Несколько представителей одного класса: класс ломает решение, если ломает хотя бы один из них.

    Кандидат видит только название класса, поэтому у «границы» бывают обе стороны: ровно k и k + 1."""


def _run_one(fn: Callable, arg: Any) -> str:
    try:
        return repr(fn(copy.deepcopy(arg)))
    except Exception as e:  # noqa: BLE001 — падение показанного кода и есть поломка
        return f"<ошибка {type(e).__name__}>"


def run_cases(code: str, cases: Mapping[str, Any]) -> dict[str, str]:
    """solve(вход) на представителях каждого класса → repr результата или «<ошибка Тип>».

    Исполняется только шаблонный код семейств — код кандидата сюда не попадает никогда."""
    ns: dict = {"__builtins__": _CASE_BUILTINS}
    exec(compile(code, "<verdict>", "exec"), ns)  # noqa: S102
    return {cls: " | ".join(_run_one(ns["solve"], a) for a in arg) if isinstance(arg, Reps) else _run_one(ns["solve"], arg)
            for cls, arg in cases.items()}


def _schema(tables: Sequence[Table]) -> list:
    return [[t.name, list(t.columns)] for t in tables]


def _differs(results: list) -> bool:
    """Эталон отработал, а показанный запрос упал или вернул другой набор строк (порядок не важен)."""
    ref, shown = results
    if ref is None:
        return False  # данные, на которых падает эталон, ничего не доказывают
    return shown is None or canonical("rows", ref) != canonical("rows", shown)


def sql_differs(sql_key: Mapping, data: Mapping[str, list[list]], *, isolated: bool = True) -> bool:
    payload = {"schema": sql_key["schema"], "data": dict(data), "queries": [sql_key["reference"], sql_key["shown"]]}
    if not isolated or not any(data.values()):  # свои данные-свидетели или пустые таблицы: чужих значений нет
        return _differs(run_payload(payload))
    try:
        out = subprocess.run([sys.executable, "-m", "app.assessment.bank.sql_isolated"], input=json.dumps(payload),
                             capture_output=True, text=True, cwd=BACKEND_DIR, timeout=PARAMS.ai_sql_timeout_s,
                             check=True, env=safe_env(), preexec_fn=child_limits(SQL_MEM_MB))
        return _differs(json.loads(out.stdout))
    except subprocess.CalledProcessError as e:
        log.warning("sql_isolated failed (%s): %s", e.returncode, (e.stderr or "")[-500:])
    except subprocess.TimeoutExpired:
        log.warning("sql_isolated timed out after %s s", PARAMS.ai_sql_timeout_s)
    except (subprocess.SubprocessError, ValueError) as e:
        log.warning("sql_isolated: %s", type(e).__name__)
    return False  # сбой проверки — поломка не доказана; в логе видно, что дело не в ответе


# ---------- генерация ----------

def python_verdict(rng: random.Random, flawed: bool, *, text: str, reference: str, mutations: Sequence[Mutation],
                   cases: Mapping[str, Any], clarify: Sequence[str]) -> Generated:
    lines, line = reference.split("\n"), None
    if flawed:
        m = rng.choice(list(mutations))
        lines[m.line - 1], line = m.code, m.line
    shown = "\n".join(lines)
    ref_out, shown_out = run_cases(reference, cases), run_cases(shown, cases)
    if any(v.startswith("<ошибка") for v in ref_out.values()):
        raise ValueError("эталон падает на представителе класса")
    breaks = sorted(c for c in cases if ref_out[c] != shown_out[c])
    if flawed and m.cls not in breaks:  # представитель «своего» класса обязан ловить дефект
        raise ValueError(f"дефект в строке {line} не ломает класс {m.cls}; ломает: {breaks or 'ничего'}")
    opts = list(clarify)
    rng.shuffle(opts)
    return Generated("verdict", VerdictPrompt(
        text=text, code=shown, language="python", input_classes=tuple(c for c in INPUT_CLASSES if c in cases),
        clarify=tuple(opts)),
        {"truth": "defect" if flawed else "ok", "line": line, "breaks": breaks, "sql": None, "clarify": None},
        ("verdict", "python"))


def sql_verdict(rng: random.Random, flawed: bool, *, text: str, tables: Sequence[Table], reference: str,
                mutations: Sequence[Mutation], clarify: Sequence[str]) -> Generated:
    lines, line, witness = reference.split("\n"), None, None
    if flawed:
        m = rng.choice(list(mutations))
        lines[m.line - 1], line = m.code, m.line
        witness = [[t.name, list(t.columns), [list(r) for r in t.rows]] for t in m.witness]
    shown = "\n".join(lines)
    sql = {"schema": _schema(tables), "reference": reference, "shown": shown, "witness": witness}
    if flawed and not sql_differs(sql, {w[0]: w[2] for w in witness}, isolated=False):
        raise ValueError(f"дефект в строке {line}: на данных-свидетеле эталон и решение совпадают")
    opts = list(clarify)
    rng.shuffle(opts)
    return Generated("verdict", VerdictPrompt(text=text, code=shown, language="sql", tables=tuple(tables),
                                              clarify=tuple(opts)),
                     {"truth": "defect" if flawed else "ok", "line": line, "breaks": [], "sql": sql, "clarify": None},
                     ("verdict", "sql"))


def clarify_verdict(rng: random.Random, *, text: str, code: str, language: Literal["python", "sql"],
                    right: str, settled: Sequence[str], input_classes: Sequence[str] = (),
                    tables: Sequence[Table] = ()) -> Generated:
    """Неоднозначное требование: верный ответ — «нужно уточнить» и вариант `right`; `settled` — вопросы,
    на которые требование уже отвечает. Решение реализует одно из толкований и выглядит правдоподобно."""
    opts = [right, *settled]
    rng.shuffle(opts)
    return Generated("verdict", VerdictPrompt(
        text=text, code=code, language=language, tables=tuple(tables),
        input_classes=tuple(c for c in INPUT_CLASSES if c in input_classes), clarify=tuple(opts)),
        {"truth": "ambiguous", "line": None, "breaks": [], "sql": None, "clarify": opts.index(right)},
        ("verdict", language))


# ---------- регистрация ----------

AI_GENERATORS: dict[str, Callable[[random.Random, bool], Generated]] = {}


def ai_family(*, code: str, area: Literal["python", "sql", "clarify"], space_size: int, median_time_s: int):
    """Семейство вердиктов. Генератор получает flawed — быть ли решению дефектным: долю дефектных
    в попытке задаёт план (engine.ai_verdicts.plan_slots). Для конвейера банка (make, check_family)
    flawed выбирается случайно, поэтому проверяются оба варианта."""
    def deco(fn: Callable[[random.Random, bool], Generated]):
        family(code=code, specialization=AI_SPEC, area=area, level=2, fmt="verdict", space_size=space_size,
               median_time_s=median_time_s)(lambda rng: fn(rng, rng.random() < 0.5))
        AI_GENERATORS[code] = fn
        return fn
    return deco


def make_verdict(code: str, seed: int, flawed: bool) -> Instance:
    g = AI_GENERATORS[code](random.Random(seed), flawed)
    return Instance(code, g.kind, g.prompt, canonical(g.kind, g.answer), tuple(g.radicals))


# ---------- ответ кандидата ----------

Cell = str | int | float | None


class VerdictResponse(BaseModel):
    verdict: Literal["ok", "defect", "clarify"]
    confidence: Literal["low", "high"] = "high"  # не отмечена — считаем «высокой»: «низкую» надо заявить
    line: int | None = Field(None, ge=1, le=500)
    input_class: str | None = None
    rows: dict[str, list[list[Cell]]] | None = None
    clarify: int | None = Field(None, ge=0, le=9)


def parse_response(raw: Any) -> VerdictResponse | None:
    try:
        return VerdictResponse.model_validate(raw)
    except ValidationError:
        return None


def _cell(v: Cell) -> Cell:
    if v is None or isinstance(v, bool):
        return None if v is None else int(v)
    if isinstance(v, int | float):
        return v if math.isfinite(v) else None
    s = v.strip()
    if s == "" or s.upper() == "NULL":
        return None
    for conv in (int, lambda x: float(x.replace(",", "."))):
        try:
            n = conv(s)
            return n if math.isfinite(n) else s
        except ValueError:
            pass
    return s


def sql_data(schema: Sequence, rows: Mapping[str, list[list[Cell]]]) -> dict[str, list[list[Cell]]] | None:
    """Данные кандидата в таблицы схемы; None — если нарушены форма или лимиты (это просто неверный ответ)."""
    cols = {name: len(columns) for name, columns in schema}
    if set(rows) - set(cols) or sum(len(r) for r in rows.values()) > PARAMS.sql_input_max_rows:
        return None
    out = {}
    for name, table_rows in rows.items():
        if any(len(r) != cols[name] for r in table_rows):
            return None
        if any(isinstance(c, str) and len(c) > CELL_MAX for r in table_rows for c in r):
            return None
        out[name] = [[_cell(c) for c in r] for r in table_rows]
    return out


def check_verdict(key: Mapping, raw: Any, *, isolated: bool = True) -> bool:
    """Ответ полностью верен: вердикт, а для дефекта — строка и ломающий вход, для неоднозначного — уточнение."""
    r = parse_response(raw)
    if r is None:
        return False
    truth = key["truth"]
    if truth == "ok":
        return r.verdict == "ok"
    if truth == "ambiguous":
        return r.verdict == "clarify" and r.clarify == key["clarify"]
    if r.verdict != "defect" or r.line != key["line"]:
        return False
    if key["sql"] is None:
        return r.input_class in key["breaks"]
    data = sql_data(key["sql"]["schema"], r.rows or {})
    return data is not None and sql_differs(key["sql"], data, isolated=isolated)


def ideal_response(key: Mapping) -> dict:
    """Эталонный ответ по ключу: самопроверка конвейера банка и тесты."""
    if key["truth"] == "ok":
        return {"verdict": "ok", "confidence": "high"}
    if key["truth"] == "ambiguous":
        return {"verdict": "clarify", "clarify": key["clarify"], "confidence": "high"}
    out = {"verdict": "defect", "line": key["line"], "confidence": "high"}
    if key["sql"] is None:
        return out | {"input_class": key["breaks"][0]}
    return out | {"rows": {name: rows for name, _cols, rows in key["sql"]["witness"]}}


def roundtrip(inst: Instance) -> bool:
    """Ключ проходит собственную проверку, а «принять всё» верно только для верного решения."""
    key = inst.answer
    accept_ok = check_verdict(key, {"verdict": "ok"}, isolated=False)
    return check_verdict(key, ideal_response(key), isolated=False) and accept_ok == (key["truth"] == "ok")
