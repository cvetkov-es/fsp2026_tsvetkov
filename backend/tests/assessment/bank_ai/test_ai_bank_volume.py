from collections import Counter

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.families import load_all
from app.assessment.bank.verdicts import AI_SPEC
from app.assessment.engine.ai_verdicts import slots_needed
from app.config.params import PARAMS

load_all()
PREFIX = {"python": "ai.py.", "sql": "ai.sql.", "clarify": "ai.clarify."}


def test_ai_bank_volume():
    fams = [f for f in REGISTRY.values() if f.specialization == AI_SPEC]
    assert len(fams) == PARAMS.ai_families == 30
    areas = Counter(f.area for f in fams)
    assert areas == {"python": 14, "sql": 10, "clarify": 6}
    assert all(areas[a] >= 2 * n for a, n in slots_needed().items())  # пересдача — на невиданных семействах
    assert all(f.code.startswith(PREFIX[f.area]) and f.fmt == "verdict" for f in fams)
