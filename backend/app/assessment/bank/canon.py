"""Канонизация ответов: терпимость к формату, строгость к содержанию."""
import math
import re
from typing import Any


class CanonError(ValueError):
    pass


def _finite(x: float, raw: Any) -> float:
    if not math.isfinite(x):
        raise CanonError(str(raw)[:40])
    return round(x, 6)


def _number(raw: Any) -> float:
    if isinstance(raw, bool):
        raise CanonError("bool")
    try:
        if isinstance(raw, int | float):
            return _finite(float(raw), raw)
        s = str(raw).strip().replace(" ", "").replace(" ", "").replace(",", ".")
        # «92,3%» в задании «доля в процентах» — тот же ответ; ответ-долю 0.923 знак процента не делает верным
        return _finite(float(s.removesuffix("%")), raw)
    except (ValueError, OverflowError) as e:  # «около пяти», 10**400
        raise CanonError(str(raw)[:40]) from e


def _int(raw: Any) -> int:
    n = _number(raw)
    if n != int(n):
        raise CanonError(str(raw)[:40])
    return int(n)


# Применяются после схлопывания пробелов: между токенами не больше одного пробела, поэтому шаблоны
# ждут ровно один необязательный пробел и не откатываются (линейное время на ответе любой длины).
_COMMA = re.compile(r" ?, ?")
_AFTER_OPEN = re.compile(r"([\[({]) ")
_BEFORE_CLOSE = re.compile(r" ([\])}])")
_CLOCK_ONE_DIGIT_HOUR = re.compile(r"\d:\d{2}:\d{2}")


def _text_line(line: str) -> str:
    """Строка вывода: пробелы схлопнуты; «[25,25]», «[ 25 , 25 ]» → «[25, 25]»; «7:05:09» → «07:05:09»."""
    s = re.sub(r"\s+", " ", line).strip()  # любые пробельные (NBSP, U+2003, \r, \v, \f) → один пробел
    s = _COMMA.sub(", ", s)
    s = _AFTER_OPEN.sub(r"\1", s)
    s = _BEFORE_CLOSE.sub(r"\1", s).strip()
    if _CLOCK_ONE_DIGIT_HOUR.fullmatch(s):
        s = "0" + s
    return s


def _text(raw: Any) -> str:
    lines = str(raw).replace("\r\n", "\n").strip().split("\n")
    return "\n".join(_text_line(ln) for ln in lines)


def _order(raw: Any) -> tuple[int, ...]:
    if isinstance(raw, str) and re.fullmatch(r"\s*\d{2,9}\s*", raw):
        parts: list[Any] = list(raw.strip())  # «312645» — номера шагов без разделителей
    else:
        parts = re.findall(r"\d+", raw) if isinstance(raw, str) else list(raw)
    if not parts:
        raise CanonError("empty order")
    return tuple(_int(p) for p in parts)


def _cell(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, int | float) and not isinstance(v, bool):
        try:
            return _finite(float(v), v)
        except OverflowError as e:
            raise CanonError(str(v)[:40]) from e
    s = re.sub(r"\s+", " ", str(v)).strip()
    if s == "" or s.upper() == "NULL":
        return None
    try:
        return _finite(float(s.replace(",", ".")), s)
    except (ValueError, OverflowError, CanonError):
        return s.casefold()  # процесс 2.4: терпимы к пробелам и регистру


def _rows(raw: Any) -> tuple:
    return tuple(sorted((tuple(_cell(c) for c in r) for r in raw), key=repr))


def _verdict(raw: Any) -> dict:
    """Ключ вердикта «Работы с ИИ» (не ответ кандидата: его проверяет bank.verdicts.check_verdict)."""
    if not isinstance(raw, dict) or raw.get("truth") not in ("ok", "defect", "ambiguous"):
        raise CanonError("verdict key")
    return {"truth": raw["truth"], "line": raw.get("line"), "breaks": sorted(raw.get("breaks") or []),
            "sql": raw.get("sql"), "clarify": raw.get("clarify")}


_DISPATCH = {
    "number": _number, "text": _text, "choice": _int, "line": _int, "order": _order, "rows": _rows,
    "verdict": _verdict,
}


def canonical(kind: str, raw: Any) -> Any:
    return _DISPATCH[kind](raw)


def is_correct(instance, raw: Any) -> bool:
    """Любой мусор от кандидата — просто неверный ответ, а не 500."""
    try:
        return canonical(instance.kind, raw) == instance.answer
    except (CanonError, TypeError, ValueError, OverflowError):
        return False
