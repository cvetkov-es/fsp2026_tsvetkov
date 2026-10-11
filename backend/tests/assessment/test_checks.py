import random

import pytest

from app.assessment.bank.base import Family, Generated, Prompt
from app.assessment.bank.checks import check_family


def _fam(gen, space=10**6, code="toy.x"):
    return Family(code, "backend", "lang", 1, "output", space, 20, gen)


def good(rng: random.Random) -> Generated:
    a, b = rng.randint(1, 10**6), rng.randint(1, 10**6)
    return Generated("number", Prompt(text=f"{a} + {b} = ?"), a + b, ("add",))


def tiny_space(rng: random.Random) -> Generated:
    a = rng.randint(1, 3)
    return Generated("number", Prompt(text=f"{a} * 2 = ?"), a * 2, ("mul",))


def unstable_radicals(rng: random.Random) -> Generated:
    a = rng.randint(1, 10**6)
    return Generated("number", Prompt(text=f"{a}?"), a, ("r", rng.randint(0, 1)))


def test_good_family_passes():
    r = check_family(_fam(good), subprocess_probe=False)
    assert r.ok, r.errors
    assert r.unique_prompt_share >= 0.95 and r.deterministic and r.radicals_stable and r.keys_roundtrip


def test_small_space_fails():
    r = check_family(_fam(tiny_space, space=3), subprocess_probe=False)
    assert not r.ok and any("пространство" in e for e in r.errors)
    assert any("уникальн" in e for e in r.errors)


def test_unstable_radicals_fail():
    r = check_family(_fam(unstable_radicals), subprocess_probe=False)
    assert not r.ok and any("радикал" in e for e in r.errors)


@pytest.mark.slow
def test_subprocess_probe_on_registered_family_is_stable():
    from app.assessment.bank.base import REGISTRY
    from app.assessment.bank.families import load_all

    load_all()
    if not REGISTRY:
        pytest.skip("семейства ещё не зарегистрированы")
    fam = next(iter(REGISTRY.values()))
    assert check_family(fam).hash_seed_stable
