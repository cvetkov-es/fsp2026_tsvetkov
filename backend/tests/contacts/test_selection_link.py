from tests.contacts.helpers import Scene

STACK = ("Python", "PostgreSQL")


def test_selection_shows_fork_fit_and_contact_status(client, db, make_candidate):
    p = make_candidate(stack=STACK, threshold=200000)
    make_candidate(stack=STACK, threshold=400000)
    s = Scene(client, db)
    s.invite(p.public_ref)
    sel = client.get(f"/api/v1/employer/needs/{s.need_id}/selection").json()
    assert sel["fork_fit"] == {"fit": 1, "total": 2}  # вилка до 261 000 на руки
    cards = {c["ref"]: c for b in sel["blocks"] for c in b["items"]}
    assert cards[p.public_ref]["contact_status"] == "sent"
