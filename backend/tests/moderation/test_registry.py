import pytest

from app.moderation.service import open_case
from app.moderation.types import TYPES


def test_every_registered_type_has_actions_and_summary():
    assert {"vote_dispute", "free_work"} <= set(TYPES)  # остальные типы регистрируют задачи 2–4
    for t in TYPES.values():
        assert t.title and t.actions and callable(t.summary) and callable(t.apply)


def test_unknown_type_is_rejected(db, make_candidate):
    p = make_candidate()
    with pytest.raises(KeyError):
        open_case(db, "nope", {}, p.user_id)
