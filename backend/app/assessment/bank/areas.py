"""Области (blueprint) по специализациям — процесс v4, 3.1."""
AREAS: dict[str, tuple[str, ...]] = {
    "backend": ("lang", "http", "db", "arch", "debug"),
    "frontend": ("js", "markup", "framework", "browser", "debug"),
    "data": ("sql", "stats", "python", "metrics", "quality"),
}

AREA_TITLES: dict[str, str] = {
    "lang": "Язык и рантайм", "http": "HTTP и API", "db": "БД и SQL",
    "arch": "Архитектура и надёжность", "debug": "Отладка и тестирование",
    "js": "JS/TS", "markup": "HTML, CSS, доступность", "framework": "Фреймворк и состояние",
    "browser": "Браузер и сеть", "sql": "SQL и модели данных",
    "stats": "Статистика и эксперименты", "python": "Python для данных",
    "metrics": "Метрики и продуктовая аналитика", "quality": "Качество данных и пайплайны",
}
