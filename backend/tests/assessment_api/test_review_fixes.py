"""Регрессии по итогам финального ревью плана 03."""
import time
import uuid
from datetime import UTC, datetime, timedelta
from threading import Barrier, BrokenBarrierError, Thread

import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.assessment import service as svc
from app.assessment.bank.base import REGISTRY
from app.assessment.bank_sync import ensure_thresholds, sync_bank
from app.assessment.models import Attempt, AttemptItem, ItemFamilyRow, ThresholdsRow
from app.assessment.schemas import AnswerIn, StartIn
from app.auth.models import Consent, Role, User
from app.candidates.models import CandidateProfile
from app.common import clock
from app.config.params import PARAMS
from tests.assessment_api.helpers import answer_current

START = {"target_grade": "middle", "accept_rules": True, "pledge": True}
T0 = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)


def start(client, **kw):
    return client.post("/api/v1/candidate/attempts", json={**START, **kw}).json()["id"]


def keep_only(pred):
    for code in [c for c in REGISTRY if not pred(c)]:
        del REGISTRY[code]


# ---------- C1: исчерпание банка раньше N_MIN_DECIDE ----------

def test_bank_exhausted_before_min_answers_is_incomplete_without_status(client, db, candidate_login, toy_bank):
    keep_only(lambda c: c.startswith("toy.db.3."))  # 3 семейства — меньше N_MIN_DECIDE
    u = candidate_login()
    aid = start(client)
    for _ in range(3):
        st = answer_current(client, db, aid, False)
    st = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()
    assert st["stage"] == "incomplete" and st["result"] is None and st["bank_exhausted"] is True
    db.expire_all()
    a = db.get(Attempt, uuid.UUID(aid))
    assert a.status == "incomplete" and a.decision is None and a.bank_exhausted
    p = db.get(CandidateProfile, u.id)
    assert p.grade_status == "not_tested"
    av = client.get("/api/v1/candidate/tests/availability").json()
    assert all(av[g]["allowed"] for g in ("junior", "middle", "senior"))


def test_bank_exhausted_in_phase2_keeps_phase1_decision(client, db, candidate_login, toy_bank):
    keep_only(lambda c: c.startswith(("toy.db.3.", "toy.db.4.")))  # 6 семейств: на фазу 2 ничего не остаётся
    candidate_login()
    aid = start(client)
    for _ in range(6):
        st = answer_current(client, db, aid, True)
    assert st["stage"] == "transition"
    st = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()
    assert st["stage"] == "finished" and st["result"]["decision"] == "confirmed" and st["bank_exhausted"]
    db.expire_all()
    a = db.get(Attempt, uuid.UUID(aid))
    assert a.status == "completed" and a.bank_exhausted and a.border is False


def test_start_refused_when_specialization_has_no_bank(client, db, candidate_login, toy_bank):
    candidate_login(specialization="frontend")
    r = client.post("/api/v1/candidate/attempts", json=START)
    assert r.status_code == 409 and r.json()["code"] == "bank_unavailable"


def test_meta_marks_specializations_without_bank(client, db, candidate_login, toy_bank):
    candidate_login()
    meta = client.get("/api/v1/candidate/meta").json()
    avail = {s["code"]: s["test_available"] for s in meta["specializations"]}
    assert avail == {"backend": True, "frontend": False, "data": False}


# ---------- I2: автозакрытие ставит время истечения, а не время обнаружения ----------

def test_autoclose_stamps_expiry_time(client, db, candidate_login, toy_bank, frozen_now):
    frozen_now(T0)
    candidate_login()
    aid = start(client)
    answer_current(client, db, aid, True)
    db.expire_all()
    last = db.get(Attempt, uuid.UUID(aid)).last_activity_at
    frozen_now(T0 + timedelta(days=5))
    assert client.get(f"/api/v1/candidate/attempts/{aid}").json()["stage"] == "incomplete"
    db.expire_all()
    a = db.get(Attempt, uuid.UUID(aid))
    assert a.finished_at == last + timedelta(hours=PARAMS.attempt_autoclose_hours)


def test_autoclosed_decision_dated_at_expiry_so_cooldown_not_stretched(client, db, candidate_login, toy_bank,
                                                                       frozen_now):
    frozen_now(T0)
    candidate_login()
    aid = start(client)
    for _ in range(6):
        answer_current(client, db, aid, True)  # решение зафиксировано, фаза 2 брошена
    db.expire_all()
    last = db.get(Attempt, uuid.UUID(aid)).last_activity_at
    frozen_now(T0 + timedelta(days=5))
    client.get(f"/api/v1/candidate/attempts/{aid}")
    db.expire_all()
    a = db.get(Attempt, uuid.UUID(aid))
    assert a.status == "completed" and a.finished_at == last + timedelta(hours=PARAMS.attempt_autoclose_hours)


