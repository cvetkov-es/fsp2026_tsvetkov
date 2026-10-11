import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from app.common import clock
from app.config.params import PARAMS
from app.contacts.models import Contact
from app.employer_tasks.models import EmployerTask
from app.moderation.models import Case
from tests.contacts.helpers import INVITE, Scene, as_user
from tests.hiring.helpers import moderator

STACK = ("Python", "PostgreSQL")


def task_body(**kw):
    deadline = (clock.now() + timedelta(days=7)).isoformat()
    return {"title": "Посчитать p95", "specialization": "backend", "text": "Дан лог запросов…", "deadline": deadline} | kw


def test_l0_cannot_publish_and_limits_apply(client, db):
    s = Scene(client, db, trust_level="L0")
    r = client.post("/api/v1/employer/tasks", json=task_body())
    assert r.status_code == 403 and r.json()["code"] == "trust_required"
    s.company.trust_level = "L1"
    db.commit()
    far = (clock.now() + timedelta(days=PARAMS.task_ttl_days + 1)).isoformat()
    assert client.post("/api/v1/employer/tasks", json=task_body(deadline=far)).json()["code"] == "bad_deadline"
    assert client.post("/api/v1/employer/tasks", json=task_body(text="x" * (PARAMS.task_text_max + 1))).status_code == 422
    assert client.post("/api/v1/employer/tasks", json=task_body()).status_code == 201


def test_reference_answer_never_leaks_and_autocheck(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db, trust_level="L1")
    tid = client.post("/api/v1/employer/tasks", json=task_body(reference_answer="31337.5", answer_kind="number")).json()["id"]
    as_user(client, db, p.user_id)
    feed = client.get("/api/v1/candidate/tasks").json()
    assert feed[0]["id"] == tid and feed[0]["company"]["trust_level"] == "L1" and feed[0]["has_reference"]
    assert "31337" not in str(feed) and "reference" not in str(feed).replace("has_reference", "")
    mine = client.post(f"/api/v1/candidate/tasks/{tid}/submission", json={"answer": " 31337,50 "}).json()
    assert mine["status"] == "auto_correct"
    s.as_employer()
    items = client.get(f"/api/v1/employer/tasks/{tid}/submissions").json()["items"]
    assert items[0]["alias"].startswith("B-M-") and items[0]["auto_correct"] is True
    assert "Секретное Имя" not in str(items) and "@x.ru" not in str(items)  # решения псевдонимны


