import random

import pytest

from app.assessment.bank.base import (
    REGISTRY,
    Generated,
    Prompt,
    Table,
    clear_registry,
    families,
    family,
    mcq,
    rows_space,
    template_fields,
)
from app.assessment.bank.canon import is_correct


@pytest.fixture
def toy_registry():
    saved = dict(REGISTRY)
    clear_registry()

    @family(code="toy.add", specialization="backend", area="lang", level=1, fmt="output",
            space_size=10**6, median_time_s=20)
    def toy(rng: random.Random) -> Generated:
        a, b = rng.randint(1, 999), rng.randint(1, 999)
        return Generated("number", Prompt(text=f"Сколько будет {a} + {b}?"), a + b, ("add",))

    yield
    clear_registry()
    REGISTRY.update(saved)


def test_make_is_deterministic_and_public_hides_answer(toy_registry):
    f = REGISTRY["toy.add"]
    i1, i2 = f.make(42), f.make(42)
    assert i1 == i2 and "answer" not in i1.public() and i1.public()["prompt"]["text"]
    assert i1.key()["answer"] == i1.answer
    assert is_correct(i1, str(int(i1.answer))) and not is_correct(i1, "-1")
    assert is_correct(i1, "что-то не то") is False


def test_registry_filters_and_rejects_duplicates(toy_registry):
    assert [f.code for f in families("backend")] == ["toy.add"]
    with pytest.raises(ValueError):
        family(code="toy.add", specialization="backend", area="lang", level=1, fmt="output",
               space_size=1, median_time_s=1)(lambda rng: None)


def test_mcq_shuffles_and_points_to_correct():
    t = Table("t", ("id",), ((1,),))
    seen = set()
    for seed in range(40):
        g = mcq(random.Random(seed), "Вопрос?", "верно", ("а", "б", "в"), code="SELECT 1;",
                language="sql", tables=[t])
        assert g.kind == "choice" and g.prompt.options[g.answer] == "верно"
        assert sorted(g.prompt.options) == sorted(("верно", "а", "б", "в"))
        assert g.prompt.code == "SELECT 1;" and g.prompt.language == "sql" and g.prompt.tables == (t,)
        assert g.radicals == ("mcq", 4) and g.prompt.answer_hint == "Один вариант"
        seen.add(g.answer)
    assert seen == {0, 1, 2, 3}
    g = mcq(random.Random(1), "Вопрос?", "x", ("y", "z", "w"), radicals=("own", 4))
    assert g.radicals == ("own", 4) and g.prompt.code is None and g.prompt.language is None


def test_rows_space_counts_only_used_fields():
    rows = ((("{a} и {b}", "только {a}"), "верно", ("д1", "д2", "д3")),
            (("{a}, {b} и {c}",), "верно2", ("д1", "д2", "д3")))
    sizes = {"a": 2, "b": 3, "c": 5}
    assert template_fields("{a} и {{литерал}} {b}") == {"a", "b"}
    assert rows_space(rows, sizes) == (2 * 3 + 2 + 2 * 3 * 5) * 24
    assert rows_space(rows, sizes, extra=1, dependent=frozenset({"b"})) == 2 + 2 + 2 * 5
