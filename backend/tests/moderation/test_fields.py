from sqlalchemy import inspect

from app.config.params import PARAMS


def test_new_fields_for_junior_trust_and_helper(db):
    insp = inspect(db.get_bind())

    def cols(table):
        return {c["name"] for c in insp.get_columns(table)}

    assert "birth_date" in cols("users")
    assert {"guardian_email", "guardian_consent_at"} <= cols("candidate_profiles")
    assert "legal_name" in cols("companies")
    assert "employment" in cols("needs")
    employment = next(c for c in insp.get_columns("needs") if c["name"] == "employment")
    assert "full" in str(employment["default"])  # строки, добавленные до миграции, не остаются с NULL
    assert "hours_per_week" in cols("contacts")
    assert {"company_id", "contact_id", "questions", "at"} <= cols("helper_uses")


def test_new_params():
    assert (PARAMS.adult_age, PARAMS.minor_hours_week, PARAMS.minor_school_factor) == (18, (24, 35), 0.5)
    assert (PARAMS.guardian_token_ttl_days, PARAMS.helper_questions, PARAMS.art16_days) == (7, 10, 30)
