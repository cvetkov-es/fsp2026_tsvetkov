import pytest

from app.assessment.bank.base import REGISTRY, clear_registry
from app.assessment.bank.families import load_all

from .toys import register_toys


@pytest.fixture
def toy_verdicts():
    load_all()  # реальные модули попадают в кэш импорта до очистки реестра
    saved = dict(REGISTRY)
    clear_registry()
    register_toys({"python": 1, "sql": 1, "clarify": 1})
    yield
    clear_registry()
    REGISTRY.update(saved)
