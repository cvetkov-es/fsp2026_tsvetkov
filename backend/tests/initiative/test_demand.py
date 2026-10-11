from datetime import timedelta

from app.common import clock
from app.config.params import PARAMS
from app.employers.models import Company, Need
from tests.contacts.helpers import as_user


def _need(db, company, created, grades=("middle",), must=("Python", "Docker"), nice=("Kafka",), status="active",
          spec="backend"):
    db.add(Need(company_id=company.id, title="Бэкенд", specialization=spec, grades=list(grades), must=list(must),
                nice=list(nice), formats=[], salary_from=200_000, salary_to=300_000, gross_net="net",
                contact_method="chat", status=status, created_at=created))


def _companies(db, n):
    out = [Company(name=f"Компания {i}", trust_level="L1") for i in range(n)]
    db.add_all(out)
    db.flush()
    return out


def test_demand_k_anonymity_and_delay(client, db, make_candidate):
    p = make_candidate(stack=("Python",))
    t = clock.now()
    old = t - timedelta(days=PARAMS.demand_delay_days + 1)
    cs = _companies(db, PARAMS.demand_min_employers)
    for c in cs[:-1]:
        _need(db, c, old)
    _need(db, cs[-1], t - timedelta(days=1))  # свежая — ещё не учитывается
    db.commit()
    as_user(client, db, p.user_id)
    d = client.get("/api/v1/candidate/demand").json()
    assert d["enough"] is False and d["companies"] is None and d["top"] == []
    assert d["min_companies"] == PARAMS.demand_min_employers  # порог показывает фронтенд: числа только из PARAMS
    _need(db, cs[-1], old, status="closed")  # закрытая тоже не считается
    _need(db, _companies(db, 1)[0], old, grades=("senior",))  # чужой грейд не считается
    db.commit()
    assert client.get("/api/v1/candidate/demand").json()["enough"] is False


def test_demand_top_techs_and_skill_call(client, db, make_candidate):
    p = make_candidate(stack=("Python",))
    old = clock.now() - timedelta(days=PARAMS.demand_delay_days + 2)
    for c in _companies(db, PARAMS.demand_min_employers):
        _need(db, c, old)
    db.commit()
    as_user(client, db, p.user_id)
    d = client.get("/api/v1/candidate/demand").json()
    assert d["enough"] and d["companies"] == PARAMS.demand_min_employers and d["category"] == "Backend · Middle"
    top = {x["tech"]: x for x in d["top"]}
    assert top["Docker"]["share"] == 1.0 and top["Docker"]["state"] == "missing" and top["Docker"]["skill"] == "devops"
    assert top["Python"]["state"] == "confirmed"  # Backend Middle подтверждён — Python из ядра специализации
    assert d["skills"][0]["code"] == "devops"