# ---------- I3: тест ниже подтверждённого грейда ----------

def test_lower_grade_than_confirmed_refused(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client)
    for _ in range(6):
        answer_current(client, db, aid, True)
    for _ in range(10):
        if answer_current(client, db, aid, True)["stage"] == "finished":
            break
    client.post("/api/v1/demo/reset-cooldowns")
    r = client.post("/api/v1/candidate/attempts", json={**START, "target_grade": "junior"})
    assert r.status_code == 409 and r.json()["code"] == "grade_below_confirmed"


# ---------- I4: смена специализации во время попытки ----------

def test_specialization_change_blocked_during_attempt(client, db, candidate_login, toy_bank, frozen_now):
    frozen_now(T0)
    candidate_login()
    start(client)
    r = client.put("/api/v1/candidate/profile/survey", json={"specialization": "data", "claimed_grade": "middle"})
    assert r.status_code == 409 and r.json()["code"] == "attempt_in_progress"
    r = client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "senior"})
    assert r.status_code == 200
    frozen_now(T0 + timedelta(hours=PARAMS.attempt_autoclose_hours, minutes=1))
    r = client.put("/api/v1/candidate/profile/survey", json={"specialization": "data", "claimed_grade": "middle"})
    assert r.status_code == 200


# ---------- M3: ленивое автозакрытие под блокировкой профиля ----------

@pytest.mark.parametrize("method,path", [("get", "/attempts/{aid}"), ("get", "/tests/availability"),
                                         ("get", "/attempts")])
def test_lazy_autoclose_paths_lock_profile(client, db, candidate_login, toy_bank, engine, method, path):
    candidate_login()
    aid = start(client)
    seen = []

    def spy(conn, cursor, statement, *a):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", spy)
    try:
        getattr(client, method)("/api/v1/candidate" + path.format(aid=aid))
    finally:
        event.remove(engine, "before_cursor_execute", spy)
    assert any("FROM candidate_profiles" in s and "FOR UPDATE" in s for s in seen)


# ---------- M4: экспозиция увеличивается атомарно ----------

def test_exposure_increment_is_atomic(engine, committed_candidate):
    """Параллельный показ того же семейства не теряет инкремент (read-modify-write в ORM терял)."""
    code = "toy.db.3.0"
    with Session(engine) as a, Session(engine) as b:
        assert a.get(ItemFamilyRow, code).exposure_count == 0  # транзакция A прочитала 0
        b.execute(text("UPDATE item_families SET exposure_count = 5 WHERE code = :c"), {"c": code})
        b.commit()
        svc._bump_exposure(a, code)
        a.commit()
    with Session(engine) as s:
        assert s.get(ItemFamilyRow, code).exposure_count == 6


# ---------- M6: лимиты тела ответа ----------

def test_too_many_integrity_events_are_truncated_not_rejected(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client)
    seq = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()["item"]["seq"]
    events = [{"type": "blur", "at": "2026-10-09T10:00:00Z"}] * 250
    r = client.post(f"/api/v1/candidate/attempts/{aid}/answer", json={"seq": seq, "response": "1", "events": events})
    assert r.status_code == 200
    db.expire_all()
    row = db.scalar(select(AttemptItem).where(AttemptItem.attempt_id == uuid.UUID(aid), AttemptItem.seq == seq))
    assert len(row.events) == 200


def test_oversized_response_rejected(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client)
    seq = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()["item"]["seq"]
    r = client.post(f"/api/v1/candidate/attempts/{aid}/answer", json={"seq": seq, "response": "x" * 20_000})
    assert r.status_code == 422


# ---------- M8: грейд, к которому относится статус ----------

def test_profile_reports_grade_of_status_attempt(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client)
    for _ in range(6):
        answer_current(client, db, aid, False)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "junior"})
    p = client.get("/api/v1/candidate/profile").json()
    assert p["grade_status"] == "not_confirmed" and p["status_grade"] == "middle" and p["claimed_grade"] == "junior"


# ---------- M9: история без запросов на каждую попытку ----------

def _add_finished(db, user_id, n):
    for _ in range(n):
        a = Attempt(user_id=user_id, kind="grade", specialization="backend", target_grade="middle",
                    item_cap=PARAMS.test_max, thresholds_version="expert-1", status="completed",
                    decision="not_confirmed", decided_at=clock.now(), finished_at=clock.now())
        db.add(a)
        db.flush()
        db.add(AttemptItem(attempt_id=a.id, seq=1, phase=1, family_code="toy.db.3.0", area="db", level=3,
                           b=0.0, seed="1", instance={}, time_limit_s=90, answered_at=clock.now(),
                           correct=True))
    db.commit()


