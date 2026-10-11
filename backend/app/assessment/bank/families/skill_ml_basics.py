"""Навык «Основы ML»: области data и model.

Ключи — формулы и правила библиотек (sklearn, NumPy, pandas), посчитанные кодом без самих библиотек в генераторе;
семантические тесты сверяют их с NumPy и pandas.
"""
import math
import random

from app.assessment.bank.base import Generated, Prompt, Table, family

SPEC = "skill:ml_basics"
FEATURES = ("age", "income", "tenure", "visits", "score", "price", "rooms", "distance", "clicks", "rating")
MODELS = ("LogisticRegression", "RandomForest", "GradientBoosting", "SVC", "KNN", "CatBoost")


def _fraction_ok(x: float, digits: int) -> bool:
    """Значение далеко от границы округления: ответ не зависит от способа округления."""
    return abs((x * 10**digits) % 1 - 0.5) > 0.01


# --- sk.ml.minmax_value -----------------------------------------------------------------------
@family(code="sk.ml.minmax_value", specialization=SPEC, area="data", level=1, fmt="calc",
        space_size=len(FEATURES) * 90**6, median_time_s=45)
def minmax_value(rng: random.Random) -> Generated:
    while True:
        xs = rng.sample(range(10, 100), rng.randint(6, 9))
        x = rng.choice([v for v in xs if v not in (min(xs), max(xs))])
        value = (x - min(xs)) / (max(xs) - min(xs))
        if _fraction_ok(value, 2):
            break
    feat = rng.choice(FEATURES)
    code = f"{feat} = [{', '.join(map(str, xs))}]\nscaled = MinMaxScaler().fit_transform(...)  # по столбцу {feat}"
    return Generated("number", Prompt(
        text=f"Каким станет значение {x} после MinMaxScaler, обученного на этом столбце? Округлите до 2 знаков.",
        code=code, language="python", answer_hint="Число, например 0.37"), round(value, 2), ("minmax",))


# --- sk.ml.split_sizes ------------------------------------------------------------------------
TEST_SIZES = (0.1, 0.15, 0.2, 0.25, 0.3, 0.33)


@family(code="sk.ml.split_sizes", specialization=SPEC, area="model", level=1, fmt="calc",
        space_size=4951 * len(TEST_SIZES) * 100, median_time_s=40)
def split_sizes(rng: random.Random) -> Generated:
    while True:
        n, t = rng.randint(50, 5000), rng.choice(TEST_SIZES)
        product = n * t
        if abs(product - round(product)) > 1e-6:  # дробное n·t: ceil однозначен и для человека, и для float
            break
    n_test = math.ceil(product)  # правило sklearn: test = ceil(n · test_size), остальное — train
    code = (f"assert len(X) == {n}\nX_train, X_test, y_train, y_test = train_test_split(\n"
            f"    X, y, test_size={t}, random_state={rng.randint(0, 99)})")
    return Generated("number", Prompt(text="Сколько строк окажется в X_train?", code=code, language="python",
                                      answer_hint="Целое число"), n - n_test, ("train_test_split",))


# --- sk.ml.numpy_shape ------------------------------------------------------------------------
def _divisors(n: int) -> list[int]:
    return [d for d in range(2, n) if n % d == 0]


MAKERS = ("np.zeros({shape})", "np.ones({shape})", "np.empty({shape})", "np.full({shape}, {k})")
REDUCERS = ("sum", "mean", "max")


@family(code="sk.ml.numpy_shape", specialization=SPEC, area="data", level=2, fmt="calc",
        # форма (2–3 оси по 2..9) × способ создания × две операции (с осью и делителем для reshape)
        space_size=8**3 * (len(MAKERS) - 1 + 10) * (2 + len(REDUCERS) * 3 + 6) ** 2, median_time_s=50)
