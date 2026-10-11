"""Навык DevOps и контейнеры: области container и linux. Ключи вычисляются кодом по правилам документации (Docker, Compose, Kubernetes, bash, cron).
"""
import math
import random
from datetime import datetime, timedelta

from app.assessment.bank.base import SHUFFLES, Generated, Prompt, Table, family, mcq

SPEC = "skill:devops"
IMAGES = ("nginx:1.27", "redis:7", "postgres:16", "grafana/grafana:11", "minio/minio", "rabbitmq:3-management",
          "prom/prometheus", "jenkins/jenkins:lts", "mongo:7", "elasticsearch:8.15.0", "keycloak/keycloak:26",
          "myorg/api:1.4.2")
NAMES = ("api", "web", "cache", "queue", "metrics", "auth", "search", "storage", "billing", "reports")


# --- sk.devops.port_mapping -------------------------------------------------------------------
@family(code="sk.devops.port_mapping", specialization=SPEC, area="container", level=1, fmt="calc",
        space_size=len(IMAGES) * len(NAMES) * 8976 * 8975, median_time_s=30)
def port_mapping(rng: random.Random) -> Generated:
    host, cont = rng.sample(range(1024, 10000), 2)
    name, image = rng.choice(NAMES), rng.choice(IMAGES)
    code = f"docker run -d --name {name} -p {host}:{cont} {image}"
    return Generated("number", Prompt(
        text=f"Сервис внутри контейнера слушает порт {cont}. На какой порт хоста нужно обращаться "
             "(http://localhost:<порт>)?", code=code, language="bash", answer_hint="Номер порта"),
        host, ("publish_port",))


# --- sk.devops.chmod_octal --------------------------------------------------------------------
FILES = ("deploy.sh", "backup.sh", "config.yaml", ".env", "id_rsa", "app.log", "run.py", "secrets.json",
         "Makefile", "nginx.conf", "cron.sh", "data.db")
DIRS = ("logs", "backups", "scripts", "data", "releases", "uploads", "cache", ".ssh", "config", "tmp", "certs",
        "secrets")
OWNERS = ("root", "deploy", "app", "www-data", "ci", "postgres")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _mode(bits: int) -> str:
    return "".join(ch if bits & (1 << (8 - i)) else "-" for i, ch in enumerate("rwxrwxrwx"))


@family(code="sk.devops.chmod_octal", specialization=SPEC, area="linux", level=1, fmt="calc",
        space_size=512 * 2 * len(FILES) * len(OWNERS) * 12 * 28, median_time_s=40)
def chmod_octal(rng: random.Random) -> Generated:
    bits = rng.randrange(512)
    kind = rng.choice("-d")
    owner = rng.choice(OWNERS)
    links, name = (rng.randint(2, 12), rng.choice(DIRS)) if kind == "d" else (1, rng.choice(FILES))
    line = (f"{kind}{_mode(bits)} {links} {owner} {owner} {rng.randint(1, 99999)} {rng.choice(MONTHS)} "
            f"{rng.randint(1, 28):>2} {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d} {name}")
    return Generated("text", Prompt(
        text="Строка из ls -l. Какой аргумент нужно передать chmod, чтобы выставить ровно такие права "
             "(восьмеричная запись)?", code=line, language="text", answer_hint="Три цифры, например 644"),
        f"{bits >> 6}{(bits >> 3) & 7}{bits & 7}", ("octal_mode",))


# --- sk.devops.layer_cache_line ---------------------------------------------------------------
# база, файлы манифеста, установка зависимостей, каталоги исходников (с файлом внутри), отдельные файлы, запуск
STACKS = (
    ("python:{tag}-slim", ("requirements.txt",), "RUN pip install --no-cache-dir -r requirements.txt",
     (("src/", "src/main.py"), ("app/", "app/models.py")), ("config.yaml", "alembic.ini"),
     'CMD ["python", "-m", "src.main"]'),
    ("node:{tag}-alpine", ("package.json", "package-lock.json"), "RUN npm ci",
     (("src/", "src/index.ts"), ("public/", "public/index.html")), ("tsconfig.json", "vite.config.ts"),
     'CMD ["node", "dist/index.js"]'),
    ("golang:{tag}", ("go.mod", "go.sum"), "RUN go mod download",
     (("cmd/", "cmd/server/main.go"), ("internal/", "internal/db/db.go")), ("config.toml", "Makefile"),
     'CMD ["./server"]'),
)
MAINTAINERS = ("platform", "devops", "backend", "infra", "sre", "core", "payments", "search")
TAGS = {"python": ("3.11", "3.12", "3.13"), "node": ("20", "22", "24"), "golang": ("1.22", "1.23", "1.24")}
WORKDIRS = ("/app", "/srv", "/opt/app", "/usr/src/app", "/code", "/workspace")


