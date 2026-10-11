from datetime import timedelta

from sqlalchemy import select

from app.common import clock
from app.config.params import PARAMS
from app.contacts.models import Contact
from app.notifications.models import Notification
from tests.contacts.helpers import INVITE, Scene, as_user
from tests.junior.helpers import give_consent, minor

STACK = ("Python", "PostgreSQL")


def team(make_candidate, monkeypatch, n=3):
    """Команда из n участников на платформе — подменяем поиск команд ФСП (его проверяют тесты 07a1)."""
    ps = [make_candidate(stack=STACK) for _ in range(n)]
    set_team(monkeypatch, ps)
    return ps


def set_team(monkeypatch, ps, team_id="t1"):
    from app.groups import service as groups_service

    monkeypatch.setattr(groups_service, "prize_teams", lambda db, specialization=None: [
        {"team_id": team_id, "team_name": "Byte Force", "members": [{"ref": p.public_ref} for p in ps]}])


def create(client, s, ps, min_size=2, days=3, **kw):
    body = {"need_id": s.need_id, "team_id": "t1", "min_size": min_size,
            "deadline": (clock.now() + timedelta(days=days)).isoformat(),
            "members": [{"ref": p.public_ref, "salary_from": 200_000, "salary_to": 300_000} for p in ps],
            **{k: INVITE[k] for k in ("gross_net", "description", "why_you", "next_step")}, **kw}
    return client.post("/api/v1/employer/groups", json=body)


def my_invitation(client, db, p):
    as_user(client, db, p.user_id)
    return client.get("/api/v1/candidate/invitations").json()[0]


def test_group_spends_quota_per_member(client, db, make_candidate, monkeypatch):
    ps = team(make_candidate, monkeypatch, n=PARAMS.quota_l0 + 1)
    s = Scene(client, db, trust_level="L0")
    r = create(client, s, ps)
    assert r.status_code == 409 and r.json()["code"] == "quota_exceeded"
    assert db.scalars(select(Contact)).all() == []  # до создания: ни одного контакта
    s.company.trust_level = "L1"
    db.commit()
    assert create(client, s, ps).status_code == 201
    assert client.get(f"/api/v1/employer/needs/{s.need_id}/quota").json()["used"] == len(ps)


