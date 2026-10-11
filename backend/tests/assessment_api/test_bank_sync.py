from sqlalchemy import select

from app.assessment.bank_sync import ensure_thresholds, sync_bank
from app.assessment.models import ItemFamilyRow, ThresholdsRow
from app.config.params import PARAMS


def test_sync_upserts_and_keeps_exposure(db, toy_bank):
    assert sync_bank(db) == 75
    row = db.get(ItemFamilyRow, "toy.db.3.0")
    assert row.b == PARAMS.b_levels[2] and row.status == "active"
    row.exposure_count = 7
    db.commit()
    sync_bank(db)
    assert db.get(ItemFamilyRow, "toy.db.3.0").exposure_count == 7


def test_missing_families_retired(db, toy_bank):
    sync_bank(db)
    db.add(ItemFamilyRow(code="gone.x", specialization="backend", area="db", level=1, fmt="x",
                         b=-2.0, median_time_s=10))
    db.commit()
    sync_bank(db)
    assert db.get(ItemFamilyRow, "gone.x").status == "retired"


def test_thresholds_expert_version(db):
    ensure_thresholds(db)
    ensure_thresholds(db)
    rows = db.scalars(select(ThresholdsRow)).all()
    assert [r.version for r in rows] == ["expert-1"]
    assert rows[0].cut_m == PARAMS.cut_m