def test_history_query_count_does_not_grow_with_attempts(client, db, candidate_login, toy_bank, engine):
    u = candidate_login()
    ensure_thresholds(db)
    counts = []
    for n in (1, 3):
        _add_finished(db, u.id, n)
        seen = []

        def spy(*a, seen=seen):
            seen.append(1)

        event.listen(engine, "before_cursor_execute", spy)
        try:
            hist = client.get("/api/v1/candidate/attempts").json()
        finally:
            event.remove(engine, "before_cursor_execute", spy)
        counts.append((len(hist), len(seen)))
    assert [c[0] for c in counts] == [1, 4]
    assert counts[0][1] == counts[1][1], counts


# ---------- M10: «мусорные» ответы для разных видов ответа ----------

@pytest.mark.parametrize("kind,stored", [("order", [2, 1, 3]), ("rows", [[1, "a"]]), ("choice", 1),
                                         ("line", 3), ("text", "6 7 25"), ("number", 2.5)])
@pytest.mark.parametrize("garbage", [None, "abc", {"x": 1}, [{"y": []}], 10**400, float("nan")])
def test_garbage_is_wrong_for_every_kind(kind, stored, garbage):
    assert svc._matches(kind, stored, garbage) is False


# ---------- конкурентность на настоящих транзакциях ----------

@pytest.fixture
def committed_candidate(engine, toy_bank):
    """Кандидат и зеркало банка, закоммиченные по-настоящему: для тестов с несколькими сессиями."""
    with Session(engine) as s:
        u = User(email=f"race-{uuid.uuid4().hex[:8]}@x.ru", role=Role.candidate, password_hash="x",
                 email_verified_at=clock.now())
        s.add(u)
        s.flush()
        s.add(CandidateProfile(user_id=u.id, specialization="backend", claimed_grade="middle"))
        sync_bank(s)
        ensure_thresholds(s)
        s.commit()
        uid = u.id
    yield uid
    with Session(engine) as s:
        s.execute(delete(User).where(User.id == uid))
        s.execute(delete(ItemFamilyRow).where(ItemFamilyRow.code.like("toy.%")))
        s.execute(delete(ThresholdsRow))
        s.commit()


def _run_parallel(engine, fn, n=2):
    results, errors = [], []

    def worker():
        with Session(engine, expire_on_commit=False) as s:
            try:
                results.append(fn(s))
            except Exception as e:  # noqa: BLE001 — тест собирает любые сбои потоков
                s.rollback()
                errors.append(e)

    threads = [Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    return results, errors


def test_parallel_starts_create_one_attempt_and_one_consent(engine, committed_candidate, monkeypatch):
    barrier = Barrier(2, timeout=2)
    orig = svc.grade_availability

    def slow(*a, **k):
        r = orig(*a, **k)
        try:
            barrier.wait()
        except BrokenBarrierError:
            pass
        return r

    monkeypatch.setattr(svc, "grade_availability", slow)
    data = StartIn(target_grade="middle", accept_rules=True, pledge=True)

    def go(s):
        return svc.start_attempt(s, s.get(User, committed_candidate), data).id

    ids, errors = _run_parallel(engine, go)
    assert not errors, errors
    assert len(set(ids)) == 1
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(Attempt).where(
            Attempt.user_id == committed_candidate, Attempt.status == "in_progress")) == 1
        assert s.scalar(select(func.count()).select_from(Consent).where(
            Consent.user_id == committed_candidate, Consent.type == "automated_rules")) == 1


def test_parallel_double_submit_counted_once(engine, committed_candidate):
    with Session(engine, expire_on_commit=False) as s:
        user = s.get(User, committed_candidate)
        a = svc.start_attempt(s, user, StartIn(target_grade="middle", accept_rules=True, pledge=True))
        svc.present_next(s, user, a.id)
        aid = a.id

    def go(s):
        return svc.submit_answer(s, s.get(User, committed_candidate), aid, AnswerIn(seq=1, response="1")).id

    _, errors = _run_parallel(engine, go, n=4)
    assert not errors, errors
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(AttemptItem).where(
            AttemptItem.attempt_id == aid, AttemptItem.answered_at.is_not(None))) == 1


def test_first_requests_on_empty_db_do_not_collide(engine, toy_bank):
    """Две первые транзакции на пустой БД синхронизируют банк и пороги одновременно."""
    def go(s):
        sync_bank(s)
        ensure_thresholds(s)
        time.sleep(0.3)  # держим незакоммиченную вставку, чтобы вторая транзакция на неё наткнулась
        s.commit()
        return True

    try:
        ok, errors = _run_parallel(engine, go)
        assert not errors, errors
        assert ok == [True, True]
    finally:
        with Session(engine) as s:
            s.execute(delete(ItemFamilyRow).where(ItemFamilyRow.code.like("toy.%")))
            s.execute(delete(ThresholdsRow))
            s.commit()
