from app.assessment.engine.rules import Decision, ItemResult
from app.assessment.engine.skill import evaluate_skill
from app.assessment.phrases import skill_phrase
from app.assessment.skills import SKILLS, skill_code, skill_spec
from app.config.params import PARAMS
from app.matching.stack_dict import SKILL_TECHS, SKILL_TITLES


def items(answers: list[bool], b: float = -0.5) -> list[ItemResult]:
    return [ItemResult(i + 1, f"f{i}", "a", 2, b, ok, 1) for i, ok in enumerate(answers)]


def test_fixed_length_then_decision():
    assert PARAMS.skill_len == 6
    ev = evaluate_skill(items([True] * 5))
    assert ev.status == "in_progress" and ev.decision is None and ev.n_answered == 5
    assert evaluate_skill(items([True] * 6)).decision == Decision.confirmed
    assert evaluate_skill(items([False] * 6)).decision == Decision.not_confirmed


def test_decision_is_probability_of_basic_level():
    ev = evaluate_skill(items([True, True, True, True, False, False], b=0.0))
    assert ev.status == "finished" and (ev.decision == Decision.confirmed) == (ev.p_pass >= 0.5)


def test_catalog_matches_stack_dictionary():
    assert set(SKILLS) == {"sql", "devops", "frontend_basics", "backend_basics", "ml_basics"}
    assert set(SKILLS) <= set(SKILL_TECHS)  # каждый навык подтверждает технологии словаря
    assert all(len(s.areas) == 2 and s.title == SKILL_TITLES[c] for c, s in SKILLS.items())
    assert skill_code(skill_spec("sql")) == "sql" and skill_code("backend") is None


def test_phrase():
    assert skill_phrase("SQL", "confirmed", 5, 6) == "Навык «SQL» подтверждён · решено 5 из 6"
    assert skill_phrase("SQL", "not_confirmed", 2, 6) == "Навык «SQL» не подтверждён · решено 2 из 6"
