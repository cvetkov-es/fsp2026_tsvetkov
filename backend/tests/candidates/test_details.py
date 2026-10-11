from app.candidates.models import CandidateProfile, SkillResult
from tests.candidates.test_profile import login


def test_details_roundtrip_and_validation(client, db):
    login(client, db)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    body = {"full_name": "Иван Петров", "contacts": {"telegram": "@ivan"}, "experience_years": 3.5,
            "formats": ["remote", "hybrid"], "city": "Казань", "domains": ["финтех"],
            "salary_threshold": 250000, "salary_gross_net": "gross"}
    r = client.put("/api/v1/candidate/profile/details", json=body)
    assert r.status_code == 200 and r.json()["formats"] == ["remote", "hybrid"]
    assert client.get("/api/v1/candidate/profile/details").json()["contacts"] == {"telegram": "@ivan"}
    bad = client.put("/api/v1/candidate/profile/details", json={**body, "formats": ["moon"]})
    assert bad.status_code == 422


def test_stack_states_declared_confirmed_and_unknown(client, db):
    u = login(client, db)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    r = client.put("/api/v1/candidate/profile/stack", json={"techs": ["postgres", "Docker", "Django", "суперфреймворк"]})
    assert r.status_code == 200
    data = r.json()
    states = {i["tech"]: i["state"] for i in data["items"]}
    assert states["PostgreSQL"] == "declared" and states["Python"] == "declared"  # implies от Django
    assert data["unknown"] == ["суперфреймворк"]
    db.add(SkillResult(user_id=u.id, skill_code="devops", passed=True))
    p = db.get(CandidateProfile, u.id)
    p.grade_status, p.confirmed_grade = "confirmed", "middle"
    db.commit()
    states = {i["tech"]: i["state"] for i in client.get("/api/v1/candidate/profile/stack").json()["items"]}
    assert states["Docker"] == "confirmed"  # навык devops
    assert states["SQL"] == "confirmed"  # ядро backend при подтверждённом грейде
    assert states["PostgreSQL"] == "declared"


def test_open_window_and_market(client, db):
    login(client, db)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    assert client.post("/api/v1/candidate/profile/open-window").json()["open_until"]
    m = client.get("/api/v1/candidate/market").json()
    assert m["n"] == 0 and m["median_net"] is None


def test_stack_lists_declared_even_when_confirmed_by_skill(client, db):
    u = login(client, db)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    client.put("/api/v1/candidate/profile/stack", json={"techs": ["Docker", "Django"]})
    db.add(SkillResult(user_id=u.id, skill_code="devops", passed=True))
    db.commit()
    data = client.get("/api/v1/candidate/profile/stack").json()
    assert data["declared"] == ["Django", "Docker"]
    assert {i["tech"]: i["state"] for i in data["items"]}["Docker"] == "confirmed"


def test_domain_items_limited_to_column_length(client, db):
    login(client, db)
    r = client.put("/api/v1/candidate/profile/details", json={"domains": ["д" * 41]})
    assert r.status_code == 422


def test_candidate_profile_endpoints_typed_in_openapi(client):
    paths = client.app.openapi()["paths"]
    for path, method in (("/api/v1/candidate/profile/stack", "get"), ("/api/v1/candidate/profile/stack", "put"),
                         ("/api/v1/candidate/profile/open-window", "post"), ("/api/v1/candidate/market", "get")):
        schema = paths[path][method]["responses"]["200"]["content"]["application/json"]["schema"]
        assert "$ref" in schema, path
