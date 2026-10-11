import random

import pytest

from app.assessment.bank.base import REGISTRY, Generated, Prompt, clear_registry, family
from app.assessment.bank.families import load_all
from app.assessment.skills import SKILLS, skill_spec


def _toy(rng: random.Random) -> Generated:
    a, b = rng.randint(1, 10**6), rng.randint(1, 10**6)
    return Generated("number", Prompt(text=f"{a} + {b} = ?"), a + b, ("toy",))


@pytest.fixture
def toy_skill_bank():
    """Учебный банк SQL-навыка: 10 семейств, уровни 1–4, обе области (как toy_bank плана 03)."""
    load_all()
    saved = dict(REGISTRY)
    clear_registry()
    layout = [("query", 1), ("model", 1), ("query", 2), ("model", 2), ("query", 2), ("model", 2), ("query", 3),
              ("model", 3), ("query", 3), ("model", 4)]
    for i, (area, lv) in enumerate(layout):
        family(code=f"toy.sk.sql.{i}", specialization=skill_spec("sql"), area=area, level=lv, fmt="toy",
               space_size=10**6, median_time_s=30)(_toy)
    assert set(SKILLS["sql"].areas) == {"query", "model"}
    yield
    clear_registry()
    REGISTRY.update(saved)
