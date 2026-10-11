from collections import Counter

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.families import load_all
from app.assessment.skills import SKILLS, skill_spec
from app.config.params import PARAMS

load_all()
LEVELS = {1: 2, 2: 4, 3: 3, 4: 1}  # 10 семейств на навык вокруг SKILL_CUT


@pytest.mark.parametrize("code", sorted(SKILLS))
def test_skill_banks_volume(code):
    fams = [f for f in REGISTRY.values() if f.specialization == skill_spec(code)]
    assert len(fams) == PARAMS.families_per_skill
    assert Counter(f.level for f in fams) == Counter(LEVELS)
    areas = Counter(f.area for f in fams)
    assert set(areas) == set(SKILLS[code].areas) and min(areas.values()) >= 4
    assert not any(f.code.startswith(("be.", "fe.", "da.")) for f in fams)
