from datetime import timedelta

from sqlalchemy import select

from app.candidates.models import SkillResult
from app.common import clock
from app.config.params import PARAMS
from app.hiring import helper as helper_module
from app.hiring.models import HelperUse
from tests.contacts.helpers import as_user

from .helpers import STACK, accept, accepted, stage

URL = "/api/v1/employer/contacts/{}/interview-helper"


def test_helper_trust_limit_and_reuse(client, db, make_candidate, monkeypatch):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p, trust="L1")
    assert client.get(URL.format(cid)).json()["code"] == "trust_required"
    s.company.trust_level = "L2"
    db.commit()
    stage(client, cid, stage="rejected", level="below", reason="level_below", weak_areas=["db"])
    first = client.get(URL.format(cid)).json()
    assert 0 < len(first["questions"]) <= PARAMS.helper_questions and first["used"] == 1
    assert first["window_days"] == PARAMS.helper_window_days  # окно лимита — из параметров, не из текста интерфейса
    assert sum(q["reason"] == "слабая область по итогам этапа" for q in first["questions"]) == 2
    assert client.get(URL.format(cid)).json() == first  # повтор — те же вопросы, лимит не тратится
    monkeypatch.setattr(helper_module, "PARAMS", PARAMS.model_copy(update={"helper_monthly": 1}))
    p2 = make_candidate(stack=STACK)
    cid2 = s.invite(p2.public_ref).json()["id"]
    accept(client, db, p2.user_id, cid2)
    s.as_employer()
    r = client.get(URL.format(cid2))
    assert r.status_code == 409 and r.json()["code"] == "helper_limit"  # новый контакт сверх лимита


def test_selection_covers_areas_confirmed_and_declared_skills_without_repeats(client, db, make_candidate):
    p = make_candidate(stack=("Python", "Docker"))
    db.add(SkillResult(user_id=p.user_id, skill_code="sql", passed=True))
    db.commit()
    s, cid = accepted(client, db, p, trust="L2")
    out = client.get(URL.format(cid)).json()
    reasons = {q["reason"] for q in out["questions"]}
    assert {"область специализации", "навык подтверждён тестом, спросите глубже", "заявлено без подтверждения, проверьте"} <= reasons
    topics = {q["topic"]: q["reason"] for q in out["questions"]}
    assert topics["SQL"] == "навык подтверждён тестом, спросите глубже" and topics["DevOps и контейнеры"] == "заявлено без подтверждения, проверьте"
    texts = [q["text"] for q in out["questions"]]
    assert len(texts) == len(set(texts)) <= PARAMS.helper_questions


def test_helper_needs_an_accepted_contact_of_the_own_company(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p, trust="L2")
    p2 = make_candidate(stack=STACK)
    sent = s.invite(p2.public_ref).json()["id"]
    r = client.get(URL.format(sent))
    assert r.status_code == 409 and r.json()["code"] == "helper_unavailable"  # приглашение ещё не принято
    as_user(client, db, p.user_id)
    assert client.get(URL.format(cid)).status_code == 403  # кандидат вопросов не видит
    other, _ = accepted(client, db, make_candidate(stack=STACK), trust="L2", email="hr2@corp.ru", company="Чужая")
    assert client.get(URL.format(cid)).json()["code"] == "contact_not_found"


def test_uses_older_than_thirty_days_do_not_count(client, db, make_candidate, frozen_now, monkeypatch):
    t0 = clock.now()
    frozen_now(t0)
    monkeypatch.setattr(helper_module, "PARAMS", PARAMS.model_copy(update={"helper_monthly": 1}))
    p1, p2 = make_candidate(stack=STACK), make_candidate(stack=STACK)
    s, c1 = accepted(client, db, p1, trust="L2")
    assert client.get(URL.format(c1)).json()["used"] == 1
    c2 = s.invite(p2.public_ref).json()["id"]
    accept(client, db, p2.user_id, c2)
    s.as_employer()
    assert client.get(URL.format(c2)).json()["code"] == "helper_limit"
    frozen_now(t0 + timedelta(days=31))
    as_user(client, db, s.employer.id)
    assert client.get(URL.format(c2)).json()["used"] == 1  # старое использование выпало из окна
    assert len(db.scalars(select(HelperUse)).all()) == 2
