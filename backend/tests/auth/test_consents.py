from sqlalchemy import select

from app.auth.consents import CONSENT_TEXTS, DISTRIBUTION_PRESETS, ConsentType, record_consent
from app.auth.models import Consent, Role, User


def test_all_four_consent_texts_exist_with_versions():
    assert set(CONSENT_TEXTS) == set(ConsentType)
    for t in CONSENT_TEXTS.values():
        assert t.version and len(t.body) > 200


def test_standard_preset_never_shows_name_or_contacts():
    std = DISTRIBUTION_PRESETS["standard"]
    assert std["full_name"] == "deny" and std["contacts"] == "deny"
    assert std["grade"] == "allow" and std["stack"] == "allow"


def test_record_consent_persists_version(db):
    u = User(email="a@b.ru", role=Role.candidate)
    db.add(u)
    db.flush()
    c = record_consent(db, u.id, ConsentType.processing)
    db.flush()
    row = db.scalars(select(Consent).where(Consent.user_id == u.id)).one()
    assert row.id == c.id and row.version == CONSENT_TEXTS[ConsentType.processing].version
    assert row.revoked_at is None