@family(code="sk.devops.layer_cache_line", specialization=SPEC, area="container", level=2, fmt="bug",
        space_size=len(STACKS) * 3 * len(WORKDIRS) * (1 + len(MAINTAINERS)) * 1001 * 2 * 2 * 4, median_time_s=60)
def layer_cache_line(rng: random.Random) -> Generated:
    base, manifest, install, dirs, extras, cmd = rng.choice(STACKS)
    lines = [f"FROM {base.format(tag=rng.choice(TAGS[base.split(':')[0]]))}"]
    if rng.random() < 0.5:
        lines.append(f'LABEL team="{rng.choice(MAINTAINERS)}"')
    lines.append(f"WORKDIR {rng.choice(WORKDIRS)}")
    if rng.random() < 0.5:
        lines.append(f"ENV PORT={rng.randint(8000, 9000)}")
    lines.append(f"COPY {' '.join(manifest)} ./")
    lines.append(install)
    copied: list[tuple[str, int]] = [(f, len(lines) - 1) for f in manifest]  # (файл, номер строки COPY)
    if rng.random() < 0.5:
        lines.append("COPY . .")
        whole = len(lines)
        candidates = [d[1] for d in dirs] + list(extras)
        copied += [(f, whole) for f in candidates]
    else:
        for d, inner in dirs:
            lines.append(f"COPY {d} ./{d}")
            copied.append((inner, len(lines)))
        extra = rng.choice(extras)
        lines.append(f"COPY {extra} ./")
        copied.append((extra, len(lines)))
    lines.append(cmd)
    changed, line_no = rng.choice(copied)
    return Generated("line", Prompt(
        text=f"Образ уже собирался, все слои в кэше. Затем изменился файл {changed} — с какой строки Dockerfile "
             "слои начнут пересобираться?", code="\n".join(lines), language="dockerfile",
        answer_hint="Номер строки"), line_no, ("layer_cache",))


# --- sk.devops.cron_next_run ------------------------------------------------------------------
WEEKDAYS = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")
JOBS = ("sync", "backup", "report", "cleanup", "export", "reindex", "digest", "rotate")
STEPS = (5, 10, 15, 20, 30)


def _matches(expr: str, t: datetime) -> bool:
    minute, hour, _, _, dow = expr.split()
    if dow == "1-5" and t.isoweekday() > 5:
        return False
    if minute.startswith("*/"):
        ok_min = t.minute % int(minute[2:]) == 0
    else:
        ok_min = t.minute == int(minute)
    if "-" in hour:
        h1, h2 = map(int, hour.split("-"))
        ok_hour = h1 <= t.hour <= h2
    else:
        ok_hour = t.hour == int(hour)
    return ok_min and ok_hour


@family(code="sk.devops.cron_next_run", specialization=SPEC, area="linux", level=2, fmt="calc",
        space_size=365 * 24 * 60 * len(JOBS) * 2, median_time_s=75)
def cron_next_run(rng: random.Random) -> Generated:
    if rng.random() < 0.5:
        h1 = rng.randint(7, 10)
        expr = f"*/{rng.choice(STEPS)} {h1}-{rng.randint(h1 + 2, min(h1 + 9, 21))} * * 1-5"
    else:
        expr = f"{rng.randrange(0, 60, 5)} {rng.randint(0, 23)} * * *"
    now = datetime(2026, 1, 1) + timedelta(days=rng.randrange(365), hours=rng.randrange(24),
                                            minutes=rng.randrange(60), seconds=rng.randint(1, 59))
    t = now.replace(second=0) + timedelta(minutes=1)
    while not _matches(expr, t):
        t += timedelta(minutes=1)
    return Generated("text", Prompt(
        text=f"Сейчас {WEEKDAYS[now.weekday()]}, {now:%d.%m.%Y %H:%M:%S}. Когда задание из crontab запустится "
             "в следующий раз?", code=f"{expr} /opt/jobs/{rng.choice(JOBS)}.sh", language="text",
        answer_hint="ДД.ММ ЧЧ:ММ, например 05.03 09:15"), f"{t:%d.%m %H:%M}", ("cron_schedule",))


