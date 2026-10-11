import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import load_all

load_all()


@pytest.mark.slow
@pytest.mark.parametrize("code", sorted(REGISTRY))
def test_every_family_passes_full_pipeline(code):
    r = check_family(REGISTRY[code])
    assert r.ok, r.errors
