import math
import re
from datetime import datetime, timedelta

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families.skill_devops import compose_value

from ._helpers import assert_mcq_form, make, skill_codes

CODES = skill_codes("devops")
SEEDS = range(40)


@pytest.mark.parametrize("code", CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)


def test_volume_and_areas():
    assert len(CODES) == 10
    assert sorted(REGISTRY[c].level for c in CODES) == [1, 1, 2, 2, 2, 2, 3, 3, 3, 4]
    assert {REGISTRY[c].area for c in CODES} == {"container", "linux"}


def test_port_mapping_is_host_side():
    for seed in SEEDS:
        inst = make("sk.devops.port_mapping", seed)
        host, cont = map(int, re.search(r"-p (\d+):(\d+)", inst.prompt.code).groups())
        assert host != cont and str(cont) in inst.prompt.text and inst.answer == host


def test_chmod_octal():
    for seed in SEEDS:
        inst = make("sk.devops.chmod_octal", seed)
        mode = re.search(r"^[-d]([rwx-]{9}) ", inst.prompt.code).group(1)
        digits = "".join(str(int("".join("0" if c == "-" else "1" for c in mode[i:i + 3]), 2)) for i in (0, 3, 6))
        assert inst.answer == digits


def test_layer_cache_starts_at_first_copy_of_changed_file():
    for seed in SEEDS:
        inst = make("sk.devops.layer_cache_line", seed)
        changed = re.search(r"изменился файл (\S+)", inst.prompt.text).group(1)
        expected = None
        for n, line in enumerate(inst.prompt.code.splitlines(), start=1):
            parts = line.split()
            if parts and parts[0] in ("COPY", "ADD"):
                sources = parts[1:-1]
                if any(s == "." or s == changed or (s.endswith("/") and changed.startswith(s)) for s in sources):
                    expected = n
                    break
        assert inst.answer == expected


WEEKDAYS = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")


def _next_cron(expr: str, now: datetime) -> datetime:
    minute, hour, _, _, dow = expr.split()
    for day in range(9):
        d = (now + timedelta(days=day)).date()
        if dow == "1-5" and d.isoweekday() > 5:
            continue
        if "-" in hour:
            h1, h2 = map(int, hour.split("-"))
            hours = range(h1, h2 + 1)
        else:
            hours = [int(hour)]
        step = int(minute[2:]) if minute.startswith("*/") else None
        minutes = range(0, 60, step) if step else [int(minute)]
        for h in hours:
            for m in minutes:
                t = datetime(d.year, d.month, d.day, h, m)
                if t > now:
                    return t
    raise AssertionError(expr)


def test_cron_next_run():
    for seed in SEEDS:
        inst = make("sk.devops.cron_next_run", seed)
        expr = re.search(r"^(\S+ \S+ \* \* \S+) ", inst.prompt.code).group(1)
        wd, d, t = re.search(r"Сейчас (\w+), (\d\d\.\d\d\.\d{4}) (\d\d:\d\d:\d\d)", inst.prompt.text).groups()
        now = datetime.strptime(f"{d} {t}", "%d.%m.%Y %H:%M:%S")
        assert WEEKDAYS[now.weekday()] == wd
        assert inst.answer == _next_cron(expr, now).strftime("%d.%m %H:%M")


STAGE_CODES = {"true": 0, "false": 1, "sort": 0, "wc -l": 0}


def _stage_code(stage: str) -> int:
    stage = stage.strip()
    if stage in STAGE_CODES:
        return STAGE_CODES[stage]
    if stage.startswith("printf"):
        return 0
    if m := re.fullmatch(r"\[ (\d+) -lt (\d+) \]", stage):
        return 0 if int(m.group(1)) < int(m.group(2)) else 1
    if stage.startswith("grep -q"):
        return 1  # слова нет во входе
    m = re.fullmatch(r"\(exit (\d)\)", stage)
    return int(m.group(1))


def test_pipefail_exit():
    for seed in SEEDS:
        inst = make("sk.devops.pipefail_exit", seed)
        lines = inst.prompt.code.splitlines()
        pipeline = next(ln for ln in lines if "|" in ln)
        codes = [_stage_code(s) for s in pipeline.split("|")]
        if "set -o pipefail" in lines:
            expected = next((c for c in reversed(codes) if c), 0)
        else:
            expected = codes[-1]
        assert inst.answer == expected


def test_compose_rules_by_documentation():
    # environment важнее env_file, env_file важнее ENV образа
    assert compose_value(env=("literal", "a"), env_file="b", dockerfile="c", shell=None, dotenv=None) == "a"
    assert compose_value(env=None, env_file="b", dockerfile="c", shell="x", dotenv="y") == "b"
    # ${X}: оболочка важнее .env; нигде нет — пустая строка; ${X:-d} — значение по умолчанию
    assert compose_value(env=("interp", None), env_file="b", dockerfile=None, shell="x", dotenv="y") == "x"
    assert compose_value(env=("interp", None), env_file="b", dockerfile=None, shell=None, dotenv=None) == ""
    assert compose_value(env=("default", "d"), env_file=None, dockerfile="c", shell=None, dotenv=None) == "d"


