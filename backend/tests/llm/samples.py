"""Синтетические резюме для тестов маскирования и разбора (все совпадения с реальными людьми случайны)."""
# ИНН 500100732259 и СНИЛС 112-233-445 95 — с верными контрольными суммами
HH = """Петров Иван Сергеевич
Мужчина, 29 лет, родился 5 мая 1997
+7 (999) 123-45-67 — предпочитаемый способ связи
ivan.petrov@example.ru
Проживает: Казань
Гражданство: Россия, ИНН 500100732259, СНИЛС 112-233-445 95

Желаемая должность и зарплата
Python-разработчик
Занятость: полная занятость
График работы: удаленная работа

Опыт работы — 4 года 2 месяца
Март 2021 — настоящее время
ООО «Ромашка», Backend-разработчик (middle)
Разрабатывал сервисы на Python, FastAPI и PostgreSQL, настроил CI/CD в GitLab CI, Docker, Kafka.
Сентябрь 2019 — Февраль 2021
ООО «Лютик», младший разработчик: Django, Celery, Redis.

Навыки
Python  PostgreSQL  Docker  Kubernetes  Git  REST  квантовый блокчейн
Telegram: @ivan_petrov_dev, GitHub: https://github.com/ivanpetrov
"""

FRONT = """Анна Смирнова
Frontend developer · anna.smirnova@mail.example · 8 912 345 67 89
t.me/anna_front

Опыт
01.2022 – 09.2026 — Senior Frontend, интернет-магазин: React, TypeScript, Redux, Next.js, Jest.
2019 – 2021 — верстальщик: HTML, CSS, Sass, JavaScript.
Формат: гибрид или офис, Санкт-Петербург.
Дата рождения: 12.03.1995
"""

DATA = """Резюме
Аналитик данных
Олег Кузнецов, Новосибирск, +7 913 000 11 22, oleg.k@example.org
Опыт 2 года: SQL, Python (pandas, NumPy), A/B-тесты, Airflow, Tableau, ClickHouse.
Хочу удалёнку.
"""

SAMPLES = {"hh": HH, "front": FRONT, "data": DATA}
PII = {
    "hh": ["Петров", "Иван", "Сергеевич", "999", "123-45-67", "ivan.petrov@example.ru", "500100732259",
           "112-233-445 95", "1997", "@ivan_petrov_dev", "github.com/ivanpetrov"],
    "front": ["Анна", "Смирнова", "anna.smirnova@mail.example", "912 345 67 89", "anna_front", "12.03.1995"],
    "data": ["Олег", "Кузнецов", "913 000 11 22", "oleg.k@example.org"],
}
NAMES = {"hh": ["Петров Иван Сергеевич"], "front": ["Анна Смирнова"], "data": ["Олег Кузнецов"]}
