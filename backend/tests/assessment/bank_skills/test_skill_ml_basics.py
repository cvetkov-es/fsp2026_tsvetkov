import math
import re

import numpy as np
import pandas as pd
import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family

from ._helpers import assert_mcq_form, make, skill_codes

CODES = skill_codes("ml_basics")
SEEDS = range(40)


def table(inst, i=0):
    return inst.prompt.tables[i]


@pytest.mark.parametrize("code", CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)


def test_volume_and_areas():
    assert len(CODES) == 10
    assert sorted(REGISTRY[c].level for c in CODES) == [1, 1, 2, 2, 2, 2, 3, 3, 3, 4]
    assert {REGISTRY[c].area for c in CODES} == {"data", "model"}


def test_minmax_value():
    for seed in SEEDS:
        inst = make("sk.ml.minmax_value", seed)
        xs = [float(v) for v in re.search(r"\[(.*)\]", inst.prompt.code).group(1).split(", ")]
        x = float(re.search(r"значение (\d+)", inst.prompt.text).group(1))
        assert x in xs and inst.answer == round((x - min(xs)) / (max(xs) - min(xs)), 2)


def test_split_sizes_follow_sklearn():
    for seed in SEEDS:
        inst = make("sk.ml.split_sizes", seed)
        n = int(re.search(r"len\(X\) == (\d+)", inst.prompt.code).group(1))
        t = float(re.search(r"test_size=([\d.]+)", inst.prompt.code).group(1))
        assert inst.answer == n - math.ceil(n * t)


def test_numpy_shape_by_numpy():
    for seed in SEEDS:
        inst = make("sk.ml.numpy_shape", seed)
        ns = {"np": np}
        for line in inst.prompt.code.splitlines()[1:-1]:
            exec(line, ns)  # noqa: S102 — наш шаблонный код из генератора
        assert inst.answer == str(ns["y"].shape)


def test_groupby_mean_by_pandas():
    for seed in SEEDS:
        inst = make("sk.ml.groupby_mean_value", seed)
        t = table(inst)
        df = pd.DataFrame(list(t.rows), columns=list(t.columns))
        group = re.search(r"«([^»]+)»", inst.prompt.text).group(1)
        assert inst.answer == pytest.approx(round(df.groupby(t.columns[1])[t.columns[2]].mean()[group], 2))


def test_precision_recall_f1():
    for seed in SEEDS:
        inst = make("sk.ml.precision_recall", seed)
        tp, fp, fn = (int(re.search(rf"{k} = (\d+)", inst.prompt.text).group(1)) for k in ("TP", "FP", "FN"))
        p, r = tp / (tp + fp), tp / (tp + fn)
        metric = re.search(r"Чему равен (\w+)", inst.prompt.text).group(1)
        value = {"precision": p, "recall": r, "F1": 2 * p * r / (p + r)}[metric]
        assert inst.answer == pytest.approx(round(value, 2))


def test_one_hot_columns_by_pandas():
    for seed in SEEDS:
        inst = make("sk.ml.one_hot_columns", seed)
        t = table(inst)
        df = pd.DataFrame(list(t.rows), columns=list(t.columns))
        cols = re.findall(r'"(\w+)"', re.search(r"columns=\[(.*?)\]", inst.prompt.code).group(1))
        drop = "drop_first=True" in inst.prompt.code
        assert inst.answer == pd.get_dummies(df, columns=cols, drop_first=drop).shape[1]


LEAKS = ("всех данных", "всему датасету", "всей выборке", "по метрике на test")


def test_leakage_step():
    for seed in SEEDS:
        inst = make("sk.ml.leakage_step", seed)
        steps = re.findall(r"^\d\. (.+)$", inst.prompt.code, re.M)
        leaky = [i for i, s in enumerate(steps) if any(m in s for m in LEAKS)]
        assert len(steps) == 4 and leaky == [inst.answer]
    assert_mcq_form("sk.ml.leakage_step")


def test_knn_vote():
    for seed in SEEDS:
        inst = make("sk.ml.knn_vote", seed)
        qx, qy = map(int, re.search(r"точке \((-?\d+), (-?\d+)\)", inst.prompt.text).groups())
        pts = sorted(table(inst).rows, key=lambda r: (r[0] - qx) ** 2 + (r[1] - qy) ** 2)
        d = [(r[0] - qx) ** 2 + (r[1] - qy) ** 2 for r in pts]
        assert d[2] < d[3]  # граница тройки однозначна
        labels = [r[2] for r in pts[:3]]
        best = max(set(labels), key=labels.count)
        assert labels.count(best) >= 2 and inst.answer == best


def test_early_stopping_by_simulation():
    for seed in SEEDS:
        inst = make("sk.ml.early_stopping_epoch", seed)
        patience = int(re.search(r"patience=(\d)", inst.prompt.code).group(1))
        best, wait = math.inf, 0
        stop = None
        for epoch, loss in table(inst).rows:
            if loss < best:
                best, wait = loss, 0
            else:
                wait += 1
                if wait == patience:
                    stop = epoch
                    break
        assert stop is not None and inst.answer == stop


def test_kfold_fold_size_like_array_split():
    for seed in SEEDS:
        inst = make("sk.ml.kfold_fold_size", seed)
        n = int(re.search(r"(\d+) объектов", inst.prompt.text).group(1))
        k = int(re.search(r"n_splits=(\d+)", inst.prompt.code).group(1))
        i = int(re.search(r"(\d+)-м фолде", inst.prompt.text).group(1))
        assert inst.answer == len(np.array_split(np.arange(n), k)[i - 1])


CLASSIFICATION = ("ROC AUC", "F1", "accuracy")


def test_leakage_pipelines_are_coherent():
    for seed in range(300):
        steps = re.findall(r"^\d\. (.+)$", make("sk.ml.leakage_step", seed).prompt.code, re.M)
        if "порог классификации" in steps[3]:
            assert any(m in steps[3] for m in CLASSIFICATION), steps[3]
        if "StandardScaler на всех данных" in steps[0]:
            assert "StandardScaler" not in steps[1], steps