def numpy_shape(rng: random.Random) -> Generated:
    while True:
        shape = [rng.randint(2, 9) for _ in range(rng.choice((2, 3)))]
        size = math.prod(shape)
        if _divisors(size):
            break
    expr = "x"
    cur = list(shape)
    for _ in range(rng.randint(1, 2)):
        ops = ["T", "sum", "reshape"] + (["newaxis"] if len(cur) == 1 else [])
        op = rng.choice([o for o in ops if not (o == "sum" and len(cur) == 1)])
        if op == "T":
            expr += ".T"
            cur = cur[::-1]
        elif op == "sum":
            axis = rng.randrange(len(cur))
            expr += f".{rng.choice(REDUCERS)}(axis={axis})"
            cur = cur[:axis] + cur[axis + 1:]
        elif op == "reshape":
            n = math.prod(cur)
            p = rng.choice(_divisors(n) or [1])
            expr += f".reshape({p}, {n // p})"
            cur = [p, n // p]
        else:
            expr += "[:, None]"
            cur = [cur[0], 1]
    maker = rng.choice(MAKERS).format(shape=f"({', '.join(map(str, shape))})", k=rng.randint(0, 9))
    code = "\n".join(["import numpy as np", f"x = {maker}", f"y = {expr}",
                      "print(y.shape)"])
    answer = f"({cur[0]},)" if len(cur) == 1 else f"({', '.join(map(str, cur))})"
    return Generated("text", Prompt(text="Что выведет код?", code=code, language="python",
                                    answer_hint="Форма кортежем, например (3, 4)"), answer, ("numpy_shape",))


# --- sk.ml.groupby_mean_value -----------------------------------------------------------------
GROUP_COLS = (("team", ("red", "blue", "green", "gray")), ("city", ("Москва", "Казань", "Томск", "Сочи")),
              ("plan", ("free", "pro", "team", "max")))
VALUE_COLS = ("score", "revenue", "minutes", "orders")


@family(code="sk.ml.groupby_mean_value", specialization=SPEC, area="data", level=2, fmt="calc",
        space_size=len(GROUP_COLS) * len(VALUE_COLS) * 100**8, median_time_s=60)
def groupby_mean_value(rng: random.Random) -> Generated:
    gcol, pool = rng.choice(GROUP_COLS)
    vcol = rng.choice(VALUE_COLS)
    groups = rng.sample(pool, 3)
    while True:
        rows = [(i + 1, rng.choice(groups), rng.randint(1, 100)) for i in range(rng.randint(8, 12))]
        present = [g for g in groups if sum(r[1] == g for r in rows) >= 2]
        if not present:
            continue
        g = rng.choice(present)
        vals = [r[2] for r in rows if r[1] == g]
        mean = sum(vals) / len(vals)
        if _fraction_ok(mean, 2):
            break
    t = Table("df", ("id", gcol, vcol), tuple(rows))
    return Generated("number", Prompt(
        text=f"Какое значение вернёт df.groupby(\"{gcol}\")[\"{vcol}\"].mean() для группы «{g}»? Округлите до 2 знаков.",
        tables=(t,), answer_hint="Число, например 41.67"), round(mean, 2), ("groupby_mean",))


# --- sk.ml.precision_recall -------------------------------------------------------------------
@family(code="sk.ml.precision_recall", specialization=SPEC, area="model", level=2, fmt="calc",
        space_size=191**4 * 3, median_time_s=60)
def precision_recall(rng: random.Random) -> Generated:
    while True:
        tp, fp, fn, tn = (rng.randint(10, 200) for _ in range(4))
        p, r = tp / (tp + fp), tp / (tp + fn)
        metric = rng.choice(("precision", "recall", "F1"))
        value = {"precision": p, "recall": r, "F1": 2 * p * r / (p + r)}[metric]
        if _fraction_ok(value, 2):
            break
    t = Table("confusion", ("", "предсказано 1", "предсказано 0"), (("факт 1", tp, fn), ("факт 0", fp, tn)))
    return Generated("number", Prompt(
        text=f"Матрица ошибок классификатора: TP = {tp}, FP = {fp}, FN = {fn}, TN = {tn}. Чему равен {metric} "
             "для класса 1? Округлите до 2 знаков.", tables=(t,), answer_hint="Число, например 0.81"),
        round(value, 2), ("precision_recall_f1",))


# --- sk.ml.one_hot_columns --------------------------------------------------------------------
CATEGORICAL = (("city", ("Москва", "Казань", "Томск", "Омск", "Сочи")), ("plan", ("free", "pro", "team", "max")),
               ("device", ("ios", "android", "web")), ("channel", ("ads", "seo", "email", "partner", "direct")))
NUMERIC = ("age", "visits", "spent", "days")


@family(code="sk.ml.one_hot_columns", specialization=SPEC, area="data", level=2, fmt="calc",
        space_size=math.comb(len(CATEGORICAL), 2) * 2 * 3**2 * len(NUMERIC) * 100**8, median_time_s=55)
def one_hot_columns(rng: random.Random) -> Generated:
    cats = rng.sample(CATEGORICAL, rng.randint(2, 3))
    nums = rng.sample(NUMERIC, rng.randint(1, 2))
    levels = [(name, rng.sample(pool, rng.randint(2, len(pool)))) for name, pool in cats]
    n = max(len(v) for _, v in levels) + rng.randint(1, 3)
    columns = []
    for _name, vals in levels:  # каждое значение встречается хотя бы раз
        col = vals + [rng.choice(vals) for _ in range(n - len(vals))]
        rng.shuffle(col)
        columns.append(col)
    numeric = [[rng.randint(1, 100) for _ in range(n)] for _ in nums]
    rows = tuple(tuple(c[i] for c in columns + numeric) for i in range(n))
    t = Table("df", tuple([name for name, _ in levels] + nums), rows)
    drop = rng.random() < 0.5
    encoded = [name for name, _ in levels]
    answer = len(nums) + sum(len(v) - (1 if drop else 0) for _, v in levels)
    code = f"pd.get_dummies(df, columns=[{', '.join(repr(c).replace(chr(39), chr(34)) for c in encoded)}], drop_first={drop})"
    return Generated("number", Prompt(text="Сколько колонок будет у результата?", code=code, language="python",
                                      tables=(t,), answer_hint="Целое число"), answer, ("get_dummies",))


# --- sk.ml.leakage_step -----------------------------------------------------------------------
METRICS = ("ROC AUC", "F1", "accuracy", "RMSE", "MAE")
CLASS_METRICS = ("ROC AUC", "F1", "accuracy")  # порог классификации — только у классификаторов
CATS = ("city", "brand", "category", "region", "channel")


def _leakage_steps(rng: random.Random, leaky: int) -> list[str]:
    feat, cat, model = rng.choice(FEATURES), rng.choice(CATS), rng.choice(MODELS)
    metric = rng.choice(CLASS_METRICS if leaky == 3 else METRICS)
    test = f"test_size={rng.choice((0.2, 0.25, 0.3))}, random_state={rng.randint(0, 99)}"
    clean = [
        f"разбить данные на train и test ({test})",
        rng.choice([f"заполнить пропуски в {feat} медианой train и применить к test",
                    f"посчитать target encoding для {cat} на train и применить к test",
                    # второй StandardScaler после масштабирования всех данных в шаге 1 был бы бессмыслицей
                    *(["обучить StandardScaler на train и применить к train и test"] if leaky else [])]),
        f"обучить {model} на train",
        f"посчитать {metric} на test",
    ]
    leaks = [
        f"обучить StandardScaler на всех данных, затем разбить на train и test ({test})",
        rng.choice((f"заполнить пропуски в {feat} средним по всему датасету",
                    f"посчитать target encoding для {cat} по всему датасету",
                    f"отобрать {rng.randint(5, 30)} признаков SelectKBest по всей выборке")),
        f"обучить {model} на train с гиперпараметрами, подобранными по метрике на test",
        f"подобрать порог классификации по метрике на test и там же посчитать {metric}",
    ]
    steps = list(clean)
    steps[leaky] = leaks[leaky]
    return steps


@family(code="sk.ml.leakage_step", specialization=SPEC, area="model", level=3, fmt="mcq",
        space_size=4 * len(FEATURES) * len(CATS) * len(MODELS) * len(METRICS) * 3 * 3 * 100, median_time_s=60)
def leakage_step(rng: random.Random) -> Generated:
    leaky = rng.randrange(4)
    steps = _leakage_steps(rng, leaky)
    code = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, start=1))
    return Generated("choice", Prompt(
        text="В каком шаге конвейера информация из test просачивается в обучение (утечка данных)?", code=code,
        language="text", options=tuple(f"Шаг {i}" for i in range(1, 5)), answer_hint="Один вариант"),
        leaky, ("mcq", 4))


