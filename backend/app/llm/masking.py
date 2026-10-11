"""Маскирование ПДн перед LLM (исследование 06, §2): контакты — регулярками, ФИО — списком имён.

Найденное остаётся локально в Masked.found (из него черновик профиля берёт контакты), наружу уходит только text.
"""
import re
from dataclasses import dataclass, field

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"(?:https?://|www\.)\S+|\b(?:t\.me|telegram\.me|github\.com|gitlab\.com|linkedin\.com|hh\.ru|"
                 r"vk\.com|habr\.com|career\.habr\.com)/\S+", re.I)
HANDLE = re.compile(r"(?<![\w.])@[A-Za-z][A-Za-z0-9_]{2,31}\b(?!/)")  # @scope/package — пакет, а не ник
PHONE = re.compile(r"(?<![\d+])(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)"
                   r"|(?<![\d+])\+\d{1,3}[\s(-]*\d{2,4}[\s)-]*\d{3}[\s-]*\d{2,4}(?:[\s-]*\d{2,4})?(?!\d)")
DIGIT_RUN = re.compile(r"(?<!\d)\d(?:[ -]?\d){9,13}(?!\d)")  # кандидаты в ИНН и СНИЛС
MONTH = r"(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я]*"
BIRTH = re.compile(rf"(?i)(?:дата рождения|родил(?:ся|ась)|д\.\s?р\.)\s*:?\s*(?:\d{{1,2}}[.\s]+(?:\d{{1,2}}|{MONTH})[.\s]+)?"
                   rf"(?:19|20)\d{{2}}(?:\s*г(?:ода|\.)?)?")
TAGS = {"email": "[EMAIL]", "url": "[ССЫЛКА]", "handle": "[НИК]", "birth": "[ДАТА РОЖДЕНИЯ]", "snils": "[СНИЛС]",
        "inn": "[ИНН]", "number": "[НОМЕР]", "phone": "[ТЕЛЕФОН]", "name": "[ИМЯ]"}


def inn_ok(d: str) -> bool:
    def check(weights: tuple[int, ...]) -> int:
        return sum(int(x) * w for x, w in zip(d, weights, strict=False)) % 11 % 10

    if len(d) == 10:
        return check((2, 4, 10, 3, 5, 9, 4, 6, 8)) == int(d[9])
    if len(d) == 12:
        return (check((7, 2, 4, 10, 3, 5, 9, 4, 6, 8)) == int(d[10])
                and check((3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)) == int(d[11]))
    return False


def snils_ok(d: str) -> bool:
    if len(d) != 11:
        return False
    total = sum(int(x) * w for x, w in zip(d[:9], range(9, 0, -1), strict=True))
    control = total if total < 100 else (0 if total in (100, 101) else total % 101 % 100)
    return control == int(d[9:])


@dataclass
class Masked:
    text: str
    found: dict[str, list[str]] = field(default_factory=dict)


def mask(text: str, names: list[str] | None = None) -> Masked:
    found: dict[str, list[str]] = {}

    def sub(kind: str, pattern: re.Pattern, s: str, check=None) -> str:
        def repl(m: re.Match) -> str:
            value = m.group(0)
            if check and not check(re.sub(r"\D", "", value)):
                return value
            found.setdefault(kind, []).append(value.strip())
            return TAGS[kind]

        return pattern.sub(repl, s)

    s = sub("email", EMAIL, text)
    s = sub("url", URL, s)
    s = sub("handle", HANDLE, s)
    s = sub("birth", BIRTH, s)
    s = sub("snils", DIGIT_RUN, s, snils_ok)
    s = sub("inn", DIGIT_RUN, s, inn_ok)
    s = sub("phone", PHONE, s)
    s = sub("number", DIGIT_RUN, s)  # длинные номера без контрольной суммы (паспорт, водительское) тоже убираем
    for name in names or []:
        for part in sorted({name, *name.split()}, key=len, reverse=True):
            if len(part) < 3:
                continue
            s, n = re.subn(rf"(?<![\w-]){re.escape(part)}(?![\w-])", TAGS["name"], s)
            if n:
                found.setdefault("name", []).append(part)
    return Masked(s, found)


def contacts_from(found: dict[str, list[str]]) -> dict[str, str]:
    """Контакты для черновика профиля: из того, что маскирование нашло локально."""
    out: dict[str, str] = {}
    if found.get("email"):
        out["email"] = found["email"][0]
    if found.get("phone"):
        out["phone"] = found["phone"][0]
    tg = [u for u in found.get("url", []) if re.search(r"t(?:elegram)?\.me/", u, re.I)]
    if tg:
        out["telegram"] = "@" + tg[0].rstrip("/").rsplit("/", 1)[-1]
    elif found.get("handle"):
        out["telegram"] = found["handle"][0]
    gh = [u for u in found.get("url", []) if "github.com/" in u.lower()]
    if gh:
        out["github"] = gh[0]
    return out
