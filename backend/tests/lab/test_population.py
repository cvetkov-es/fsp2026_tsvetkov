from app.lab.population import make_needs, make_people, observe, thresholds, true_grade
from app.lab.rubric import relevance
from app.matching.scoring import NeedFacts


def test_people_are_reproducible_and_observed():
    a, b = make_people(30, seed=5), make_people(30, seed=5)
    assert [p.theta for p in a] == [p.theta for p in b]
    observe(a, seed=5)
    assert all(p.facts is not None and p.decision in ("confirmed", "not_confirmed") for p in a)
    assert all(p.facts.stack for p in a) and any(p.fsp_f > 0 for p in make_people(200, seed=1))


def test_rubric_uses_truth_not_declarations():
    t = thresholds()
    p = make_people(1, seed=3)[0]
    need = NeedFacts(p.spec, (true_grade(p.theta, t) or "junior",), tuple(sorted(p.techs))[:2], (), (), None)
    p.open_window = p.active = True
    p.formats = ()
    assert relevance(p, need, t) == 3
    fake = NeedFacts(p.spec, need.grades, ("Тех, которой нет у кандидата",), (), (), None)
    assert relevance(p, fake, t) == 0


def test_needs():
    needs = make_needs(9, seed=2)
    assert len(needs) == 9 and {n.facts.specialization for n in needs} == {"backend", "frontend", "data"}


def test_rubric_ignores_declared_stack_and_formula():
    """Замкнутого круга нет: заявленный стек не меняет рубрику, а сама рубрика не тянет формулу ранжирования."""
    import app.lab.rubric as rubric

    t = thresholds()
    p = make_people(1, seed=3)[0]
    p.open_window = p.active = True
    p.formats = ()
    need = NeedFacts(p.spec, (true_grade(p.theta, t) or "junior",), ("Тех, которой нет у кандидата",), (), (), None)
    p.declared = p.declared | {"Тех, которой нет у кандидата"}
    assert p.facts is None and relevance(p, need, t) == 0
    assert not any(getattr(v, "__module__", "") == "app.matching.scoring" for v in vars(rubric).values())


def test_farmers_get_low_f_by_points_table():
    farmers = [p for p in make_people(400, seed=9) if p.farmer]
    assert farmers and all(p.fsp_f < 0.1 for p in farmers)  # онлайн-отборы — одна строка на дисциплину
