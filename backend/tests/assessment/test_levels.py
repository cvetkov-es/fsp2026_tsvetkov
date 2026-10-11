import pytest

from app.assessment.engine.levels import (
    PHASE1_BAND,
    PHASE2_BAND,
    Grade,
    Thresholds,
    grade_rank,
    level_b,
)
from app.config.params import PARAMS


def test_thresholds_from_params():
    t = Thresholds.from_params(PARAMS)
    assert t.cut(Grade.junior) == pytest.approx(-0.29, abs=0.01)
    assert t.next_cut(Grade.junior) == pytest.approx(t.cut(Grade.middle))
    assert t.next_cut(Grade.senior) == pytest.approx(t.cut(Grade.senior) + 1.0)
    assert t.version == "expert-1"


def test_bands_and_levels():
    assert PHASE1_BAND[Grade.middle] == (2, 3, 4) and PHASE2_BAND[Grade.senior] == (4, 5)
    assert level_b(3, PARAMS) == 0.0
    assert grade_rank(Grade.junior) < grade_rank(Grade.senior)
