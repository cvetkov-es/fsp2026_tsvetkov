import random
import re

import pytest

from app.assessment.bank.base import REGISTRY, Family, Generated, Prompt
from app.assessment.bank.canon import canonical
from app.assessment.bank.checks import check_family, estimate_space
from app.assessment.bank.families import backend_http, load_all
from app.config.params import PARAMS

load_all()


def test_space_estimator_on_known_sizes():
    rng = random.Random(7)
    for true_n in (500, 11_520, 50_000):
        draws = [rng.randrange(true_n) for _ in range(PARAMS.gen_space_sample)]
        est = estimate_space(len(draws), len(set(draws)))
        assert 0.8 * true_n <= est <= 1.25 * true_n, (true_n, est)
    assert estimate_space(2000, 2000) >= 2000 * 2000 / 6


def test_declared_space_is_not_trusted():
    def liar(rng: random.Random) -> Generated:
        a = rng.randint(1, 30)
        return Generated("number", Prompt(text=f"{a} + 1 = ?"), a + 1, ("add",))

    r = check_family(Family("toy.liar", "backend", "lang", 1, "output", 10**6, 20, liar),
                     subprocess_probe=False)
    assert not r.ok and r.space_estimate < PARAMS.gen_space_min
    assert any("оценка пространства" in e for e in r.errors)


@pytest.mark.parametrize("code", sorted(REGISTRY))
def test_registered_families_have_real_space(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.space_estimate >= PARAMS.gen_space_min, (code, r.space_estimate)


def test_http_distractors_are_not_defensible_answers():
    defensible = {422: {400}, 409: {422}, 415: {400}, 403: {404}}
    for _, correct, distractors in backend_http.SCENARIOS:
        assert not defensible.get(correct, set()) & set(distractors), (correct, distractors)


def _hint_example(inst) -> str:
    return re.search(r"например: (.+)$", inst.prompt.answer_hint).group(1)


def test_hint_examples_can_never_be_the_answer():
    for seed in range(300):
        arch = REGISTRY["be.arch.expand_contract_order"].make(seed)
        assert canonical("order", _hint_example(arch)) != arch.answer
        assert len(re.findall(r"\d+", _hint_example(arch))) != len(arch.prompt.steps)
        lang = REGISTRY["be.lang.list_alias_copy"].make(seed)
        assert int(_hint_example(lang).split()[0]) < 4  # len(a) ≥ 4 всегда
