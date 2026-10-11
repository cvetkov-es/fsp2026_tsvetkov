from tests.employers.helpers import NEED, employer

PII = ("Секретное Имя", "+79990000000", "@x.ru", "user_id", "full_name", "contacts")


def assert_no_pii(resp):
    text = resp.text
    for marker in PII:
        assert marker not in text, f"утечка: {marker}"


def setup(client, db, **need):
    employer(client, db)
    client.put("/api/v1/employer/company", json={"name": "Корп"})
    return client.post("/api/v1/employer/needs", json={**NEED, **need}).json()["id"]


def test_selection_blocks_order_and_no_pii(client, db, make_candidate):
    make_candidate(grade="middle", s=0.5, stack=("Python", "PostgreSQL"))
    make_candidate(grade="senior", s=0.7, stack=("Python", "PostgreSQL"))
    make_candidate(grade="middle", status="not_confirmed", s=0.9, stack=("Python", "PostgreSQL"))
    make_candidate(grade="middle", s=0.9, formats=("office",))
    make_candidate(grade="middle", status="not_tested")
    nid = setup(client, db)
    r = client.get(f"/api/v1/employer/needs/{nid}/selection")
    assert r.status_code == 200
    assert_no_pii(r)
    blocks = r.json()["blocks"]
    assert [b["block"] for b in blocks] == [1, 2, 3, 4]
    assert blocks[0]["title"].startswith("Подтверждённые")
    assert blocks[3]["items"][0]["conflicts"] == ["format"]
    card = blocks[0]["items"][0]
    assert card["explanation"]["lines"][2] == "Истории ФСП нет, навыки оценены по тесту"
    assert len(card["explanation"]["lines"]) == 3 and card["alias"].startswith("B-M-")


def test_minimal_preset_hides_city_and_fsp_and_ignores_them(client, db, make_candidate):
    make_candidate(preset="minimal", fsp_f=0.9, fsp_summary="ФСП: победитель", city="Москва")
    nid = setup(client, db)
    r = client.get(f"/api/v1/employer/needs/{nid}/selection")
    card = r.json()["blocks"][0]["items"][0]
    assert card["city"] is None and "Москва" not in r.text and "победитель" not in r.text
    assert card["explanation"]["lines"][2] == "Истории ФСП нет, навыки оценены по тесту"


def test_filters_suggestions_and_diff(client, db, make_candidate):
    make_candidate(stack=("Python", "PostgreSQL"))
    make_candidate(stack=("Python", "PostgreSQL", "Kafka"))
    nid = setup(client, db)
    first = client.get(f"/api/v1/employer/needs/{nid}/selection").json()
    assert first["diff"] is None  # первое открытие — сравнивать не с чем
    again = client.get(f"/api/v1/employer/needs/{nid}/selection").json()
    assert again["diff"] == {"added": 0, "removed": []}
    narrowed = client.get(f"/api/v1/employer/needs/{nid}/selection", params={"techs": "Kafka"}).json()
    assert sum(len(b["items"]) for b in narrowed["blocks"]) == 1
    assert len(narrowed["diff"]["removed"]) == 1 and "Kafka" in narrowed["diff"]["removed"][0]["reason"]
    empty = client.get(f"/api/v1/employer/needs/{nid}/selection", params={"techs": "Kafka", "has_fsp": "true"}).json()
    assert not any(b["items"] for b in empty["blocks"])
    assert any(s["filter"] == "has_fsp" and s["gain"] >= 1 for s in empty["suggestions"])


def test_shortlist_survives_filters_with_reason(client, db, make_candidate):
    p = make_candidate(stack=("Python", "PostgreSQL"))
    nid = setup(client, db)
    assert client.put(f"/api/v1/employer/needs/{nid}/shortlist/{p.public_ref}").status_code == 204
    r = client.get(f"/api/v1/employer/needs/{nid}/selection", params={"techs": "Kafka"}).json()
    assert r["shortlist"][0]["ref"] == p.public_ref and r["shortlist"][0]["pinned"] is True
    assert "Kafka" in r["shortlist"][0]["filter_mismatch"]
    assert client.delete(f"/api/v1/employer/needs/{nid}/shortlist/{p.public_ref}").status_code == 204


def test_latest_distribution_consent_wins_and_revoked_is_hidden(client, db, make_candidate):
    from datetime import timedelta

    from app.auth.consents import DISTRIBUTION_PRESETS, ConsentType, record_consent
    from app.auth.models import Consent
    from app.common import clock

    moved = make_candidate(city="Москва")
    later = record_consent(db, moved.user_id, ConsentType.distribution,
                           scope={"preset": "minimal", "fields": DISTRIBUTION_PRESETS["minimal"]})
    later.granted_at = clock.now() + timedelta(seconds=1)
    gone = make_candidate()
    for c in db.query(Consent).filter(Consent.user_id == gone.user_id):
        c.revoked_at = clock.now()
    db.commit()
    nid = setup(client, db)
    r = client.get(f"/api/v1/employer/needs/{nid}/selection")
    refs = [i["ref"] for b in r.json()["blocks"] for i in b["items"]]
    assert moved.public_ref in refs and gone.public_ref not in refs and "Москва" not in r.text


def test_map_and_cell(client, db, make_candidate):
    low = make_candidate(grade="middle", s=0.4)
    high = make_candidate(grade="middle", s=0.8)
    unc = make_candidate(grade="middle", status="not_confirmed", s=0.95)
    setup(client, db)
    cells = client.get("/api/v1/employer/map").json()["cells"]
    mid = next(c for c in cells if c["specialization"] == "backend" and c["grade"] == "middle")
    assert mid["confirmed"] == 2 and mid["unconfirmed"] == 1
    r = client.get("/api/v1/employer/map/backend/middle")
    assert_no_pii(r)
    statuses = [i["grade_status"] for i in r.json()["items"]]
    assert statuses == ["confirmed", "confirmed", "not_confirmed"]
    assert [i["ref"] for i in r.json()["items"]] == [high.public_ref, low.public_ref, unc.public_ref]


def test_percentile_counts_only_confirmed_of_the_cell(client, db, make_candidate):
    make_candidate(s=0.4)
    top = make_candidate(s=0.8)
    make_candidate(status="not_confirmed", s=0.95)
    nid = setup(client, db)
    r = client.get(f"/api/v1/employer/needs/{nid}/selection").json()
    items = {i["ref"]: i for b in r["blocks"] for i in b["items"]}
    assert "сильнее 100% категории" in items[top.public_ref]["explanation"]["lines"][0]


def test_snapshot_upsert_survives_concurrent_first_open(client, db, make_candidate, monkeypatch):
    from app.matching import service

    make_candidate()
    nid = setup(client, db)
    assert client.get(f"/api/v1/employer/needs/{nid}/selection").status_code == 200
    # второй параллельный запрос прочитал снимок до того, как первый его записал
    monkeypatch.setattr(service, "_previous_refs", lambda db, need_id: None)
    assert client.get(f"/api/v1/employer/needs/{nid}/selection").status_code == 200
