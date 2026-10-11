from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import load_all
from app.assessment.bank.pysnippet import run_python_snippet

load_all()


def test_alias_copy_answer_is_real_output_and_varies_by_copy_kind():
    f = REGISTRY["be.lang.list_alias_copy"]
    lens = set()
    for seed in range(40):
        inst = f.make(seed)
        assert inst.answer == run_python_snippet(inst.prompt.code)
        a, c, _ = inst.answer.split()
        lens.add(a == c)
    assert lens == {True, False}  # встречаются и псевдоним, и копия


def test_status_code_options_distinct_and_answer_in_range():
    f = REGISTRY["be.http.status_code"]
    valid = {"201", "403", "401", "204", "409", "422", "429", "415"}
    for seed in range(40):
        inst = f.make(seed)
        opts = inst.prompt.options
        assert len(opts) == 4 and len(set(opts)) == 4
        assert 0 <= inst.answer < 4 and opts[inst.answer] in valid


def test_lang_http_families_pass_pipeline():
    for code in ("be.lang.list_alias_copy", "be.http.status_code"):
        r = check_family(REGISTRY[code], subprocess_probe=False)
        assert r.ok, (code, r.errors)