# --- sk.devops.pipefail_exit ------------------------------------------------------------------
WORDS = ("ERROR", "FAIL", "panic", "timeout", "denied", "fatal", "refused", "crash", "abort", "oom")
TEXTS = ("deploy ok", "build done", "tests passed", "cache warm", "release ready", "sync complete")
BUILDS = 999


def _stage(rng: random.Random, after_writer: bool, first: bool) -> tuple[str, int, bool]:
    """(команда, код выхода, пишет ли в stdout). После пишущей команды — только читающие вход целиком:
    иначе запись упала бы с SIGPIPE (141) и код зависел бы от гонки."""
    if first:
        pool = ["printf", "true", "false", "test", "exit"]
    elif after_writer:
        pool = ["sort", "wc", "grep"]
    else:
        pool = ["true", "false", "test", "exit", "sort", "wc", "grep"]
    kind = rng.choice(pool)
    if kind == "printf":
        return f"printf '{rng.choice(TEXTS)} #{rng.randint(1, BUILDS)}\\n'", 0, True
    if kind == "test":
        a, b = rng.sample(range(1, 100), 2)
        return f"[ {a} -lt {b} ]", int(a >= b), False
    if kind == "exit":
        k = rng.randint(2, 9)
        return f"(exit {k})", k, False
    if kind == "grep":
        return f"grep -q {rng.choice(WORDS)}", 1, False  # слова во входе нет
    if kind == "sort":
        return "sort", 0, after_writer
    if kind == "wc":
        return "wc -l", 0, True
    return kind, int(kind == "false"), False


@family(code="sk.devops.pipefail_exit", specialization=SPEC, area="linux", level=2, fmt="calc",
        # первая команда (printf с текстом и номером сборки, сравнение чисел, true, false, exit 2..9)
        # × две следующие × pipefail
        space_size=(len(TEXTS) * BUILDS + 99 * 98 + 10) * (99 * 98 + len(WORDS) + 12) ** 2 * 2, median_time_s=55)
def pipefail_exit(rng: random.Random) -> Generated:
    while True:  # в конвейере есть команда с числами (printf с номером сборки или сравнение): задания не повторяются
        stages, writer = [], False
        for i in range(rng.randint(2, 3)):
            cmd, code, writer = _stage(rng, writer, i == 0)
            stages.append((cmd, code))
        if any(c.startswith(("printf", "[")) for c, _ in stages):
            break
    pipefail = rng.random() < 0.5
    codes = [c for _, c in stages]
    exit_code = next((c for c in reversed(codes) if c), 0) if pipefail else codes[-1]
    lines = ["#!/bin/bash", *(["set -o pipefail"] if pipefail else []), " | ".join(c for c, _ in stages), "echo $?"]
    return Generated("number", Prompt(text="Какое число выведет echo $? в конце скрипта?", code="\n".join(lines),
                                      language="bash",
                                      answer_hint="Целое число"), exit_code, ("pipeline_exit",))


# --- sk.devops.compose_env_precedence ---------------------------------------------------------
VARS = ("LOG_LEVEL", "APP_MODE", "DB_HOST", "CACHE_TTL", "FEATURE_FLAG", "API_URL", "REGION", "WORKERS")
VALUES = ("debug", "info", "warn", "error", "trace", "prod", "stage", "local", "blue", "green", "fast", "safe")
EMPTY = "(пустая строка)"


def compose_value(env: tuple[str, str | None] | None, env_file: str | None, dockerfile: str | None,
                  shell: str | None, dotenv: str | None) -> str:
    """Правила Compose: environment > env_file > ENV образа. ${X} — из оболочки, иначе из .env, иначе пусто;
    ${X:-d} — d, если X не задана или пуста. Переменные оболочки и .env в контейнер сами не попадают."""
    if env is not None:
        mode, value = env
        if mode == "literal":
            return value
        x = shell if shell is not None else dotenv
        if mode == "default":
            return x if x else value
        return x if x is not None else ""
    return env_file if env_file is not None else dockerfile


@family(code="sk.devops.compose_env_precedence", specialization=SPEC, area="container", level=2, fmt="mcq",
        space_size=len(VARS) * math.perm(len(VALUES), 3) * 4 * 4 * SHUFFLES, median_time_s=80)