def test_deadline_and_one_submission(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p1, p2 = make_candidate(stack=STACK), make_candidate(stack=STACK)
    Scene(client, db, trust_level="L1")
    tid = client.post("/api/v1/employer/tasks", json=task_body()).json()["id"]
    as_user(client, db, p1.user_id)
    assert client.post(f"/api/v1/candidate/tasks/{tid}/submission", json={"answer": "Решение"}).json()["status"] == "pending"
    assert client.post(f"/api/v1/candidate/tasks/{tid}/submission", json={"answer": "Ещё"}).json()["code"] == "already_submitted"
    frozen_now(t0 + timedelta(days=8))
    as_user(client, db, p2.user_id)
    assert client.get("/api/v1/candidate/tasks").json() == []
    assert client.post(f"/api/v1/candidate/tasks/{tid}/submission", json={"answer": "Поздно"}).json()["code"] == "task_closed"


def test_employer_evaluates_and_invites_the_author(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db, trust_level="L1")
    tid = client.post("/api/v1/employer/tasks", json=task_body()).json()["id"]
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/tasks/{tid}/submission", json={"answer": "Решение"})
    old = clock.now() - timedelta(days=20)
    p.last_activity_at = old
    db.commit()
    s.as_employer()
    sid = client.get(f"/api/v1/employer/tasks/{tid}/submissions").json()["items"][0]["id"]
    r = client.post(f"/api/v1/employer/task-submissions/{sid}/evaluate", json={"verdict": "accepted", "comment": "Хорошо"})
    assert r.json()["verdict"] == "accepted"
    db.expire_all()
    assert db.get(type(p), p.user_id).last_activity_at > old  # оценённое решение — активность
    inv = client.post(f"/api/v1/employer/task-submissions/{sid}/invite",
                      json={**INVITE, "ref": p.public_ref, "need_id": s.need_id})
    assert inv.status_code == 201, inv.text
    c = db.scalar(select(Contact).where(Contact.user_id == p.user_id))
    assert c.channel == "task_author" and str(c.task_submission_id) == sid
    as_user(client, db, p.user_id)
    assert client.get("/api/v1/candidate/tasks").json()[0]["my_submission"]["status"] == "accepted"


def test_hint_is_advice_and_uses_masked_text(client, db, make_candidate):
    from app.llm.deps import get_llm
    from tests.llm_fakes import fake_llm

    llm, t = fake_llm('{"fits": "partly", "summary": "Учтены не все граничные случаи"}')
    client.app.dependency_overrides[get_llm] = lambda: llm
    p = make_candidate(stack=STACK)
    s = Scene(client, db, trust_level="L1")
    tid = client.post("/api/v1/employer/tasks", json=task_body()).json()["id"]
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/tasks/{tid}/submission", json={"answer": "Пишите мне: ivan@mail.ru, +7 999 123-45-67"})
    s.as_employer()
    sid = client.get(f"/api/v1/employer/tasks/{tid}/submissions").json()["items"][0]["id"]
    hint = client.post(f"/api/v1/employer/task-submissions/{sid}/hint").json()
    assert hint["llm_hint"]["fits"] == "partly" and hint["verdict"] is None  # совет, а не решение
    assert "ivan@mail.ru" not in t.sent_text() and "999 123" not in t.sent_text()


def test_free_work_complaint_removes_task(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    Scene(client, db, trust_level="L1")
    tid = client.post("/api/v1/employer/tasks", json=task_body()).json()["id"]
    as_user(client, db, p.user_id)
    assert client.post(f"/api/v1/candidate/tasks/{tid}/complaint", json={"comment": "Это реальная задача из бэклога"}).status_code == 201
    assert client.post(f"/api/v1/candidate/tasks/{tid}/complaint", json={}).json()["code"] == "already_complained"
    mod = moderator(client, db)
    case = client.get("/api/v1/moderation/cases").json()[0]
    assert case["type"] == "free_work" and {r["label"]: r["value"] for r in case["summary"]}["Задача"] == "Посчитать p95"
    assert [a["code"] for a in case["actions"]] == ["remove", "dismiss"]
    url = f"/api/v1/moderation/cases/{case['id']}/resolve"
    assert client.post(url, json={"action": "annul"}).json()["code"] == "bad_action"
    assert client.post(url, json={"action": "remove", "resolution_text": "Похоже на реальную работу"}).json()["status"] == "resolved"
    as_user(client, db, p.user_id)
    assert client.get("/api/v1/candidate/tasks").json() == []
    assert db.scalar(select(Case)).resolved_by == mod.id
    assert client.post(f"/api/v1/candidate/tasks/{tid}/submission", json={"answer": "Ответ"}).json()["code"] == "task_not_found"


def test_limits_come_from_params(client, db):
    Scene(client, db, trust_level="L1")
    assert client.get("/api/v1/employer/tasks/limits").json() == {
        "text_max": PARAMS.task_text_max, "ttl_days": PARAMS.task_ttl_days}


def test_naive_deadline_is_a_validation_error_not_a_crash(client, db):
    Scene(client, db, trust_level="L1")
    naive = (datetime.now() + timedelta(days=3)).replace(tzinfo=None).isoformat()
    assert client.post("/api/v1/employer/tasks", json=task_body(deadline=naive)).status_code == 422


def test_reference_must_fit_its_kind(client, db):
    Scene(client, db, trust_level="L1")
    r = client.post("/api/v1/employer/tasks", json=task_body(reference_answer="около 400", answer_kind="number"))
    assert r.status_code == 422 and r.json()["code"] == "bad_reference"
    assert client.post("/api/v1/employer/tasks", json=task_body(reference_answer="400", answer_kind="number")).status_code == 201


def test_invite_author_with_a_malformed_need_id_is_422(client, db):
    Scene(client, db, trust_level="L1")
    body = {**INVITE, "ref": "abcd1234", "need_id": "not-a-uuid"}
    assert client.post("/api/v1/employer/task-submissions/00000000-0000-0000-0000-000000000000/invite", json=body).status_code == 422


def test_pending_counts_only_what_waits_for_a_manual_check(client, db, make_candidate):
    p1, p2 = make_candidate(stack=STACK), make_candidate(stack=STACK)
    s = Scene(client, db, trust_level="L1")
    auto = client.post("/api/v1/employer/tasks", json=task_body(reference_answer="400", answer_kind="number")).json()["id"]
    manual = client.post("/api/v1/employer/tasks", json=task_body(title="Описать API")).json()["id"]
    as_user(client, db, p1.user_id)
    client.post(f"/api/v1/candidate/tasks/{auto}/submission", json={"answer": "400"})
    as_user(client, db, p2.user_id)
    client.post(f"/api/v1/candidate/tasks/{manual}/submission", json={"answer": "Описание"})
    s.as_employer()
    rows = {r["id"]: r for r in client.get("/api/v1/employer/tasks").json()}
    assert (rows[auto]["submissions"], rows[auto]["pending"]) == (1, 0)  # проверено эталоном
    assert (rows[manual]["submissions"], rows[manual]["pending"]) == (1, 1)  # ждёт работодателя


def test_feed_tells_the_answer_limit(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    Scene(client, db, trust_level="L1")
    client.post("/api/v1/employer/tasks", json=task_body())
    as_user(client, db, p.user_id)
    assert client.get("/api/v1/candidate/tasks").json()[0]["answer_max"] == PARAMS.task_answer_max


def test_removing_a_task_resolves_the_other_complaints_about_it(client, db, make_candidate):
    p1, p2 = make_candidate(stack=STACK), make_candidate(stack=STACK)
    Scene(client, db, trust_level="L1")
    tid = client.post("/api/v1/employer/tasks", json=task_body()).json()["id"]
    for p in (p1, p2):
        as_user(client, db, p.user_id)
        client.post(f"/api/v1/candidate/tasks/{tid}/complaint", json={"comment": "Реальная работа"})
    moderator(client, db)
    first = client.get("/api/v1/moderation/cases").json()[0]
    client.post(f"/api/v1/moderation/cases/{first['id']}/resolve", json={"action": "remove"})
    assert client.get("/api/v1/moderation/cases").json() == []  # вторая жалоба закрыта вместе с первой
    assert {c.resolution for c in db.scalars(select(Case))} == {"remove"}


def test_a_complaint_about_a_deleted_task_does_not_break_the_queue(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    Scene(client, db, trust_level="L1")
    tid = client.post("/api/v1/employer/tasks", json=task_body()).json()["id"]
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/tasks/{tid}/complaint", json={"comment": "Реальная работа"})
    db.delete(db.get(EmployerTask, uuid.UUID(tid)))
    db.commit()
    moderator(client, db)
    r = client.get("/api/v1/moderation/cases")
    assert r.status_code == 200 and "удалена" in {x["label"]: x["value"] for x in r.json()[0]["summary"]}["Задача"]
    url = f"/api/v1/moderation/cases/{r.json()[0]['id']}/resolve"
    assert client.post(url, json={"action": "dismiss"}).json()["status"] == "resolved"
