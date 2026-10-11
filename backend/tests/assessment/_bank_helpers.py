"""Общие помощники семантических тестов банка (не зависят от генераторов): все специализации."""
import re
from collections import Counter

from app.assessment.bank.base import REGISTRY, Instance
from app.assessment.bank.families import load_all

load_all()


def make(code: str, seed: int) -> Instance:
    return REGISTRY[code].make(seed)


def area_codes(area: str, specialization: str = "backend") -> list[str]:
    return sorted(c for c, f in REGISTRY.items() if f.specialization == specialization and f.area == area)


def kind_codes(specialization: str, kind: str) -> list[str]:
    """Семейства специализации с данным типом ответа (по экземпляру 0)."""
    return sorted(c for c, f in REGISTRY.items() if f.specialization == specialization and f.make(0).kind == kind)


def template_regex(template: str) -> re.Pattern:
    """Шаблон str.format -> regexp: каждое {поле} = любой фрагмент, {{ и }} — литеральные скобки."""
    t = template.replace("{{", "\x01").replace("}}", "\x02")
    pat = re.sub(r"\\\{\w+\\\}", "(.+?)", re.escape(t))
    return re.compile(pat.replace("\x01", r"\{").replace("\x02", r"\}"), re.S)


def row_for(text: str, rows):
    """Строка таблицы сценариев, чей шаблон дал этот текст (независимо от генератора)."""
    hits = [r for r in rows if any(template_regex(t).fullmatch(text) for t in r[0])]
    assert len(hits) == 1, text
    return hits[0]


# --- форма MCQ: ключ не угадывается по длине, позиции и первому слову ---------------------------
def _first_word(option: str) -> str:
    return option.split()[0]


def unique_extreme(lens: list[int], key: int, pick) -> bool:
    """Ключ — единственный самый длинный (pick=max) или единственный самый короткий (pick=min)."""
    return lens[key] == pick(lens) and lens.count(pick(lens)) == 1


def prefix_cue(options, key: int) -> bool:
    """Три дистрактора начинаются одним словом, а ключ — другим: ключ виден по началу."""
    others = {_first_word(o) for i, o in enumerate(options) if i != key}
    return len(others) == 1 and _first_word(options[key]) not in others


def assert_mcq_form(code: str, seeds=range(200)) -> None:
    n = len(seeds)
    longest = shortest = prefix = 0
    positions = Counter()
    for seed in seeds:
        inst = make(code, seed)
        opts = inst.prompt.options
        assert len(opts) == 4 and len(set(opts)) == 4, opts
        assert 0 <= inst.answer < 4
        lens = [len(o) for o in opts]
        longest += unique_extreme(lens, inst.answer, max)
        shortest += unique_extreme(lens, inst.answer, min)
        prefix += prefix_cue(opts, inst.answer)
        positions[inst.answer] += 1
    assert set(positions) == {0, 1, 2, 3} and max(positions.values()) <= 0.4 * n, (code, positions)
    assert longest <= 0.5 * n, (code, "ключ — единственный самый длинный", longest / n)
    assert shortest <= 0.5 * n, (code, "ключ — единственный самый короткий", shortest / n)
    assert prefix <= 0.1 * n, (code, "ключ выделяется первым словом", prefix / n)


def assert_area_mcq_lengths(codes: list[str], label: str) -> None:
    n = longest = shortest = 0
    for code in codes:
        for seed in range(100):
            inst = make(code, seed)
            lens = [len(o) for o in inst.prompt.options]
            longest += unique_extreme(lens, inst.answer, max)
            shortest += unique_extreme(lens, inst.answer, min)
            n += 1
    assert longest <= 0.4 * n and shortest <= 0.4 * n, (label, longest / n, shortest / n)


# --- текстовые ответы: формат записи не влияет на зачёт, содержание — влияет ---------------------
def format_variants(key: str) -> list[str]:
    """Та же запись в ином, но допустимом формате: как её мог бы набрать кандидат."""
    out = [key.replace(", ", ","), re.sub(r"([\[(])", r"\1 ", key).replace("]", " ]"),
           key.replace(", ", " , ")]
    if re.fullmatch(r"0\d:\d\d:\d\d", key):
        out.append(key[1:])
    return out


def content_change(key: str) -> str:
    """Та же форма, другое содержание: меняем последнюю цифру (или добавляем символ)."""
    m = list(re.finditer(r"\d", key))
    if not m:
        return key + "x"
    i = m[-1].start()
    return key[:i] + str((int(key[i]) + 1) % 10) + key[i + 1:]
