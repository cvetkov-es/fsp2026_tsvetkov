from app.matching.stack_dict import find_techs
from app.matching.text_rules import (
    city_in,
    formats_in,
    grades_in,
    gross_net_in,
    salary_in,
    specialization_in,
)


def test_find_techs_ngrams_hyphens_and_ambiguous():
    text = ("Python-разработчик: FastAPI, PostgreSQL; MS SQL Server, Spring Boot, CI/CD, A/B-тесты, Node.js. "
            "Пишу на Go и JS. Курсор в базе, next шаг, го гулять")
    found = find_techs(text)
    for t in ("Python", "FastAPI", "PostgreSQL", "MS SQL Server", "Spring", "CI/CD", "A/B-тесты", "Node.js", "Go",
              "JavaScript"):
        assert t in found, t
    assert "Cursor" not in found and "Next.js" not in found


def test_formats_city_grades():
    assert formats_in("График: удаленная работа, возможен гибрид") == ["remote", "hybrid"]
    assert city_in("Проживает: Казань, готов к переезду") == "Казань"
    assert city_in("Работаю из СПб") == "Санкт-Петербург" and city_in("нет города") is None
    assert grades_in("Ищем middle+ разработчика") == ["middle", "senior"]
    assert grades_in("Junior или Middle") == ["junior", "middle"]


def test_specialization_guess():
    assert specialization_in("Бэкенд-разработчик", ["Python", "PostgreSQL"]) == "backend"
    assert specialization_in("Аналитик данных", ["SQL", "pandas"]) == "data"
    assert specialization_in("", []) is None


def test_salary_patterns_and_experience_ignored():
    assert salary_in("от 200 000 до 300 000 ₽ на руки") == (200_000, 300_000)
    assert salary_in("Вилка 200–300 тыс. gross") == (200_000, 300_000)
    assert salary_in("Опыт от 3 до 5 лет. Зарплата до 350к") == (None, 350_000)
    assert salary_in("от 180 000 руб.") == (180_000, None)
    assert gross_net_in("до вычета НДФЛ") == "gross" and gross_net_in("на руки") == "net" and gross_net_in("") is None


def test_senior_words_need_a_role_context():
    assert grades_in("Работали с ведущими компаниями рынка, занимались lead generation") == []
    assert grades_in("Ведущий разработчик") == ["senior"] and grades_in("Team Lead бэкенда") == ["senior"]
