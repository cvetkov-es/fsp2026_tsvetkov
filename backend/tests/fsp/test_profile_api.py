from tests.candidates.test_profile import login
from tests.contacts.helpers import as_user
from tests.fsp.helpers import SUB, link


def test_not_linked_is_neutral(client, db):
    login(client, db)
    v = client.get("/api/v1/candidate/fsp").json()
    assert v["status"] == "NOT_LINKED" and v["summary"] is None and v["results"] == []
    assert v["online"] == {"count": 0, "disciplines": 0}


def test_online_folded_and_not_counted_marked(client, db, make_candidate):
    farmer = link(db, make_candidate(), SUB["Тихонов"])
    as_user(client, db, farmer.user_id)
    v = client.get("/api/v1/candidate/fsp").json()
    assert v["results"] == [] and v["online"] == {"count": 10, "disciplines": 1}
    zh = link(db, make_candidate(), SUB["Исаева"])
    as_user(client, db, zh.user_id)
    notes = {r["competition_title"]: r["note"] for r in client.get("/api/v1/candidate/fsp").json()["results"]}
    assert notes["Чемпионат ЦФО по программированию систем ИБ 2025, финал"] == "дисквалификация"
    assert notes["Чемпионат Москвы по алгоритмическому программированию 2026"] == "предварительный протокол"
    assert notes["Чемпионат ЦФО по алгоритмическому программированию 2025, финал"] is None


def test_ranks_with_validity_and_team_line(client, db, make_candidate):
    anna = link(db, make_candidate(), SUB["Кузнецова"])
    as_user(client, db, anna.user_id)
    v = client.get("/api/v1/candidate/fsp").json()
    assert v["ranks"] == [{"rank": "KMS", "title": "КМС", "valid_until": "2028-12-20", "valid": True}]
    assert v["results"][0]["team_name"] == "Byte Force" and v["last_sync_at"]
    daria = link(db, make_candidate(), SUB["Миронова"])
    as_user(client, db, daria.user_id)
    assert client.get("/api/v1/candidate/fsp").json()["ranks"][0]["valid"] is False


def test_unlink_endpoint(client, db, make_candidate):
    p = link(db, make_candidate(), SUB["Кузнецова"])
    as_user(client, db, p.user_id)
    assert client.delete("/api/v1/candidate/fsp").status_code == 204
    v = client.get("/api/v1/candidate/fsp").json()
    assert v["status"] == "CONSENT_REVOKED" and v["results"] == [] and v["summary"] is None
