from datetime import timedelta

from sqlalchemy import select

from app.common import clock
from app.config.params import PARAMS
from app.integrations.models import Outbox, WebhookDelivery, WebhookEndpoint
from app.integrations.outbox import deliver_webhooks
from app.integrations.webhooks import new_secret
from tests.contacts.helpers import Scene, as_user
from tests.hiring.helpers import accepted, stage

STACK = ("Python", "PostgreSQL")
ok = lambda url: None  # noqa: E731 — example.com в песочнице может не резолвиться


class FakeHttp:
    def __init__(self, codes):
        self.codes, self.calls = list(codes), []

    def post(self, url, content=None, headers=None, follow_redirects=False):
        self.calls.append((url, content, headers))
        code = self.codes.pop(0) if self.codes else 200
        if isinstance(code, Exception):
            raise code

        class R:
            status_code = code
        return R()


def endpoint(db, company, url="https://ats.example.com/hook", active=True):
    ep = WebhookEndpoint(company_id=company.id, url=url, secret=new_secret(), active=active)
    db.add(ep)
    db.commit()
    return ep


def test_contact_events_reach_outbox_without_pd(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    s.invite(p.public_ref)
    ev = db.scalar(select(Outbox).where(Outbox.event_type == "contact.sent"))
    assert ev.company_id == s.company.id and ev.payload["candidate_ref"] == p.public_ref
    assert {"contact_id", "need_id", "channel", "alias", "status", "version", "at", "contact_url"} <= set(ev.payload)
    assert ev.payload["contact_url"].endswith(f"/contacts/{ev.payload['contact_id']}")
    assert "Секретное Имя" not in str(ev.payload) and "@x.ru" not in str(ev.payload) and "salary" not in str(ev.payload)


def test_hiring_stage_reaches_outbox_without_votes(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="below")
    ev = db.scalar(select(Outbox).where(Outbox.event_type == "pipeline.stage"))
    assert ev.payload["stage"] == "technical" and ev.payload["contact_id"] == cid
    assert "level" not in ev.payload and "below" not in str(ev.payload) and "vote" not in str(ev.payload)  # оценки приватны


def test_retries_with_backoff(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    endpoint(db, s.company)
    s.invite(p.public_ref)
    http = FakeHttp([500] * PARAMS.webhook_max_attempts)
    deliver_webhooks(db, t0, http, check=ok)
    d = db.scalar(select(WebhookDelivery))
    assert d.status == "pending" and d.attempt == 1
    assert d.next_attempt_at == t0 + timedelta(minutes=PARAMS.webhook_backoff_min[0])
    t = t0
    for minutes in PARAMS.webhook_backoff_min[: PARAMS.webhook_max_attempts - 1]:
        t += timedelta(minutes=minutes)
        deliver_webhooks(db, t, http, check=ok)
    db.refresh(d)
    assert d.status == "failed" and len(http.calls) == PARAMS.webhook_max_attempts
    assert http.calls[0][2]["webhook-signature"].startswith("v1,")
    deliver_webhooks(db, t + timedelta(days=1), http, check=ok)
    assert len(http.calls) == PARAMS.webhook_max_attempts  # после «failed» повторов нет


def test_delivered_once_and_run_is_idempotent(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    endpoint(db, s.company)
    s.invite(p.public_ref)
    http = FakeHttp([200])
    first = deliver_webhooks(db, t0, http, check=ok)
    again = deliver_webhooks(db, t0 + timedelta(minutes=10), http, check=ok)
    assert first["sent"] >= 1 and again["sent"] == 0 and len(http.calls) == first["sent"]
    d = db.scalar(select(WebhookDelivery))
    assert d.status == "delivered" and d.status_code == 200 and d.delivered_at == t0
    ids = [c[2]["webhook-id"] for c in http.calls]
    assert len(set(ids)) == len(ids)  # у каждого события свой webhook-id, он же — при повторах


def test_events_go_only_to_active_endpoints_of_their_own_company(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    mine = Scene(client, db)
    other = Scene(client, db, email="hr2@corp.ru", company="Чужая")
    endpoint(db, mine.company, "https://mine.example.com/hook")
    endpoint(db, mine.company, "https://off.example.com/hook", active=False)
    endpoint(db, other.company, "https://other.example.com/hook")
    mine.invite(p.public_ref)
    http = FakeHttp([])
    deliver_webhooks(db, t0, http, check=ok)
    assert {c[0] for c in http.calls} == {"https://mine.example.com/hook"}


def test_a_failing_endpoint_or_a_blocked_address_never_breaks_the_product(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    endpoint(db, s.company, "https://down.example.com/hook")
    s.invite(p.public_ref)
    http = FakeHttp([RuntimeError("нет сети")])
    deliver_webhooks(db, t0, http, check=ok)  # исключение при отправке не выходит наружу
    d = db.scalar(select(WebhookDelivery))
    assert d.status == "pending" and d.attempt == 1 and d.error and "нет сети" not in d.error  # подробности сети в журнал не пишем

    def deny(url):
        from app.common.errors import AppError
        raise AppError(422, "webhook_url_private", "внутренний адрес")

    deliver_webhooks(db, t0 + timedelta(minutes=2), http, check=deny)  # адрес проверяется заново перед каждой отправкой
    db.refresh(d)
    assert d.status == "failed" and d.error == "url_blocked"
    assert len(http.calls) == 1


def test_group_events_reach_the_outbox_too(client, db, make_candidate, monkeypatch):
    from tests.groups.test_groups import create, team

    ps = team(make_candidate, monkeypatch)
    s = Scene(client, db, trust_level="L1")
    create(client, s, ps)
    types = {e.event_type for e in db.scalars(select(Outbox))}
    assert "contact.group_sent" in types
    inv = db.scalars(select(Outbox).where(Outbox.event_type == "contact.group_sent")).first()
    assert inv.payload["channel"] == "group_member"
    as_user(client, db, ps[0].user_id)