def compose_env_precedence(rng: random.Random) -> Generated:
    var = rng.choice(VARS)
    vals = iter(rng.sample(VALUES, len(VALUES)))
    places = rng.sample(("env", "env_file", "dockerfile"), rng.randint(2, 3))
    env = None
    if "env" in places:
        mode = rng.choice(("literal", "interp", "default"))
        env = (mode, next(vals) if mode != "interp" else None)
    env_file = next(vals) if "env_file" in places else None
    dockerfile = next(vals) if "dockerfile" in places else None
    shell = next(vals) if rng.random() < 0.5 else None
    dotenv = next(vals) if rng.random() < 0.5 else None
    if env is not None and env[0] == "interp" and shell is None and dotenv is None:
        # у ${VAR} всегда есть источник: пустая строка из незаданной переменной — ловушка, а не основы
        if rng.random() < 0.5:
            shell = next(vals)
        else:
            dotenv = next(vals)
    key = compose_value(env, env_file, dockerfile, shell, dotenv)

    yml = ["# docker-compose.yml", "services:", "  app:", "    build: ."]
    if env_file is not None:
        yml.append("    env_file: app.env")
    if env is not None:
        mode, value = env
        ref = value if mode == "literal" else f"${{{var}}}" if mode == "interp" else f"${{{var}:-{value}}}"
        yml += ["    environment:", f"      {var}: {ref}"]
    code = yml
    if env_file is not None:
        code += ["# app.env", f"{var}={env_file}"]
    if dockerfile is not None:
        code += ["# Dockerfile", "FROM python:3.12-slim", f"ENV {var}={dockerfile}"]
    if dotenv is not None:
        code += ["# .env", f"{var}={dotenv}"]
    code += ["# запуск", f"$ {var}={shell} docker compose up" if shell is not None else "$ docker compose up"]

    shown = lambda v: v if v else EMPTY  # noqa: E731
    pool = [v for v in (env[1] if env else None, env_file, dockerfile, shell, dotenv) if v is not None]
    others = [shown(v) for v in dict.fromkeys(pool) if shown(v) != shown(key)]
    for filler in (EMPTY, "переменная не задана", *VALUES):
        if len(others) >= 3:
            break
        if filler != shown(key) and filler not in others:
            others.append(filler)
    distractors = rng.sample(others, 3)
    return mcq(rng, f"Какое значение {var} увидит процесс в контейнере app?", shown(key), distractors,
               code="\n".join(code), language="yaml")


# --- sk.devops.rollout_max_pods ---------------------------------------------------------------
DEPLOYMENTS = ("api", "web", "worker", "gateway", "auth", "search", "billing", "notifier", "catalog", "orders")
PERCENTS = tuple(range(10, 55, 5))


def _rollout_value(rng: random.Random) -> str:
    return f'"{rng.choice(PERCENTS)}%"' if rng.random() < 0.6 else str(rng.randint(1, 5))


@family(code="sk.devops.rollout_max_pods", specialization=SPEC, area="container", level=3, fmt="calc",
        space_size=len(DEPLOYMENTS) * 17 * (len(PERCENTS) + 5) ** 2 * 50, median_time_s=60)
def rollout_max_pods(rng: random.Random) -> Generated:
    n = rng.randint(4, 20)
    surge, unavailable = _rollout_value(rng), _rollout_value(rng)
    raw = surge.strip('"')
    extra = math.ceil(n * int(raw[:-1]) / 100) if raw.endswith("%") else int(raw)  # процент maxSurge — вверх
    name = rng.choice(DEPLOYMENTS)
    code = "\n".join([
        "apiVersion: apps/v1", "kind: Deployment", "metadata:", f"  name: {name}", "spec:", f"  replicas: {n}",
        "  strategy:", "    type: RollingUpdate", "    rollingUpdate:", f"      maxSurge: {surge}",
        f"      maxUnavailable: {unavailable}", "  template:", "    spec:", "      containers:",
        f"        - name: {name}", f"          image: registry.local/{name}:1.{rng.randint(0, 49)}.0",
    ])
    return Generated("number", Prompt(
        text="Сколько подов этого Deployment может существовать одновременно во время выката новой версии "
             "(максимум)?", code=code, language="yaml", answer_hint="Целое число"), n + extra, ("rolling_update",))


