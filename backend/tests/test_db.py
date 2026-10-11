from datetime import UTC, datetime

from sqlalchemy import text

from app.common import clock


def test_db_roundtrip(db):
    assert db.execute(text("select 1")).scalar() == 1


def test_arrays_and_jsonb_supported(db):
    db.execute(text("create temporary table t (a text[], j jsonb)"))
    db.execute(text("insert into t values ('{x,y}', '{\"k\": 1}')"))
    a, j = db.execute(text("select a, j from t")).one()
    assert a == ["x", "y"] and j == {"k": 1}


def test_clock_override(frozen_now):
    fixed = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
    frozen_now(fixed)
    assert clock.now() == fixed
