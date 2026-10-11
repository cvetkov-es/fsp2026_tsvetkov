"""Семейства заданий (item families): генератор от rng → экземпляр с вычисленным ответом."""
import random
import string
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal

from app.assessment.bank.canon import canonical

AnswerKind = Literal["number", "text", "choice", "line", "order", "rows", "verdict"]


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True)
class Prompt:
    text: str
    code: str | None = None
    language: str | None = None
    options: tuple[str, ...] | None = None
    tables: tuple[Table, ...] = ()
    steps: tuple[str, ...] | None = None
    answer_hint: str | None = None


@dataclass(frozen=True)
class Generated:
    kind: AnswerKind
    prompt: Prompt
    answer: Any
    radicals: tuple = ()


@dataclass(frozen=True)
class Instance:
    family_code: str
    kind: AnswerKind
    prompt: Prompt
    answer: Any
    radicals: tuple = ()

    def public(self) -> dict:
        """То, что уходит клиенту. Ключа ответа здесь нет и быть не должно."""
        # Код семейства не отдаём: по имени вроде avg_ignores_null виден подвох задания
        return {"kind": self.kind, "prompt": asdict(self.prompt)}

    def key(self) -> dict:
        """instance_json: хранится только на сервере (апелляции, проверка ответа)."""
        return {"family_code": self.family_code, "public": self.public(), "answer": self.answer,
                "radicals": list(self.radicals)}


@dataclass(frozen=True)
class Family:
    code: str
    specialization: str
    area: str
    level: int
    fmt: str
    space_size: int
    median_time_s: int
    generator: Callable[[random.Random], Generated]
    b_offset: float = 0.0

    def make(self, seed: int) -> Instance:
        g = self.generator(random.Random(seed))
        return Instance(self.code, g.kind, g.prompt, canonical(g.kind, g.answer), tuple(g.radicals))

    def b(self, b_levels: Sequence[float]) -> float:
        return b_levels[self.level - 1] + self.b_offset


REGISTRY: dict[str, Family] = {}


def family(*, code: str, specialization: str, area: str, level: int, fmt: str,
           space_size: int, median_time_s: int, b_offset: float = 0.0):
    if code in REGISTRY:
        raise ValueError(f"семейство {code} уже зарегистрировано")

    def deco(fn: Callable[[random.Random], Generated]):
        REGISTRY[code] = Family(code, specialization, area, level, fmt, space_size,
                                median_time_s, fn, b_offset)
        return fn

    return deco


# --- общие помощники семейств (области не импортируют друг друга, только base) -------------
SHUFFLES = 24  # порядок четырёх вариантов MCQ: 4!


def mcq(rng: random.Random, text: str, correct: str, distractors: Iterable[str], *,
        code: str | None = None, language: str | None = None, tables: Sequence[Table] = (),
        radicals: tuple | None = None) -> Generated:
    """Сборка MCQ: правильный вариант + дистракторы, порядок перемешан, ключ — индекс правильного."""
    options = [correct, *distractors]
    rng.shuffle(options)
    return Generated(
        "choice",
        Prompt(text=text, code=code, language=language, options=tuple(options), tables=tuple(tables),
               answer_hint="Один вариант"),
        options.index(correct), radicals or ("mcq", len(options)),
    )


def template_fields(template: str) -> set[str]:
    """Имена подстановок {поле} в шаблоне str.format."""
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


def rows_space(rows: Iterable[tuple], sizes: Mapping[str, int], *, extra: int = SHUFFLES,
               dependent: frozenset[str] = frozenset()) -> int:
    """Честный подсчёт для таблицы сценариев (шаблоны, правильный, дистракторы, …).

    Сумма по всем шаблонам всех строк произведения размеров только используемых подстановок,
    умноженная на `extra` (по умолчанию — порядок четырёх вариантов). `dependent` — поля, значения
    которых целиком определяются другим полем (берутся кортежем) и отдельно не считаются."""
    total = 0
    for templates, *_ in rows:
        for template in templates:
            n = 1
            for f in template_fields(template) - dependent:
                n *= sizes[f]
            total += n
    return total * extra


def families(specialization: str | None = None) -> list[Family]:
    return [f for f in REGISTRY.values() if specialization is None or f.specialization == specialization]


def clear_registry() -> None:
    REGISTRY.clear()
