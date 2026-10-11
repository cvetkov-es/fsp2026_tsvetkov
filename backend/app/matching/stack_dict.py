"""Канонический словарь технологий (по категориям Stack Overflow Survey) с русскими синонимами."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Tech:
    canonical: str
    category: str
    synonyms: tuple[str, ...] = ()
    implies: tuple[str, ...] = ()
    skill: str | None = None


_RAW: tuple[Tech, ...] = (
    # языки
    Tech("Python", "lang", ("py", "python3", "питон", "пайтон")),
    Tech("Java", "lang", ("джава",)),
    Tech("Kotlin", "lang", ("котлин",), ("Java",)),
    Tech("Go", "lang", ("golang", "го")),
    Tech("C#", "lang", ("csharp", "c sharp", "шарп")),
    Tech("C++", "lang", ("cpp", "плюсы")),
    Tech("PHP", "lang", ("пхп",)),
    Tech("Ruby", "lang", ("руби",)),
    Tech("JavaScript", "lang", ("js", "javascript", "джаваскрипт", "ecmascript"), skill="frontend_basics"),
    Tech("TypeScript", "lang", ("ts", "тайпскрипт"), ("JavaScript",)),
    Tech("SQL", "lang", ("эскьюэль",), skill="sql"),
    Tech("R", "lang", ()),
    Tech("Scala", "lang", ("скала",)),
    Tech("Rust", "lang", ("раст",)),
    # бэкенд-фреймворки
    Tech("Django", "framework", ("джанго",), ("Python",)),
    Tech("FastAPI", "framework", ("fast api", "фастапи"), ("Python",)),
    Tech("Flask", "framework", ("фласк",), ("Python",)),
    Tech("Spring", "framework", ("spring boot", "спринг"), ("Java",)),
    Tech("ASP.NET", "framework", ("aspnet", "asp net", ".net", "dotnet"), ("C#",)),
    Tech("Node.js", "framework", ("node", "nodejs", "нода"), ("JavaScript",)),
    Tech("NestJS", "framework", ("nest",), ("Node.js", "TypeScript")),
    Tech("Express", "framework", ("expressjs",), ("Node.js",)),
    Tech("Laravel", "framework", ("ларавель",), ("PHP",)),
    Tech("Gin", "framework", (), ("Go",)),
    # фронтенд
    Tech("React", "frontend", ("reactjs", "react.js", "реакт"), ("JavaScript",)),
    Tech("Vue", "frontend", ("vuejs", "vue.js", "вью"), ("JavaScript",)),
    Tech("Angular", "frontend", ("ангуляр",), ("TypeScript",)),
    Tech("Next.js", "frontend", ("nextjs", "next"), ("React",)),
    Tech("Redux", "frontend", ("редакс",), ("React",)),
    Tech("HTML", "frontend", ("html5",), skill="frontend_basics"),
    Tech("CSS", "frontend", ("css3",), skill="frontend_basics"),
    Tech("Tailwind CSS", "frontend", ("tailwind",), ("CSS",)),
    Tech("Sass", "frontend", ("scss",), ("CSS",)),
    Tech("Webpack", "frontend", ("вебпак",)),
    Tech("Vite", "frontend", ("вите",)),
    Tech("Jest", "testing", ("джест",), ("JavaScript",)),
    Tech("Playwright", "testing", ()),
    Tech("pytest", "testing", ("пайтест",), ("Python",)),
    # базы данных и хранилища
    Tech("PostgreSQL", "db", ("postgres", "postgresql", "pg", "постгрес", "постгре"), ("SQL",), "sql"),
    Tech("MySQL", "db", ("мускул", "майскл"), ("SQL",), "sql"),
    Tech("SQLite", "db", (), ("SQL",)),
    Tech("Oracle", "db", ("оракл",), ("SQL",)),
    Tech("MS SQL Server", "db", ("mssql", "sql server"), ("SQL",), "sql"),
    Tech("ClickHouse", "db", ("кликхаус", "clickhouse"), ("SQL",), "sql"),
    Tech("MongoDB", "db", ("mongo", "монго")),
    Tech("Redis", "db", ("редис",)),
    Tech("Elasticsearch", "db", ("elastic", "эластик")),
    Tech("Cassandra", "db", ("кассандра",)),
    # очереди и интеграции
    Tech("Kafka", "messaging", ("apache kafka", "кафка")),
    Tech("RabbitMQ", "messaging", ("rabbit", "рэббит", "кролик")),
    Tech("gRPC", "messaging", ("grpc",), skill="backend_basics"),
    Tech("REST", "messaging", ("rest api", "restful", "рест"), skill="backend_basics"),
    Tech("GraphQL", "messaging", ("графкуэль",)),
    Tech("Celery", "messaging", ("селери",), ("Python",)),
    # DevOps
    Tech("Docker", "devops", ("докер",), skill="devops"),
    Tech("Kubernetes", "devops", ("k8s", "кубер", "кубернетес"), ("Docker",), "devops"),
    Tech("Git", "devops", ("гит",)),
    Tech("Linux", "devops", ("линукс",), skill="devops"),
    Tech("CI/CD", "devops", ("ci", "cicd", "ci cd"), skill="devops"),
    Tech("GitLab CI", "devops", ("gitlab-ci",), ("CI/CD", "Git")),
    Tech("GitHub Actions", "devops", (), ("CI/CD", "Git")),
    Tech("Terraform", "devops", ("терраформ",)),
    Tech("Ansible", "devops", ("ансибл",)),
    Tech("Nginx", "devops", ("энджинкс", "нджинкс")),
    Tech("Prometheus", "devops", ("прометей",)),
    Tech("Grafana", "devops", ("графана",)),
    Tech("AWS", "devops", ("амазон",)),
    Tech("Yandex Cloud", "devops", ("яндекс облако", "yc")),
    # данные и ML
    Tech("pandas", "data", ("пандас",), ("Python",), "ml_basics"),
    Tech("NumPy", "data", ("numpy", "нампай"), ("Python",), "ml_basics"),
    Tech("scikit-learn", "data", ("sklearn", "склерн"), ("Python",), "ml_basics"),
    Tech("PyTorch", "data", ("torch", "торч"), ("Python",)),
    Tech("TensorFlow", "data", ("tf", "тензорфлоу"), ("Python",)),
    Tech("Airflow", "data", ("apache airflow", "эйрфлоу")),
    Tech("Spark", "data", ("pyspark", "apache spark", "спарк")),
    Tech("dbt", "data", ()),
    Tech("Jupyter", "data", ("jupyter notebook", "юпитер")),
    Tech("Tableau", "data", ("таблоу",)),
    Tech("Power BI", "data", ("powerbi",)),
    Tech("Superset", "data", ("apache superset",)),
    Tech("Excel", "data", ("эксель",)),
    Tech("A/B-тесты", "data", ("ab tests", "a/b", "аб тесты", "a/b testing")),
    Tech("Статистика", "data", ("statistics", "матстат")),
    # ИИ-инструменты
    Tech("LLM API", "ai", ("openai api", "gigachat api", "yandexgpt api"), skill="ai"),
    Tech("Copilot", "ai", ("github copilot",), skill="ai"),
    Tech("Cursor", "ai", ("курсор",), skill="ai"),
    Tech("Claude Code", "ai", ("claude",), skill="ai"),
    Tech("LangChain", "ai", ("лэнгчейн",), ("Python",)),
)

TECHS: dict[str, Tech] = {t.canonical: t for t in _RAW}


def _key(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


_INDEX: dict[str, str] = {}
for _t in _RAW:
    for _name in (_t.canonical, *_t.synonyms):
        _INDEX[_key(_name)] = _t.canonical

# Что подтверждает основной тест специализации: области банка (AREAS) и язык заданий
# (Backend — Python, процесс 3.1 и план 03b; Frontend — JS; Data — Python и SQL)
SPEC_CORE: dict[str, tuple[str, ...]] = {
    "backend": ("Python", "SQL", "REST"),
    "frontend": ("JavaScript", "HTML", "CSS"),
    "data": ("SQL", "Python", "Статистика"),
}

SKILL_TECHS: dict[str, tuple[str, ...]] = {
    "sql": tuple(t.canonical for t in _RAW if t.skill == "sql"),
    "devops": tuple(t.canonical for t in _RAW if t.skill == "devops"),
    "frontend_basics": tuple(t.canonical for t in _RAW if t.skill == "frontend_basics"),
    "backend_basics": tuple(t.canonical for t in _RAW if t.skill == "backend_basics"),
    "ml_basics": tuple(t.canonical for t in _RAW if t.skill == "ml_basics"),
    "ai": tuple(t.canonical for t in _RAW if t.skill == "ai"),
}

SKILL_TITLES: dict[str, str] = {
    "sql": "SQL", "devops": "DevOps и контейнеры", "frontend_basics": "Основы фронтенда",
    "backend_basics": "Основы бэкенда", "ml_basics": "Основы ML", "ai": "Работа с ИИ",
}

SPEC_POOL: dict[str, tuple[str, ...]] = {
    "backend": ("Python", "Django", "FastAPI", "Java", "Spring", "Go", "Node.js", "PostgreSQL", "MySQL",
                "Redis", "Kafka", "RabbitMQ", "Docker", "Kubernetes", "Git", "Linux", "REST", "gRPC",
                "CI/CD", "ClickHouse", "Celery", "Nginx"),
    "frontend": ("JavaScript", "TypeScript", "React", "Vue", "Angular", "Next.js", "Redux", "HTML",
                 "CSS", "Tailwind CSS", "Sass", "Webpack", "Vite", "Jest", "Playwright", "Git",
                 "GraphQL", "REST"),
    "data": ("Python", "SQL", "pandas", "NumPy", "scikit-learn", "PyTorch", "Airflow", "Spark", "dbt",
             "ClickHouse", "PostgreSQL", "Jupyter", "Tableau", "Power BI", "Superset", "Excel",
             "A/B-тесты", "Статистика"),
}


def normalize(term: str) -> str | None:
    return _INDEX.get(_key(term))


def normalize_many(terms) -> tuple[list[str], list[str]]:
    known, unknown = [], []
    for term in terms:
        canon = normalize(term)
        if canon is None:
            if term.strip() and term.strip() not in unknown:
                unknown.append(term.strip())
        elif canon not in known:
            known.append(canon)
    return known, unknown


def expand(states: dict[str, str]) -> dict[str, str]:
    out = dict(states)
    stack = list(states.items())
    while stack:
        tech, state = stack.pop()
        for imp in TECHS[tech].implies if tech in TECHS else ():
            if out.get(imp) != "confirmed" and (state == "confirmed" or imp not in out):
                out[imp] = state
                stack.append((imp, state))
    return out


# Синонимы, которые в свободном тексте совпадают с обычными словами («го», «next», «курсор», «excel»).
# Одиночный такой токен засчитывается, только если он латиницей и с заглавной: Go, R, REST, JS, Node.
_AMBIGUOUS = frozenset({
    "го", "go", "r", "ci", "pg", "tf", "next", "node", "nest", "ts", "js", "py", "yc", "rest", "spring",
    "express", "gin", "elastic", "rabbit", "кролик", "claude", "cursor", "excel", "jest", "vite", "spark",
    "git", "sass", "dbt", "torch", "a/b", "рест", "нода", "вью", "вите", "гит", "курсор", "эксель",
})
_TOKEN = re.compile(r"[A-Za-zА-Яа-яЁё0-9#+./-]+")


def find_techs(text: str) -> list[str]:
    """Технологии из словаря в свободном тексте: n-граммы до трёх слов, «Python-разработчик» → Python."""
    tokens = [t.rstrip(".,-/") for t in _TOKEN.findall(text)]
    tokens = [t for t in tokens if t]
    found: list[str] = []
    i = 0
    while i < len(tokens):
        step = 1
        for n in (3, 2, 1):
            chunk = tokens[i:i + n]
            if len(chunk) < n:
                continue
            key = _key(" ".join(chunk))
            canon = _INDEX.get(key)
            if canon is None and n == 1 and "-" in chunk[0]:
                key = _key(chunk[0].split("-", 1)[0])
                canon = _INDEX.get(key)
            ambiguous = n == 1 and key in _AMBIGUOUS and not (chunk[0][0].isascii() and chunk[0][0].isupper())
            if canon is None or ambiguous:
                continue
            if canon not in found:
                found.append(canon)
            step = n
            break
        i += step
    return found
