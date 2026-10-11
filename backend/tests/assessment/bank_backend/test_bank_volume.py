# backend/tests/assessment/bank_backend/test_bank_volume.py
from collections import Counter

from app.assessment.bank.areas import AREAS
from app.assessment.bank.base import REGISTRY
from app.assessment.bank.families import load_all
from app.config.params import PARAMS

load_all()


def test_backend_cells_match_params():
    cells = Counter((f.area, f.level) for f in REGISTRY.values() if f.specialization == "backend")
    for area in AREAS["backend"]:
        for level in range(1, 6):
            need = PARAMS.families_per_cell_cut if level in (2, 3, 4) else PARAMS.families_per_cell
            assert cells[(area, level)] == need, (area, level, cells[(area, level)])


def test_output_share_at_high_levels():
    high = [f for f in REGISTRY.values() if f.specialization == "backend" and f.level >= 4]
    share = sum(f.fmt == "output" for f in high) / len(high)
    assert share <= PARAMS.d45_output_share
