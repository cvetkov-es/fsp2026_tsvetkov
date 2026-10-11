from tests.employers.helpers import NEED, employer
from tests.pdf_factory import pdf_text


def test_employer_pdf_is_pseudonymous(client, db, make_candidate):
    p = make_candidate(stack=("Python", "PostgreSQL"))
    employer(client, db)
    client.put("/api/v1/employer/company", json={"name": "Корп"})
    nid = client.post("/api/v1/employer/needs", json=NEED).json()["id"]
    r = client.get(f"/api/v1/employer/needs/{nid}/candidates/{p.public_ref}/pdf")
    assert r.status_code == 200
    text = pdf_text(r.content)
    assert p.public_ref[:4].upper() in text and "Почему в подборке «Бэкенд в платежи»" in text
    for secret in ("Секретное Имя", "+79990000000", "200000", "200 000"):
        assert secret not in text, secret
