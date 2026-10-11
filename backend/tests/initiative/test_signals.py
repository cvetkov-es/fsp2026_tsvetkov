from datetime import datetime, timedelta

from sqlalchemy import select

from app.auth.models import Consent
from app.common import clock
from app.common.clock import MSK
from app.config.params import PARAMS
from app.matching.scoring import NeedFacts, accept
from app.notifications.models import Notification
from tests.contacts.helpers import Scene, as_user

STACK = ("Python", "PostgreSQL")


def company_id(s: Scene) -> str:
    return str(s.company.id)


def test_signal_raises_readiness_only_in_its_company(client, db, make_candidate):
    p = make_candidate(stack=STACK, threshold=200_000)
    mine, other = Scene(client, db, company="Корп"), Scene(client, db, email="hr2@corp.ru", company="Чужая")
    as_user(client, db, p.user_id)
    companies = client.get("/api/v1/candidate/companies").json()
    assert companies["signals_left"] == PARAMS.signals_per_quarter == companies["signals_limit"]
    assert {c["name"] for c in companies["items"]} == {"Корп", "Чужая"}
    r = client.post(f"/api/v1/candidate/companies/{company_id(mine)}/signal")
    assert r.status_code == 201 and r.json()["signals_left"] == PARAMS.signals_per_quarter - 1
    mine.as_employer()
    card = next(c for b in client.get(f"/api/v1/employer/needs/{mine.need_id}/selection").json()["blocks"]
                for c in b["items"] if c["ref"] == p.public_ref)
    assert card["signal"]
    assert [x["ref"] for x in client.get("/api/v1/employer/interest").json()] == [p.public_ref]
    assert db.scalar(select(Notification).where(Notification.user_id == mine.employer.id, Notification.kind == "signal"))
    other.as_employer()
    card = next(c for b in client.get(f"/api/v1/employer/needs/{other.need_id}/selection").json()["blocks"]
                for c in b["items"] if c["ref"] == p.public_ref)
    assert not card["signal"] and client.get("/api/v1/employer/interest").json() == []


def test_signal_limit_counts_withdrawn(client, db, make_candidate, frozen_now):
    frozen_now(datetime(2026, 10, 9, 12, 0, tzinfo=MSK))
    p = make_candidate(stack=STACK)
    scenes = [Scene(client, db, email=f"hr{i}@corp.ru", company=f"Корп {i}") for i in range(PARAMS.signals_per_quarter + 1)]
    as_user(client, db, p.user_id)
    first = client.post(f"/api/v1/candidate/companies/{company_id(scenes[0])}/signal").json()
    assert client.post(f"/api/v1/candidate/companies/{company_id(scenes[0])}/signal").json()["code"] == "already_signaled"
    client.delete(f"/api/v1/candidate/signals/{first['signal_id']}")  # отзыв слот не возвращает
    for s in scenes[1:PARAMS.signals_per_quarter]:
        assert client.post(f"/api/v1/candidate/companies/{company_id(s)}/signal").status_code == 201
    r = client.post(f"/api/v1/candidate/companies/{company_id(scenes[-1])}/signal")
    assert r.status_code == 409 and r.json()["code"] == "signal_limit"
    frozen_now(datetime(2027, 1, 1, 0, 5, tzinfo=MSK))  # новый квартал
    as_user(client, db, p.user_id)  # сессия прежней даты истекла
    assert client.post(f"/api/v1/candidate/companies/{company_id(scenes[-1])}/signal").status_code == 201


def test_signal_expires_after_ttl(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/companies/{company_id(s)}/signal")
    frozen_now(t0 + timedelta(days=PARAMS.signal_ttl_days, minutes=1))
    s.as_employer()
    assert client.get("/api/v1/employer/interest").json() == []


def test_blocked_company_cannot_be_signaled_and_is_hidden(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    as_user(client, db, p.user_id)
    client.put(f"/api/v1/candidate/blocks/{company_id(s)}")
    assert client.get("/api/v1/candidate/companies").json()["items"] == []
    assert client.post(f"/api/v1/candidate/companies/{company_id(s)}/signal").json()["code"] == "company_blocked"


def test_signal_floor_respects_salary_conflict(make_candidate):
    from tests.matching.test_scoring import cand  # фабрика CandidateFacts из тестов плана 04

    need = NeedFacts("backend", ("middle",), ("Python",), salary_to_net=150_000)
    t = clock.now()
    low = accept(cand(salary_threshold_net=300_000, signal_to_company=True, open_until=t - timedelta(days=1)), need, t)
    ok = accept(cand(salary_threshold_net=100_000, signal_to_company=True, open_until=t - timedelta(days=1)), need, t)
    assert low.value >= PARAMS.signal_floor_low and low.value < PARAMS.signal_floor_ok
    assert ok.value >= PARAMS.signal_floor_ok


def test_signal_needs_a_profile_that_the_company_can_see(client, db, make_candidate):
    not_tested = make_candidate(stack=STACK, status="not_tested")
    hidden = make_candidate(stack=STACK)
    for c in db.scalars(select(Consent).where(Consent.user_id == hidden.user_id, Consent.type == "distribution")):
        c.revoked_at = clock.now()  # согласие на показ профиля отозвано
    db.commit()
    s = Scene(client, db)
    for p in (not_tested, hidden):
        as_user(client, db, p.user_id)
        r = client.post(f"/api/v1/candidate/companies/{company_id(s)}/signal")
        assert r.status_code == 409 and r.json()["code"] == "not_visible"
        assert client.get("/api/v1/candidate/companies").json()["signals_left"] == PARAMS.signals_per_quarter  # слот цел


def test_signal_of_a_candidate_who_then_hid_the_company_is_ignored(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/companies/{company_id(s)}/signal")
    client.put(f"/api/v1/candidate/blocks/{company_id(s)}")
    s.as_employer()
    assert client.get("/api/v1/employer/interest").json() == []
    card = next(c for b in client.get(f"/api/v1/employer/needs/{s.need_id}/selection").json()["blocks"]
                for c in b["items"] if c["ref"] == p.public_ref)
    assert not card["signal"]