def test_conditional_accept_reveals_nothing_and_can_be_withdrawn(client, db, make_candidate, monkeypatch, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    create(client, s, ps)
    inv = my_invitation(client, db, ps[0])
    r = client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept").json()
    assert r["status"] == "conditionally_accepted" and not r["chat_open"]
    s.as_employer()
    assert client.get(f"/api/v1/contacts/{inv['id']}").json()["candidate"] is None  # контакты работодателю не раскрыты
    as_user(client, db, ps[0].user_id)
    assert client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-withdraw").json()["status"] == "sent"  # не открывали
    client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept")
    other = my_invitation(client, db, ps[1])  # минимум (2) набран — после срока выйти уже нельзя
    client.post(f"/api/v1/candidate/invitations/{other['id']}/conditional-accept")
    frozen_now(t0 + timedelta(days=4))
    as_user(client, db, ps[0].user_id)
    r = client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-withdraw")
    assert r.status_code == 409 and r.json()["code"] == "group_closed"


def test_members_see_only_own_answer_and_min_status(client, db, make_candidate, monkeypatch):
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    gid = create(client, s, ps, min_size=2).json()["id"]
    for p in ps[:2]:
        inv = my_invitation(client, db, p)
        client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept")
    inv = my_invitation(client, db, ps[2])
    assert inv["group"]["min_reached_now"] is True and "members" not in inv["group"]
    assert ps[0].public_ref not in str(inv)
    s.as_employer()
    g = client.get(f"/api/v1/employer/groups/{gid}").json()
    assert sorted(m["status"] for m in g["members"]) == ["conditionally_accepted", "conditionally_accepted", "sent"]
    # минимум равен составу — участникам статус минимума не показывается
    ps2 = team(make_candidate, monkeypatch, n=2)
    create(client, s, ps2, min_size=2)
    assert my_invitation(client, db, ps2[0])["group"]["min_reached_now"] is None


def test_v2_after_deadline_then_regular_accept(client, db, make_candidate, monkeypatch, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    gid = create(client, s, ps, min_size=2).json()["id"]
    for p in ps[:2]:
        inv = my_invitation(client, db, p)
        client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept")
    s.as_employer()
    assert client.post(f"/api/v1/employer/groups/{gid}/finalize").json()["code"] == "group_open"
    frozen_now(t0 + timedelta(days=4))
    as_user(client, db, s.employer.id)
    g = client.post(f"/api/v1/employer/groups/{gid}/finalize").json()
    assert g["state"] == "closed"
    inv = my_invitation(client, db, ps[0])
    assert inv["status"] == "offer_v2" and inv["version"] == 2
    assert client.post(f"/api/v1/candidate/invitations/{inv['id']}/accept",
                       json={"consent_contact_transfer": True}).json()["chat_open"]
    assert my_invitation(client, db, ps[2])["status"] == "expired"  # не ответил к сроку


def test_finalize_needs_the_minimum(client, db, make_candidate, monkeypatch, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    gid = create(client, s, ps, min_size=3).json()["id"]
    inv = my_invitation(client, db, ps[0])
    client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept")
    frozen_now(t0 + timedelta(days=4))
    as_user(client, db, s.employer.id)
    assert client.get(f"/api/v1/employer/groups/{gid}").json()["state"] == "not_reached"
    assert client.post(f"/api/v1/employer/groups/{gid}/finalize").json()["code"] == "min_not_reached"


def test_group_validation(client, db, make_candidate, monkeypatch):
    ps = team(make_candidate, monkeypatch)
    outsider = make_candidate(stack=STACK)
    s = Scene(client, db, trust_level="L2")
    assert create(client, s, ps, min_size=1).status_code == 422  # минимум не меньше двух
    assert create(client, s, ps, min_size=4).status_code == 422  # и не больше состава
    assert create(client, s, ps, days=PARAMS.group_ttl_days + 1).json()["code"] == "bad_deadline"
    assert create(client, s, ps, days=-1).json()["code"] == "bad_deadline"
    assert create(client, s, [*ps[:2], outsider]).json()["code"] == "member_not_in_team"
    assert create(client, s, ps[:1]).status_code == 422  # меньше TEAM_MIN_ON_PLATFORM
    assert create(client, s, ps, team_id="nope").json()["code"] == "team_not_found"
    naive = (clock.now() + timedelta(days=2)).replace(tzinfo=None).isoformat()
    assert create(client, s, ps, deadline=naive).status_code == 422  # срок без пояса — ошибка проверки, а не 500
    assert db.scalars(select(Contact)).all() == []


def test_group_respects_blocks_and_existing_invitations(client, db, make_candidate, monkeypatch):
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L2")
    s.invite(ps[0].public_ref)
    r = create(client, s, ps)
    assert r.status_code == 409 and r.json()["code"] == "invite_exists"
    assert db.scalar(select(Notification).where(Notification.kind == "group_invitation")) is None
    as_user(client, db, ps[1].user_id)
    client.put(f"/api/v1/candidate/blocks/{s.company.id}")
    s.as_employer()
    db.delete(db.scalars(select(Contact)).first())  # убираем старое приглашение: скрытие компании проверяем отдельно
    db.commit()
    r = create(client, s, ps)
    assert r.status_code == 409 and r.json()["code"] == "candidate_unavailable"


def test_group_member_can_decline_but_not_accept_directly(client, db, make_candidate, monkeypatch):
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    create(client, s, ps)
    inv = my_invitation(client, db, ps[0])
    r = client.post(f"/api/v1/candidate/invitations/{inv['id']}/accept", json={"consent_contact_transfer": True})
    assert r.status_code == 409 and r.json()["code"] == "group_conditional_only"  # контакты раскрываются только после v2
    assert client.post(f"/api/v1/candidate/invitations/{inv['id']}/counter", json={"amount": 300000, "gross_net": "gross"}).status_code == 409
    d = client.post(f"/api/v1/candidate/invitations/{inv['id']}/decline", json={"reason": "other"})
    assert d.status_code == 200 and d.json()["status"] == "declined"


def test_employer_withdraws_the_whole_group(client, db, make_candidate, monkeypatch):
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    gid = create(client, s, ps).json()["id"]
    inv = my_invitation(client, db, ps[0])
    client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept")
    as_user(client, db, s.employer.id)
    g = client.post(f"/api/v1/employer/groups/{gid}/withdraw").json()
    assert g["state"] == "closed" and {m["status"] for m in g["members"]} == {"withdrawn"}
    assert client.get(f"/api/v1/employer/needs/{s.need_id}/quota").json()["used"] == 0  # слоты освобождены


def test_min_reached_notification_once_and_only_when_min_is_below_size(client, db, make_candidate, monkeypatch):
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    create(client, s, ps, min_size=2)
    for p in ps[:2]:
        inv = my_invitation(client, db, p)
        client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept")
    inv = my_invitation(client, db, ps[0])
    client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-withdraw")
    client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept")  # снова набрали — второго письма нет
    kinds = [n.kind for n in db.scalars(select(Notification).where(Notification.kind == "group_min_reached"))]
    assert len(kinds) == 3  # работодатель и двое согласившихся — по одному разу
    ps2 = team(make_candidate, monkeypatch, n=2)
    s.as_employer()
    create(client, s, ps2, min_size=2)
    for p in ps2:
        inv = my_invitation(client, db, p)
        client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept")
    assert len(db.scalars(select(Notification).where(Notification.kind == "group_min_reached")).all()) == 3  # минимум = состав


def test_other_companies_do_not_see_the_group_and_there_is_a_list(client, db, make_candidate, monkeypatch):
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    gid = create(client, s, ps).json()["id"]
    assert [g["id"] for g in client.get("/api/v1/employer/groups").json()] == [gid]
    other = Scene(client, db, email="hr2@corp.ru", company="Чужая")
    other.as_employer()
    assert client.get(f"/api/v1/employer/groups/{gid}").status_code == 404
    assert client.get("/api/v1/employer/groups").json() == []


def test_a_minor_cannot_be_hired_into_a_full_time_group_and_needs_hours_otherwise(client, db, make_candidate, monkeypatch):
    kid = minor(db, make_candidate)
    adult = make_candidate(stack=STACK)
    give_consent(client, db, kid)
    set_team(monkeypatch, [kid, adult])
    s = Scene(client, db, trust_level="L2")
    r = create(client, s, [kid, adult])
    assert r.status_code == 409 and r.json()["code"] == "minor_full_employment"  # полная занятость — не для 14–17
    from app.employers.models import Need

    db.get(Need, s.need_id).employment = "vacation"
    db.commit()
    s.as_employer()
    assert create(client, s, [kid, adult]).json()["code"] == "hours_required"
    body_members = [{"ref": kid.public_ref, "salary_from": 40_000, "salary_to": 50_000, "hours_per_week": 20},
                    {"ref": adult.public_ref, "salary_from": 200_000, "salary_to": 300_000}]
    r = create(client, s, [kid, adult], members=body_members)
    assert r.status_code == 201
    assert db.scalar(select(Contact.hours_per_week).where(Contact.user_id == kid.user_id)) == 20


def test_group_limits_come_from_params(client, db):
    Scene(client, db, trust_level="L1")
    assert client.get("/api/v1/employer/groups/limits").json() == {"ttl_days": PARAMS.group_ttl_days, "min_team": PARAMS.team_min_on_platform}


def test_a_member_is_not_stuck_after_a_deadline_without_the_minimum(client, db, make_candidate, monkeypatch, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    create(client, s, ps, min_size=3)
    inv = my_invitation(client, db, ps[0])
    client.get(f"/api/v1/candidate/invitations/{inv['id']}")  # «Открыть»
    client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept")
    other = my_invitation(client, db, ps[1])
    client.post(f"/api/v1/candidate/invitations/{other['id']}/conditional-accept")
    frozen_now(t0 + timedelta(days=4))  # срок вышел, минимум (3) не набран: оффера не будет
    as_user(client, db, ps[0].user_id)
    r = client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-withdraw")
    assert r.status_code == 200 and r.json()["status"] == "viewed"
    as_user(client, db, ps[1].user_id)
    d = client.post(f"/api/v1/candidate/invitations/{other['id']}/decline", json={"reason": "other"})
    assert d.status_code == 200 and d.json()["status"] == "declined"  # отказаться можно и из условного согласия
    s.as_employer()
    assert client.get(f"/api/v1/employer/needs/{s.need_id}/quota").json()["used"] == 0  # слоты освобождены


def test_a_member_cannot_leave_once_the_minimum_is_reached_after_the_deadline(client, db, make_candidate, monkeypatch, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    create(client, s, ps, min_size=2)
    for p in ps[:2]:
        inv = my_invitation(client, db, p)
        client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept")
    frozen_now(t0 + timedelta(days=4))
    as_user(client, db, ps[0].user_id)
    inv = client.get("/api/v1/candidate/invitations").json()[0]
    assert client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-withdraw").json()["code"] == "group_closed"
    assert client.post(f"/api/v1/candidate/invitations/{inv['id']}/decline", json={"reason": "other"}).json()["code"] == "group_closed"


def test_withdraw_returns_to_sent_if_the_invitation_was_never_opened(client, db, make_candidate, monkeypatch):
    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    create(client, s, ps)
    inv = my_invitation(client, db, ps[0])
    client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-accept")  # без «Открыть»: viewed_at пуст
    assert client.post(f"/api/v1/candidate/invitations/{inv['id']}/conditional-withdraw").json()["status"] == "sent"
