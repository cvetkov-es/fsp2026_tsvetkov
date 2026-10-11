from tests.employers.helpers import employer
from tests.fsp.helpers import SUB, link


def as_employer(client, db):
    employer(client, db)
    client.put("/api/v1/employer/company", json={"name": "Корп"})


def test_prize_team_with_two_members_on_platform(client, db, make_candidate):
    a = link(db, make_candidate(spec="backend"), SUB["Кузнецова"])
    b = link(db, make_candidate(spec="frontend"), SUB["Орлов"])
    as_employer(client, db)
    teams = client.get("/api/v1/employer/teams").json()
    assert [t["competition_title"] for t in teams] == [
        "Кубок России по продуктовому программированию 2025, финал", "Лидеры цифровой трансформации 2024"]
    first = teams[0]
    assert (first["team_name"], first["place"], first["field_size"]) == ("Byte Force", 2, 20)
    assert (first["on_platform"], first["team_size"], first["cohesion"]) == (2, 3, 2.0)
    assert {m["ref"] for m in first["members"]} == {a.public_ref, b.public_ref}
    assert {m["minor"] for m in first["members"]} == {False}  # признак 14–17 лет нужен форме командного приглашения: часы в неделю
    assert "Секретное Имя" not in str(teams) and "Кузнецова" not in str(teams)
    assert client.get("/api/v1/employer/teams", params={"specialization": "data"}).json() == []
    assert len(client.get("/api/v1/employer/teams", params={"specialization": "frontend"}).json()) == 2


def test_hidden_fsp_or_single_member_gives_no_team(client, db, make_candidate):
    link(db, make_candidate(), SUB["Кузнецова"])
    link(db, make_candidate(preset="minimal"), SUB["Орлов"])  # ФСП скрыт пресетом видимости
    as_employer(client, db)
    assert client.get("/api/v1/employer/teams").json() == []