def _parse_compose(code: str) -> str:
    sec = {}
    current = None
    for line in code.splitlines():
        if line.startswith("# "):
            current = line[2:].strip()
            sec[current] = []
        elif current:
            sec[current].append(line)
    var = re.search(r"ENV (\w+)=|^(\w+)=", "\n".join(sum(sec.values(), [])), re.M)
    yml = "\n".join(sec["docker-compose.yml"])
    env_line = re.search(r"^      (\w+): (.+)$", yml, re.M)
    file_val = docker_val = shell = dotenv = None
    if "app.env" in sec:
        file_val = sec["app.env"][0].split("=", 1)[1]
    if "Dockerfile" in sec:
        docker_val = next(ln for ln in sec["Dockerfile"] if ln.startswith("ENV")).split("=", 1)[1]
    run = sec["запуск"][0]
    if env_line:
        raw = env_line.group(2)
        m = re.fullmatch(r"\$\{(\w+)(?::-(\w+))?\}", raw)
        if not m:
            return raw
        x, default = m.groups()
        sm = re.search(rf"\b{x}=(\w*) docker", run)
        shell = sm.group(1) if sm else None
        if ".env" in sec:
            dm = next((ln.split("=", 1)[1] for ln in sec[".env"] if ln.startswith(f"{x}=")), None)
            dotenv = dm
        value = shell if shell is not None else dotenv
        if default is not None:
            return value if value else default
        return value if value is not None else ""
    assert var
    return file_val if file_val is not None else docker_val


def test_compose_env_precedence_key():
    for seed in range(80):
        inst = make("sk.devops.compose_env_precedence", seed)
        shown = inst.prompt.options[inst.answer]
        expected = _parse_compose(inst.prompt.code)
        assert shown == (expected if expected else "(пустая строка)")
    assert_mcq_form("sk.devops.compose_env_precedence")


def test_rollout_max_pods():
    for seed in SEEDS:
        inst = make("sk.devops.rollout_max_pods", seed)
        n = int(re.search(r"replicas: (\d+)", inst.prompt.code).group(1))
        surge = re.search(r"maxSurge: (\S+)", inst.prompt.code).group(1).strip('"')
        add = math.ceil(n * int(surge[:-1]) / 100) if surge.endswith("%") else int(surge)
        assert inst.answer == n + add


def test_grep_count():
    for seed in SEEDS:
        inst = make("sk.devops.grep_count", seed)
        log = [ln for ln in inst.prompt.tables[0].rows]
        lines = [r[0] for r in log]
        cmd = inst.prompt.code
        word = cmd.split()[2]
        flags = cmd.split()[1]
        rx = re.compile(re.escape(word), re.I if "i" in flags else 0)
        hits = [bool(rx.search(ln)) for ln in lines]
        expected = sum(not h for h in hits) if "v" in flags else sum(hits)
        assert inst.answer == expected


def test_ci_needs_order_is_unique_topological():
    for seed in SEEDS:
        inst = make("sk.devops.ci_needs_order", seed)
        jobs = {}
        for step in inst.prompt.steps:
            name, needs = re.fullmatch(r"(\w+): needs \[(.*)\]", step).groups()
            jobs[name] = [x.strip() for x in needs.split(",") if x.strip()]
        names = [re.match(r"\w+", s).group(0) for s in inst.prompt.steps]
        order = [names[i - 1] for i in inst.answer]
        done: set[str] = set()
        for name in order:
            ready = [j for j in jobs if j not in done and set(jobs[j]) <= done]
            assert ready == [name]  # на каждом шаге готов ровно один job — порядок единственный
            done.add(name)


def test_healthcheck_unhealthy_by_simulation():
    for seed in SEEDS:
        inst = make("sk.devops.healthcheck_unhealthy", seed)
        interval = int(re.search(r"--interval=(\d+)s", inst.prompt.code).group(1))
        retries = int(re.search(r"--retries=(\d+)", inst.prompt.code).group(1))
        start = int(re.search(r"--start-period=(\d+)s", inst.prompt.code).group(1))
        t_fail = int(re.search(r"через (\d+) с после старта", inst.prompt.text).group(1))
        assert t_fail > start and t_fail % interval != 0 and t_fail > interval
        streak, t = 0, 0
        while True:
            t += interval
            streak = streak + 1 if t >= t_fail else 0
            if streak == retries:
                break
        assert inst.answer == t


def test_pipefail_question_names_echo():
    # конвейер с wc -l или sort сам печатает строку — спрашиваем только про echo $?
    assert all("echo $?" in make("sk.devops.pipefail_exit", s).prompt.text for s in range(200))


def test_compose_interpolation_always_has_a_source():
    # пустая строка из ${VAR} без значения — ловушка, а не основы: у интерполяции всегда есть источник
    keys = [make("sk.devops.compose_env_precedence", s) for s in range(300)]
    assert all(i.prompt.options[i.answer] != "(пустая строка)" for i in keys)


def test_chmod_listing_looks_real():
    for seed in range(200):
        line = make("sk.devops.chmod_octal", seed).prompt.code
        kind, links, name = line[0], int(line.split()[1]), line.split()[-1]
        if kind == "d":
            assert links >= 2 and "." not in name.lstrip(".")  # у каталога ≥ 2 ссылок и имя без расширения
        else:
            assert links == 1
