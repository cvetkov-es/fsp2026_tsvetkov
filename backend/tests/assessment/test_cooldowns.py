from datetime import UTC, datetime, timedelta

from app.assessment.engine.cooldowns import (
    GradeAttemptRecord,
    grade_test_availability,
    skill_test_availability,
)
from app.assessment.engine.levels import Grade
from app.assessment.engine.rules import Decision

D0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
FAILED_M = GradeAttemptRecord(Grade.middle, D0, Decision.not_confirmed, False)


def day(n):
    return D0 + timedelta(days=n)


def test_lower_grade_immediately_after_failure():
    a = grade_test_availability(Grade.junior, [FAILED_M], None, False, D0)
    assert a.allowed


def test_same_grade_after_30_days():
    assert not grade_test_availability(Grade.middle, [FAILED_M], None, False, day(29)).allowed
    a = grade_test_availability(Grade.middle, [FAILED_M], None, False, day(30))
    assert a.allowed


def test_process_example_strictest_rule():
    conf_j = GradeAttemptRecord(Grade.junior, D0, Decision.confirmed, False)
    hist = [FAILED_M, conf_j]
    a = grade_test_availability(Grade.middle, hist, Grade.junior, False, day(31))
    assert not a.allowed and a.available_at == day(90) and "cooldown_up" in a.reasons
    conf_j_confident = GradeAttemptRecord(Grade.junior, D0, Decision.confirmed, True)
    a2 = grade_test_availability(Grade.middle, [FAILED_M, conf_j_confident], Grade.junior, False, day(31))
    assert a2.allowed and a2.available_at == day(30)


def test_votes_unlock_removes_only_cooldown_up():
    conf_j = GradeAttemptRecord(Grade.junior, D0, Decision.confirmed, False)
    a = grade_test_availability(Grade.middle, [conf_j], Grade.junior, True, day(1))
    assert a.allowed
    a2 = grade_test_availability(Grade.middle, [FAILED_M, conf_j], Grade.junior, True, day(1))
    assert not a2.allowed and a2.available_at == day(30)


def test_incomplete_attempts_ignored():
    incomplete = GradeAttemptRecord(Grade.middle, D0, None, False)
    assert grade_test_availability(Grade.middle, [incomplete], None, False, D0).allowed


def test_skill_cooldown_14_days():
    assert not skill_test_availability(D0, day(13)).allowed
    assert skill_test_availability(D0, day(14)).allowed
    assert skill_test_availability(None, D0).allowed
