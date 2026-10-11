"""Подключение всех модулей семейств. Новый модуль добавляется в _MODULES."""
import importlib

_MODULES: tuple[str, ...] = (
    "backend_db", "backend_lang", "backend_http", "backend_debug", "backend_arch",
    "frontend_js", "frontend_markup", "frontend_framework", "frontend_browser", "frontend_debug",
    "data_sql", "data_stats", "data_python", "data_metrics", "data_quality",
    "skill_sql", "skill_devops", "skill_frontend_basics", "skill_backend_basics", "skill_ml_basics",
    "skill_ai_python", "skill_ai_sql", "skill_ai_clarify",
)


def load_all() -> None:
    for name in _MODULES:
        importlib.import_module(f"app.assessment.bank.families.{name}")
