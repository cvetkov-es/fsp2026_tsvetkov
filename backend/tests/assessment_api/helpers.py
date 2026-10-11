from sqlalchemy import select

from app.assessment.models import AttemptItem

FORBIDDEN_KEYS = {"answer", "family_code", "radicals", "instance", "seed"}


def walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_keys(v)


def assert_no_leak(body):
    leaked = FORBIDDEN_KEYS & set(walk_keys(body))
    assert not leaked, f"утечка ключей: {leaked}"


def answer_current(client, db, attempt_id, correct: bool) -> dict:
    state = client.post(f"/api/v1/candidate/attempts/{attempt_id}/next").json()
    assert_no_leak(state)
    item = state["item"]
    db.expire_all()
    row = db.scalar(select(AttemptItem).where(AttemptItem.attempt_id == attempt_id,
                                              AttemptItem.seq == item["seq"]))
    key = row.instance["answer"]
    response = str(int(key)) if correct else "-1"
    body = client.post(f"/api/v1/candidate/attempts/{attempt_id}/answer",
                       json={"seq": item["seq"], "response": response, "events": []}).json()
    assert_no_leak(body)
    return body
