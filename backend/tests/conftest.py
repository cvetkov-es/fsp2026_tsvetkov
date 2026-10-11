import os
import tempfile
from collections.abc import Iterator
from datetime import timedelta

import pgserver
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.all_models  # noqa: F401  — регистрирует таблицы
from app.auth.consents import DISTRIBUTION_PRESETS, ConsentType, record_consent
from app.auth.models import Role, User
from app.candidates.models import CandidateProfile, CandidateStack
from app.common import clock
from app.db.base import Base
from app.db.session import get_db
from app.llm.deps import disabled_llm, get_llm

# Тесты проверяют демо-сценарии (verify_url, /demo/*); в бою режим выключен по умолчанию
os.environ.setdefault("DEMO_MODE", "true")
# NER natasha (подпроцесс ~2 с) включают только тесты, которые проверяют именно его
os.environ.setdefault("NER_ENABLED", "false")


@pytest.fixture(scope="session")
def engine():
    datadir = tempfile.mkdtemp(prefix="fsp-test-pg-")
    server = pgserver.get_server(datadir, cleanup_mode="delete")
    uri = server.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
    eng = create_engine(uri)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Iterator[Session]:
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def client(db) -> Iterator[TestClient]:
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    # LLM в API-тестах выключен, даже если в .env разработчика есть ключ; фейк подставляет сам тест
    app.dependency_overrides[get_llm] = disabled_llm
    with TestClient(app, headers={"X-Requested-With": "fsp"}) as c:
        yield c


@pytest.fixture
def frozen_now():
    def _set(value):
        clock.set_now(value)

    yield _set
    clock.set_now(None)


@pytest.fixture
def make_candidate(db):
    counter = {"n": 0}

    def _make(grade="middle", status="confirmed", s=0.6, stack=(), formats=("remote",), city="Казань",
              preset="standard", fsp_f=0.0, fsp_summary=None, threshold=200000, spec="backend"):
        counter["n"] += 1
        u = User(email=f"cand{counter['n']}@x.ru", role=Role.candidate, password_hash="x",
                 email_verified_at=clock.now())
        db.add(u)
        db.flush()
        record_consent(db, u.id, ConsentType.distribution,
                       scope={"preset": preset, "fields": DISTRIBUTION_PRESETS[preset]})
        p = CandidateProfile(user_id=u.id, specialization=spec, claimed_grade=grade, grade_status=status,
                             confirmed_grade=grade if status == "confirmed" else None, theta=1.0, se=0.4,
                             s_cache=s, formats=list(formats), city=city, salary_threshold=threshold,
                             salary_gross_net="net", open_until=clock.now() + timedelta(days=7),
                             last_activity_at=clock.now(), fsp_f=fsp_f,
                             fsp_status="LINKED" if fsp_summary else "NOT_LINKED", fsp_summary=fsp_summary,
                             full_name=f"Секретное Имя {counter['n']}", contacts={"phone": "+79990000000"})
        db.add(p)
        db.add_all(CandidateStack(user_id=u.id, tech=t) for t in stack)
        db.commit()
        return p

    return _make


def _with_toys(copies: dict[str, int]):
    from app.assessment.bank.base import REGISTRY, clear_registry
    from app.assessment.bank.families import load_all
    from tests.assessment.bank_ai.toys import register_toys

    load_all()  # реальные модули попадают в кэш импорта до очистки реестра
    saved = dict(REGISTRY)
    clear_registry()
    register_toys(copies)
    yield
    clear_registry()
    REGISTRY.update(saved)


@pytest.fixture
def toy_ai_bank():
    """Учебный банк «Работы с ИИ»: на одно семейство больше нужного в каждой области."""
    yield from _with_toys({"python": 7, "sql": 5, "clarify": 3})


@pytest.fixture
def toy_ai_bank_short():
    """Неоднозначных требований меньше, чем нужно на попытку."""
    yield from _with_toys({"python": 6, "sql": 4, "clarify": 1})
