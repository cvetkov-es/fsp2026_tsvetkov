import re

from app.assessment.bank.areas import AREAS
from app.config.params import PARAMS
from app.hiring.interview_pool import QUESTIONS
from app.matching.stack_dict import SKILL_TITLES


def test_pool_has_eight_open_questions_per_area_and_skill():
    keys = {a for areas in AREAS.values() for a in areas} | set(SKILL_TITLES)
    assert set(QUESTIONS) == keys
    for key, qs in QUESTIONS.items():
        assert len(qs) == PARAMS.interview_q_per_area and len(set(qs)) == len(qs), key
        assert all(q.endswith("?") and len(q) <= 200 for q in qs), key


def test_questions_are_open_without_keys_or_personal_data():
    for qs in QUESTIONS.values():
        for q in qs:
            assert "@" not in q and not re.search(r"\d{5,}", q), q  # без адресов и телефонов
            assert not q.startswith(("Верно ли", "Правда ли")), q  # открытые, а не «да/нет»