# --- sk.ml.knn_vote ---------------------------------------------------------------------------
@family(code="sk.ml.knn_vote", specialization=SPEC, area="model", level=3, fmt="calc",
        space_size=21**2 * 441**7 * 3**7, median_time_s=75)
def knn_vote(rng: random.Random) -> Generated:
    while True:
        qx, qy = rng.randint(-10, 10), rng.randint(-10, 10)
        pts = {(rng.randint(-10, 10), rng.randint(-10, 10)) for _ in range(rng.randint(7, 9))} - {(qx, qy)}
        pts = sorted(pts)
        labels = [rng.choice("ABC") for _ in pts]
        d = sorted(((x - qx) ** 2 + (y - qy) ** 2, i) for i, (x, y) in enumerate(pts))
        if len(d) < 7 or d[2][0] == d[3][0]:
            continue  # граница тройки должна быть однозначной
        top = [labels[i] for _, i in d[:3]]
        best = max(set(top), key=top.count)
        if top.count(best) >= 2:
            break
    t = Table("points", ("x", "y", "class"), tuple((x, y, lab) for (x, y), lab in zip(pts, labels, strict=True)))
    return Generated("text", Prompt(
        text=f"Какой класс kNN (k = 3, евклидово расстояние, голосование большинством) присвоит точке ({qx}, {qy})?",
        tables=(t,), answer_hint="Буква класса: A, B или C"), best, ("knn_k3",))


