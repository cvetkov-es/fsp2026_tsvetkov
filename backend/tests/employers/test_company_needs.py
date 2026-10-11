from tests.employers.helpers import NEED, employer


def test_company_required_then_need_created_normalized(client, db):
    employer(client, db)
    r = client.post("/api/v1/employer/needs", json=NEED)
    assert r.status_code == 409 and r.json()["code"] == "company_required"
    assert client.put("/api/v1/employer/company", json={"name": "Корп", "description": "Платежи", "industry": "финтех",
                                                         "contacts": {"site": "corp.ru"}}).status_code == 200
    r = client.post("/api/v1/employer/needs", json=NEED)
    assert r.status_code == 201
    need = r.json()
    assert need["must"] == ["Python", "PostgreSQL"] and need["nice"] == ["Kafka"]


def test_need_validation(client, db):
    employer(client, db)
    client.put("/api/v1/employer/company", json={"name": "Корп"})
    r = client.post("/api/v1/employer/needs", json={**NEED, "salary_from": 400000})
    assert r.status_code == 422
    r = client.post("/api/v1/employer/needs", json={**NEED, "must": ["python", "квантовый блокчейн"]})
    assert r.status_code == 422 and r.json()["code"] == "unknown_terms"


def test_needs_limit_by_trust_level_l0(client, db):
    employer(client, db)
    client.put("/api/v1/employer/company", json={"name": "Корп"})
    assert client.post("/api/v1/employer/needs", json=NEED).status_code == 201
    r = client.post("/api/v1/employer/needs", json=NEED)
    assert r.status_code == 409 and r.json()["code"] == "needs_limit"


def test_foreign_need_404(client, db):
    employer(client, db, "a@corp.ru")
    client.put("/api/v1/employer/company", json={"name": "А"})
    nid = client.post("/api/v1/employer/needs", json=NEED).json()["id"]
    employer(client, db, "b@other.ru")
    client.put("/api/v1/employer/company", json={"name": "Б"})
    assert client.get(f"/api/v1/employer/needs/{nid}").status_code == 404
    assert client.post(f"/api/v1/employer/needs/{nid}/close").status_code == 404


def test_stack_dictionary_public_to_logged_in(client, db):
    employer(client, db)
    items = client.get("/api/v1/stack/dictionary").json()
    assert any(i["canonical"] == "PostgreSQL" for i in items)


def test_stack_dictionary_exposes_synonyms_for_autocomplete(client, db):
    employer(client, db)
    items = {i["canonical"]: i for i in client.get("/api/v1/stack/dictionary").json()}
    assert "k8s" in items["Kubernetes"]["synonyms"] and "реакт" in items["React"]["synonyms"]
