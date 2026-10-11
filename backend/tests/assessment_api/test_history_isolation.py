from tests.assessment_api.helpers import answer_current

START = {"target_grade": "middle", "accept_rules": True, "pledge": True}


def test_history_lists_attempts_with_phrase(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = client.post("/api/v1/candidate/attempts", json=START).json()["id"]
    for _ in range(6):
        answer_current(client, db, aid, False)
    hist = client.get("/api/v1/candidate/attempts").json()
    assert len(hist) == 1 and hist[0]["id"] == aid
    assert hist[0]["decision"] == "not_confirmed" and hist[0]["phrase"].startswith("Middle не подтверждён")


def test_foreign_attempt_is_404_everywhere(client, db, candidate_login, toy_bank):
    candidate_login(email="a@x.ru")
    aid = client.post("/api/v1/candidate/attempts", json=START).json()["id"]
    client.post(f"/api/v1/candidate/attempts/{aid}/next")
    candidate_login(email="b@x.ru")
    assert client.get(f"/api/v1/candidate/attempts/{aid}").status_code == 404
    assert client.post(f"/api/v1/candidate/attempts/{aid}/next").status_code == 404
    assert client.post(f"/api/v1/candidate/attempts/{aid}/answer", json={"seq": 1, "response": "1"}).status_code == 404
    assert client.post(f"/api/v1/candidate/attempts/{aid}/extend").status_code == 404