# --- sk.ml.early_stopping_epoch ---------------------------------------------------------------
@family(code="sk.ml.early_stopping_epoch", specialization=SPEC, area="model", level=3, fmt="calc",
        space_size=5 * 2 * 500**8, median_time_s=70)
def early_stopping_epoch(rng: random.Random) -> Generated:
    patience = rng.randint(2, 3)
    while True:
        n = rng.randint(8, 12)
        loss, losses = rng.uniform(0.8, 1.5), []
        for _ in range(n):
            loss = loss - rng.uniform(0.02, 0.15) if rng.random() < 0.6 else loss + rng.uniform(0.0, 0.05)
            losses.append(round(loss, 3))
        best, wait, stop = math.inf, 0, None
        for epoch, v in enumerate(losses, start=1):
            if v < best:  # улучшение — строго меньше лучшего
                best, wait = v, 0
            else:
                wait += 1
                if wait == patience:
                    stop = epoch
                    break
        if stop is not None and stop >= patience + 3:
            break
    t = Table("history", ("epoch", "val_loss"), tuple((i, v) for i, v in enumerate(losses, start=1)))
    code = f"EarlyStopping(monitor='val_loss', patience={patience}, min_delta=0)"
    return Generated("number", Prompt(
        text="На какой эпохе обучение остановится? Эпохи нумеруются с 1, улучшение — значение строго меньше лучшего.",
        code=code, language="python", tables=(t,), answer_hint="Номер эпохи"), stop, ("early_stopping",))


# --- sk.ml.kfold_fold_size --------------------------------------------------------------------
DATASETS = ("клиентов", "заказов", "сессий", "пациентов", "изображений", "транзакций")


@family(code="sk.ml.kfold_fold_size", specialization=SPEC, area="model", level=4, fmt="calc",
        space_size=481 * 8 * 5 * len(DATASETS), median_time_s=55)
def kfold_fold_size(rng: random.Random) -> Generated:
    while True:
        n, k = rng.randint(20, 500), rng.randint(3, 10)
        if n % k:  # иначе все фолды равны и правило не проверяется
            break
    i = rng.randint(1, k)
    size = n // k + (1 if i <= n % k else 0)  # первые n mod k фолдов на один объект больше
    return Generated("number", Prompt(
        text=f"В выборке {n} объектов ({rng.choice(DATASETS)}). Сколько объектов окажется в тестовой части в "
             f"{i}-м фолде (фолды нумеруются с 1)?", code=f"KFold(n_splits={k}, shuffle=False)", language="python",
        answer_hint="Целое число"), size, ("kfold_sizes",))
