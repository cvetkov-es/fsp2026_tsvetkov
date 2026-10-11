# backend/tests/assessment/test_bank_volume_all.py
from collections import Counter

import pytest

from app.assessment.bank.areas import AREAS
from app.assessment.bank.base import REGISTRY
from app.assessment.bank.families import load_all
from app.config.params import PARAMS

load_all()


@pytest.mark.parametrize("spec", ["backend", "frontend", "data"])
def test_cells_match_params(spec):
    cells = Counter((f.area, f.level) for f in REGISTRY.values() if f.specialization == spec)
    for area in AREAS[spec]:
        for level in range(1, 6):
            need = PARAMS.families_per_cell_cut if level in (2, 3, 4) else PARAMS.families_per_cell
            assert cells[(area, level)] == need, (spec, area, level, cells[(area, level)])


@pytest.mark.parametrize("spec", ["backend", "frontend", "data"])
def test_output_share_at_high_levels(spec):
    high = [f for f in REGISTRY.values() if f.specialization == spec and f.level >= 4]
    assert sum(f.fmt == "output" for f in high) / len(high) <= PARAMS.d45_output_share
