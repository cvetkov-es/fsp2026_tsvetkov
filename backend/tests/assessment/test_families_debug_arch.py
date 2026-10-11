import ast

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.families import load_all
from app.assessment.bank.pysnippet import run_python_snippet

load_all()


def test_window_bug_manifests_on_example_and_line_in_mutation_points():
    f = REGISTRY["be.debug.window_sums_bug"]
    for seed in range(40):
        inst = f.make(seed)
        assert inst.answer in (3, 4, 5, 6)
        call, expected = inst.prompt.text.split("Пример: ")[1].split(" == ")
        expected = ast.literal_eval(expected.split("\n")[0].strip().rstrip("."))
        got = ast.literal_eval(run_python_snippet(inst.prompt.code + f"\nprint({call})"))
        assert got != expected


def test_order_answer_restores_canonical_sequence():
    f = REGISTRY["be.arch.expand_contract_order"]
    for seed in range(40):
        inst = f.make(seed)
        ordered = [inst.prompt.steps[i - 1] for i in inst.answer]
        assert ordered[0].startswith("Добавить") and ordered[-1].startswith("Удалить")
        assert sorted(inst.answer) == [1, 2, 3, 4, 5, 6]
