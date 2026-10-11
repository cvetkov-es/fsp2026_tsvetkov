"""Правила разбора свободного текста (резюме, вакансия) без LLM: формат, город, грейд, специализация, вилка.

Это основной путь на стенде без ключа LLM (процесс 2.2) и фолбэк, когда LLM недоступен.
"""
import re

from app.matching.stack_dict import SPEC_POOL

FORMATS = (("remote", r"удал[её]нн?\w*|remote|дистанц\w*|из дома"), ("hybrid", r"гибрид\w*|hybrid"),
           ("office", r"\bофис\w*|\boffice\b|в офисе"))
CITIES = (
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань", "Нижний Новгород", "Челябинск", "Самара",
    "Омск", "Ростов-на-Дону", "Уфа", "Красноярск", "Воронеж", "Пермь", "Волгоград", "Краснодар", "Саратов",
    "Тюмень", "Тольятти", "Ижевск", "Барнаул", "Ульяновск", "Иркутск", "Хабаровск", "Ярославль", "Владивосток",
    "Махачкала", "Томск", "Оренбург", "Кемерово", "Новокузнецк", "Рязань", "Набережные Челны", "Астрахань",
    "Пенза", "Киров", "Липецк", "Чебоксары", "Калининград", "Тула", "Курск", "Сочи", "Ставрополь", "Иннополис",
)
_CITY_ALIASES = {"спб": "Санкт-Петербург", "питер": "Санкт-Петербург", "мск": "Москва", "нск": "Новосибирск",
                 "екб": "Екатеринбург"}
GRADE_WORDS = (
    # «ведущий/старший» и lead — только рядом с ролью: «ведущие компании» и «lead generation» не грейд
    ("senior", r"\b(?:senior|сеньор\w*|синьор\w*|тимлид\w*|техлид\w*|(?:team|tech)[\s-]?lead|lead\s+(?:developer|engineer|analyst)"
               r"|(?:ведущ|старш)\w*\s+(?:разработчик|инженер|аналитик|программист|специалист)\w*)\b"),
    ("middle", r"\b(?:middle|мидл\w*)\b"),
    ("junior", r"\b(?:junior|джун\w*|младш\w*|стаж[её]р\w*|intern)\b"),
)
SPEC_WORDS = {
    "backend": r"\b(?:backend|бэкенд\w*|бекенд\w*|back-end|серверн\w*)",
    "frontend": r"\b(?:frontend|фронтенд\w*|front-end|верст\w*)",
    "data": r"\b(?:аналитик\w*|analyst|data|данных|ml\b|machine learning|машинн\w+ обучен\w*)",
}


def formats_in(text: str) -> list[str]:
    return [code for code, rx in FORMATS if re.search(rx, text, re.I)]


def city_in(text: str) -> str | None:
    m = re.search(r"(?:Проживает|Город|Местоположение|Location)\s*:\s*([А-ЯЁ][а-яё]+(?:[\s-][А-ЯЁа-яё]+){0,2})", text)
    if m:
        head = m.group(1).strip()
        for city in CITIES:
            if head.startswith(city):
                return city
        return head.split(",")[0][:80]
    for city in CITIES:
        if re.search(rf"(?<![\w-]){re.escape(city)}(?![\w-])", text):
            return city
    for alias, city in _CITY_ALIASES.items():
        if re.search(rf"(?<![\w-]){alias}(?![\w-])", text, re.I):
            return city
    return None


def grades_in(text: str) -> list[str]:
    """Все упомянутые грейды; «middle+» добавляет senior."""
    found = [g for g, rx in GRADE_WORDS if re.search(rx, text, re.I)]
    if re.search(r"(?:middle|мидл)\s*\+", text, re.I) and "senior" not in found:
        found.append("senior")
    order = ("junior", "middle", "senior")
    return sorted(found, key=order.index)


def specialization_in(text: str, techs: list[str]) -> str | None:
    score = {spec: 2 * len(re.findall(rx, text, re.I)) for spec, rx in SPEC_WORDS.items()}
    for spec, pool in SPEC_POOL.items():
        score[spec] += sum(1 for t in techs if t in pool)
    best = max(score.values())
    leaders = [s for s, v in score.items() if v == best]
    return leaders[0] if best > 0 and len(leaders) == 1 else None


_NUM = r"\d{1,3}(?:[\s ]?\d{3})*(?:[.,]\d+)?"
_UNIT = r"(?:тыс\.?|т\.р\.?|k|к)(?![а-яa-z])"
_RANGE = re.compile(rf"(?:от\s*)?(?P<a>{_NUM})\s*(?P<ua>{_UNIT})?\s*(?:[—–-]|до)\s*(?P<b>{_NUM})\s*(?P<ub>{_UNIT})?", re.I)
_FROM = re.compile(rf"\bот\s*(?P<a>{_NUM})\s*(?P<ua>{_UNIT})?", re.I)
_TO = re.compile(rf"\bдо\s*(?P<b>{_NUM})\s*(?P<ub>{_UNIT})?", re.I)
SALARY_MIN, SALARY_MAX = 10_000, 10_000_000


def _money(num: str | None, unit: str | None) -> int | None:
    if not num:
        return None
    value = float(re.sub(r"[\s ]", "", num).replace(",", "."))
    if unit:
        value *= 1000
    v = int(round(value))
    return v if SALARY_MIN <= v <= SALARY_MAX else None


def salary_in(text: str) -> tuple[int | None, int | None]:
    """Вилка из текста: «от 200 000 до 300 000 ₽», «200–300 тыс.», «до 350к». Опыт «от 3 до 5 лет» отсекается порогом суммы."""
    for m in _RANGE.finditer(text):
        unit_b = m.group("ub")
        a, b = _money(m.group("a"), m.group("ua") or unit_b), _money(m.group("b"), unit_b)
        if a and b and a <= b:
            return a, b
    lo = next((v for m in _FROM.finditer(text) if (v := _money(m.group("a"), m.group("ua")))), None)
    hi = next((v for m in _TO.finditer(text) if (v := _money(m.group("b"), m.group("ub")))), None)
    return lo, hi


def gross_net_in(text: str) -> str | None:
    if re.search(r"на руки|\bnet\b|чистыми|после вычета", text, re.I):
        return "net"
    if re.search(r"gross|до вычета|до налог|брутто|до ндфл", text, re.I):
        return "gross"
    return None