# --- sk.devops.grep_count ---------------------------------------------------------------------
LEVELS = (("ERROR", "Error", "error"), ("WARN", "Warn", "warn"), ("INFO", "Info", "info"))
MESSAGES = ("user login ok", "db timeout", "retry after error", "cache miss", "payment declined", "job started",
            "job finished", "disk usage 91%", "token expired", "request served", "error budget ok",
            "queue is empty", "info page cached", "slow query 2.3s")
COMMANDS = (("-c", "ERROR"), ("-ci", "error"), ("-vc", "INFO"), ("-c", "WARN"), ("-ci", "warn"), ("-vc", "ERROR"))


@family(code="sk.devops.grep_count", specialization=SPEC, area="linux", level=3, fmt="output",
        space_size=len(COMMANDS) * (9 * len(MESSAGES)) ** 10, median_time_s=70)
def grep_count(rng: random.Random) -> Generated:
    lines = []
    for _ in range(rng.randint(10, 15)):
        level = rng.choice(rng.choice(LEVELS))
        lines.append(f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d} {level} "
                     f"{rng.choice(MESSAGES)}")
    flags, word = rng.choice(COMMANDS)
    hit = [(word.lower() in ln.lower()) if "i" in flags else (word in ln) for ln in lines]
    count = hit.count(False) if "v" in flags else hit.count(True)
    return Generated("number", Prompt(
        text="Что выведет команда для файла app.log (строки файла — в таблице)?", code=f"grep {flags} {word} app.log",
        language="bash", tables=(Table("app.log", ("line",), tuple((ln,) for ln in lines)),),
        answer_hint="Целое число"), count, ("grep_flags",))


# --- sk.devops.ci_needs_order -----------------------------------------------------------------
CI_JOBS = ("lint", "unit", "build", "scan", "package", "e2e", "deploy", "migrate", "notify", "docs", "audit",
           "smoke")


@family(code="sk.devops.ci_needs_order", specialization=SPEC, area="container", level=3, fmt="order",
        space_size=math.perm(len(CI_JOBS), 4) * 24, median_time_s=80)
def ci_needs_order(rng: random.Random) -> Generated:
    order = rng.sample(CI_JOBS, rng.randint(4, 6))  # истинный порядок
    needs = {order[0]: []}
    for i in range(1, len(order)):
        extra = [j for j in order[:i - 1] if rng.random() < 0.4]
        needs[order[i]] = sorted({order[i - 1], *extra}, key=order.index)  # цепочка делает порядок единственным
    shown = rng.sample(order, len(order))
    steps = tuple(f"{j}: needs [{', '.join(needs[j])}]" for j in shown)
    answer = tuple(shown.index(j) + 1 for j in order)
    return Generated("order", Prompt(
        text="Job запускается, когда завершились все job из его needs; одновременно выполняется один job. "
             "В каком порядке они выполнятся?", steps=steps,
        answer_hint="Номера всех job через пробел, например: 2 1 3 …"), answer, ("ci_needs",))


# --- sk.devops.healthcheck_unhealthy ----------------------------------------------------------
INTERVALS = (5, 10, 15, 20, 30)


@family(code="sk.devops.healthcheck_unhealthy", specialization=SPEC, area="container", level=4, fmt="calc",
        space_size=len(INTERVALS) * 4 * 11 * 150 * 50, median_time_s=90)
def healthcheck_unhealthy(rng: random.Random) -> Generated:
    interval = rng.choice(INTERVALS)
    retries = rng.randint(2, 5)
    start = rng.randrange(10, 65, 5)
    while True:
        t_fail = rng.randint(max(start, interval) + 1, start + 150)
        if t_fail % interval:
            break
    first_fail = math.ceil(t_fail / interval)  # проверки в моменты k·interval
    answer = (first_fail + retries - 1) * interval
    code = (f"HEALTHCHECK --interval={interval}s --timeout=3s --start-period={start}s --retries={retries} \\\n"
            f"  CMD curl -f http://localhost:{rng.randint(8000, 8999)}/health || exit 1")
    return Generated("number", Prompt(
        text=f"Проверки мгновенные и идут в моменты interval, 2·interval, … от старта контейнера. Сервис отвечает "
             f"нормально, а через {t_fail} с после старта начинает отвечать ошибкой и больше не восстанавливается. "
             "Через сколько секунд от старта контейнер получит статус unhealthy?", code=code, language="dockerfile",
        answer_hint="Целое число секунд"), answer, ("healthcheck_retries",))
