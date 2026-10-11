import random

import pytest

from app.assessment.bank.areas import AREAS
from app.assessment.bank.base import REGISTRY, Generated, Prompt, clear_registry, family
from app.assessment.bank.families import load_all
from app.auth.models import Role, User
from app.auth.service import create_session
from app.common import clock


def _toy(rng: random.Random) -> Generated:
    a, b = rng.randint(1, 10**6), rng.randint(1, 10**6)
    return Generated("number", Prompt(text=f"{a} + {b} = ?"), a + b, ("toy",))


@pytest.fixture
def toy_bank():
    load_all()  # реальные модули попадают в кэш импорта до очистки реестра
    saved = dict(REGISTRY)
    clear_registry()
    for area in AREAS["backend"]:
        for lv in range(1, 6):
            for i in range(3):
                family(code=f"toy.{area}.{lv}.{i}", specialization="backend", area=area, level=lv,
                       fmt="toy", space_size=10**6, median_time_s=30)(_toy)
    yield
    clear_registry()
    REGISTRY.update(saved)


@pytest.fixture
def candidate_login(client, db):
    def _login(email="cand@x.ru", specialization="backend", grade="middle") -> User:
        u = User(email=email, role=Role.candidate, password_hash="x", email_verified_at=clock.now())
        db.add(u)
        db.commit()
        client.cookies.set("fsp_session", create_session(db, u))
        client.put("/api/v1/candidate/profile/survey",
                   json={"specialization": specialization, "claimed_grade": grade})
        return u

    return _login
