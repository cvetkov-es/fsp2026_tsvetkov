import uuid

from sqlalchemy import func, select

from app.assessment.models import Attempt, AttemptItem
from app.candidates.models import CandidateProfile
from tests.assessment_api.helpers import answer_current, assert_no_leak

START = {"target_grade": "middle", "accept_rules": True, "pledge": True}


def start(client, **kw):
    return client.post("/api/v1/candidate/attempts", json={**START, **kw}).json()["id"]


def test_confirm_at_six_then_transition_then_phase2_finish(client, db, candidate_login, toy_bank):
    u = candidate_login()
    aid = start(client)
    for _ in range(6):
        st = answer_current(client, db, aid, True)
    assert st["stage"] == "transition" and st["result"]["decision"] == "confirmed"
    assert st["result"]["phrase"].startswith("Middle подтверждён · решено 6 из 6")
    p = db.get(CandidateProfile, u.id)
    db.refresh(p)
    assert p.grade_status == "confirmed" and p.confirmed_grade == "middle" and p.s_cache is not None
    for _ in range(st["phase2_total"]):
        st = answer_current(client, db, aid, True)
    assert st["stage"] == "finished" and st["status"] == "completed" and st["item"] is None
    assert "уровня выше" in st["result"]["phrase"]


def test_all_wrong_not_confirmed_and_lower_grade_available(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client)
    for _ in range(6):
        st = answer_current(client, db, aid, False)
    assert st["stage"] == "finished" and st["result"]["decision"] == "not_confirmed"
    r = client.post("/api/v1/candidate/attempts", json=START)
    assert r.status_code == 409 and r.json()["code"] == "cooldown"
    assert client.post("/api/v1/candidate/attempts", json={**START, "target_grade": "junior"}).status_code == 201


def test_double_submit_counted_once(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client)
    st = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()
    seq = st["item"]["seq"]
    for _ in range(2):
        r = client.post(f"/api/v1/candidate/attempts/{aid}/answer", json={"seq": seq, "response": "1"})
        assert r.status_code == 200
    n = db.scalar(select(func.count()).select_from(AttemptItem).where(
        AttemptItem.attempt_id == aid, AttemptItem.answered_at.is_not(None)))
    assert n == 1


def test_next_is_idempotent(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client)
    a = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()["item"]
    b = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()["item"]
    assert a["seq"] == b["seq"] and a["prompt"] == b["prompt"]


def test_garbage_responses_are_wrong_not_500(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client)
    for resp in (None, "abc", {"x": 1}, [1, 2]):
        st = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()
        r = client.post(f"/api/v1/candidate/attempts/{aid}/answer",
                        json={"seq": st["item"]["seq"], "response": resp})
        assert r.status_code == 200
    db.expire_all()
    assert not any(i.correct for i in db.scalars(select(AttemptItem).where(AttemptItem.attempt_id == aid)))


def test_timeout_counts_as_no_answer(client, db, candidate_login, toy_bank, frozen_now):
    from datetime import UTC, datetime, timedelta

    t0 = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)
    frozen_now(t0)
    candidate_login()
    aid = start(client)
    st = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()
    item = st["item"]
    db.expire_all()
    row = db.scalar(select(AttemptItem).where(AttemptItem.attempt_id == aid, AttemptItem.seq == item["seq"]))
    frozen_now(t0 + timedelta(seconds=item["time_limit_s"] + 6))
    client.post(f"/api/v1/candidate/attempts/{aid}/answer",
                json={"seq": item["seq"], "response": str(int(row.instance["answer"]))})
    db.refresh(row)
    assert row.timed_out is True and row.correct is False


def test_extra_time_raises_limit(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client, extra_time=True)
    st = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()
    assert st["item"]["time_limit_s"] == 30 * 3 * 1.5  # median 30 c, фактор 3, +50%


def test_express_awaiting_continue_and_extend(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client, express=True)
    for i in range(8):
        st = answer_current(client, db, aid, i % 2 == 0)  # чередование держит P около 0.5
    assert st["stage"] == "awaiting_continue" and st["n_answered"] == 8 and st["item"] is None
    assert client.post(f"/api/v1/candidate/attempts/{aid}/next").json()["item"] is None
    st = client.post(f"/api/v1/candidate/attempts/{aid}/extend").json()
    assert st["stage"] == "phase1" and st["express"] is False
    assert client.post(f"/api/v1/candidate/attempts/{aid}/next").json()["item"]["seq"] == 9
    r = client.post(f"/api/v1/candidate/attempts/{aid}/extend")
    assert r.status_code == 409 and r.json()["code"] == "not_extendable"


def test_bank_exhausted_finishes_gracefully(client, db, candidate_login, toy_bank):
    from app.assessment.bank.base import REGISTRY

    for code in [c for c in REGISTRY if not c.startswith("toy.db.")]:
        del REGISTRY[code]  # в банке остаются 15 семейств одной области
    candidate_login()
    aid = start(client)
    st = None
    for i in range(30):
        st = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()
        if st["item"] is None:
            break
        client.post(f"/api/v1/candidate/attempts/{aid}/answer",
                    json={"seq": st["item"]["seq"], "response": "-1" if i % 2 else "1"})
    assert st["stage"] == "finished"
    db.expire_all()
    a = db.get(Attempt, uuid.UUID(aid))
    assert a.status == "completed" and (a.bank_exhausted or a.decision is not None)
    assert_no_leak(st)


def test_next_holds_row_lock_until_single_commit(client, db, candidate_login, toy_bank, monkeypatch):
    """Ленивая синхронизация банка не должна коммитить посреди /next: commit снимает FOR UPDATE,
    и параллельный /next (StrictMode, двойной клик) вставит задание с тем же seq → 500."""
    candidate_login()
    aid = start(client)
    commits = []
    orig = db.commit
    monkeypatch.setattr(db, "commit", lambda: (commits.append(1), orig())[1])
    st = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()
    assert st["item"] is not None
    assert len(commits) == 1


def test_item_remaining_time_counts_from_presentation(client, db, candidate_login, toy_bank, frozen_now):
    """После перезагрузки страницы таймер продолжает отсчёт сервера, а не начинается заново."""
    from datetime import UTC, datetime, timedelta

    t0 = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)
    frozen_now(t0)
    candidate_login()
    aid = start(client)
    item = client.post(f"/api/v1/candidate/attempts/{aid}/next").json()["item"]
    assert item["remaining_s"] == item["time_limit_s"]
    frozen_now(t0 + timedelta(seconds=40))
    again = client.get(f"/api/v1/candidate/attempts/{aid}").json()["item"]
    assert again["remaining_s"] == item["time_limit_s"] - 40
    frozen_now(t0 + timedelta(seconds=item["time_limit_s"] + 100))
    assert client.get(f"/api/v1/candidate/attempts/{aid}").json()["item"]["remaining_s"] == 0
