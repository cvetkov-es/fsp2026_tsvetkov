"""Навыки MVP (процесс 2.5). «Работа с ИИ» — отдельный формат, план 07a3."""
from dataclasses import dataclass

from app.matching.stack_dict import SKILL_TITLES

SKILL_PREFIX = "skill:"


@dataclass(frozen=True)
class Skill:
    code: str
    title: str
    summary: str
    areas: tuple[str, ...]  # области: тест навыка чередует две, «Работа с ИИ» — свои три


def _skill(code: str, summary: str, areas: tuple[str, ...]) -> Skill:
    return Skill(code, SKILL_TITLES[code], summary, areas)  # названия — из словаря стека (план 04)


SKILLS: dict[str, Skill] = {s.code: s for s in (
    _skill("sql", "Выборки, соединения, группировки, NULL, ограничения и транзакции", ("query", "model")),
    _skill("devops", "Docker и Compose, Kubernetes, Linux, cron, CI", ("container", "linux")),
    _skill("frontend_basics", "JavaScript, HTML и CSS: базовая семантика", ("js", "markup")),
    _skill("backend_basics", "HTTP, REST, форматы данных, повторы запросов", ("http", "api")),
    _skill("ml_basics", "pandas и NumPy, разбиение выборки, метрики, утечка данных", ("data", "model")),
)}

AI_SKILL_CODE = "ai"
# «Работа с ИИ» — свой формат (вердикты, общий таймер), поэтому не в SKILLS: там только тесты из SKILL_LEN заданий
CATALOG: dict[str, Skill] = {**SKILLS, AI_SKILL_CODE: _skill(
    AI_SKILL_CODE, "ИИ разрешён: найти ошибки в готовых решениях и вовремя уточнить требование",
    ("python", "sql", "clarify"))}


def skill_spec(code: str) -> str:
    return f"{SKILL_PREFIX}{code}"


def skill_code(spec: str | None) -> str | None:
    return spec[len(SKILL_PREFIX):] if spec and spec.startswith(SKILL_PREFIX) else None
