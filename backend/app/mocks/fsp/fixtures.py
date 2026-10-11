"""Фикстуры мока ФСП: спортсмены, результаты и разряды (исследование 04, §2: модель и демо-персоны).

Люди вымышлены; названия соревнований — по образцу календаря ФСП. Этот же файл берёт засев (без сети).
"""

PASSWORD = "demo"  # пароль всех демо-спортсменов на странице входа мока
AS_OF = "2026-10-01T00:00:00Z"
DEMO_DOMAIN = "athletes.fsp-mock.example"


def _stage(cid: str, title: str, discipline: str, level: str, stage_type: str, fmt: str, day: str,
           field: int) -> dict:
    return {"competition_id": cid, "competition_title": title, "discipline": discipline, "level": level,
            "stage_type": stage_type, "format": fmt, "date": day, "field_size": field,
            "source_url": "https://fsp-russia.ru/calendar/"}


def _res(stage: dict, place: int | None = None, team: dict | None = None, status: str = "OK",
         protocol: str = "FINAL", advanced: bool = False) -> dict:
    return {**stage, "place": place, "team": team, "status": status, "protocol_status": protocol,
            "advanced": advanced}


KR25_FINAL = _stage("kr25-product", "Кубок России по продуктовому программированию 2025, финал", "product",
                    "all_russian", "FINAL", "OFFLINE", "2025-11-22", 20)
KR25_QUAL = _stage("kr25-product-q", "Кубок России по продуктовому программированию 2025, отбор", "product",
                   "all_russian", "QUALIFIER", "ONLINE", "2025-04-20", 340)
LCT24 = _stage("lct24", "Лидеры цифровой трансформации 2024", "product", "international", "SINGLE", "OFFLINE",
               "2024-10-12", 60)
CR25_PRODUCT = _stage("cr25-product", "Чемпионат России по продуктовому программированию 2025, финал", "product",
                      "all_russian", "FINAL", "OFFLINE", "2025-11-28", 30)
PR21_ALGO = _stage("pr21-algo", "Первенство России по алгоритмическому программированию 2021, финал", "algo",
                   "all_russian", "FINAL", "OFFLINE", "2021-11-14", 45)
CFO25_INFOSEC = _stage("cfo25-infosec", "Чемпионат ЦФО по программированию систем ИБ 2025, финал", "infosec",
                       "district", "FINAL", "OFFLINE", "2025-10-05", 25)
CFO25_ALGO = _stage("cfo25-algo", "Чемпионат ЦФО по алгоритмическому программированию 2025, финал", "algo",
                    "district", "FINAL", "OFFLINE", "2025-10-19", 40)
MSK26_ALGO = _stage("msk26-algo", "Чемпионат Москвы по алгоритмическому программированию 2026", "algo",
                    "regional", "SINGLE", "OFFLINE", "2026-09-27", 80)
ONLINE_ALGO = [_stage(f"online-algo-{k}", f"Онлайн-отбор по алгоритмическому программированию, этап {k}", "algo",
                      "all_russian", "QUALIFIER", "ONLINE", f"2025-{k:02d}-15", 500) for k in range(1, 11)]

BYTE_FORCE_25 = {"id": "byte-force-kr25", "name": "Byte Force", "size": 3}
BYTE_FORCE_24 = {"id": "byte-force-lct24", "name": "Byte Force", "size": 3}
NEURAL_NORTH = {"id": "neural-north-cr25", "name": "Neural North", "size": 4}


def _athlete(n: int, given: str, family: str, note: str, results: list, ranks: list) -> dict:
    return {"sub": f"3f6c1e2a-0001-4c00-9000-{n:012d}", "email": f"athlete{n}@{DEMO_DOMAIN}", "given_name": given,
            "family_name": family, "note": note, "results": results, "ranks": ranks}


ATHLETES = [
    _athlete(1, "Анна", "Кузнецова", "КМС, призёр финала Кубка России, команда Byte Force",
             [_res(KR25_FINAL, 2, BYTE_FORCE_25), _res(KR25_QUAL, 7, BYTE_FORCE_25, advanced=True),
              _res(LCT24, 3, BYTE_FORCE_24)],
             [{"rank": "KMS", "assigned_at": "2025-12-20", "valid_until": "2028-12-20"}]),
    _athlete(2, "Борис", "Орлов", "Команда Byte Force: два призовых старта",
             [_res(KR25_FINAL, 2, BYTE_FORCE_25), _res(LCT24, 3, BYTE_FORCE_24)], []),
    _athlete(3, "Вера", "Соколова", "Третий участник Byte Force, ещё не на платформе",
             [_res(KR25_FINAL, 2, BYTE_FORCE_25)], []),
    _athlete(4, "Глеб", "Тихонов", "10 онлайн-отборов без призов",
             [_res(stage, 150 + 7 * k) for k, stage in enumerate(ONLINE_ALGO)], []),
    _athlete(5, "Дарья", "Миронова", "Призёр Первенства России 2021, разряд истёк",
             [_res(PR21_ALGO, 2)], [{"rank": "I", "assigned_at": "2021-12-10", "valid_until": "2023-12-10"}]),
    _athlete(6, "Егор", "Лебедев", "FSP ID есть, результатов нет", [], []),
    _athlete(7, "Жанна", "Исаева", "Дисквалификация и предварительный протокол",
             [_res(CFO25_INFOSEC, None, status="DSQ"), _res(MSK26_ALGO, 1, protocol="PRELIMINARY"),
              _res(CFO25_ALGO, 9)], []),
    _athlete(8, "Иван", "Демидов", "Победитель Чемпионата России, команда Neural North (для гида)",
             [_res(CR25_PRODUCT, 1, NEURAL_NORTH)],
             [{"rank": "KMS", "assigned_at": "2025-12-05", "valid_until": "2028-12-05"}]),
]
_BY_SUB = {a["sub"]: a for a in ATHLETES}


def by_sub(sub: str | None) -> dict | None:
    return _BY_SUB.get(sub or "")


def by_credentials(email: str | None, password: str | None) -> dict | None:
    a = next((x for x in ATHLETES if x["email"] == (email or "").strip().lower()), None)
    return a if a and password == PASSWORD else None


def full_name(a: dict) -> str:
    return f"{a['given_name']} {a['family_name']}".strip()


def payload_for(sub: str) -> dict:
    """Ответ API достижений: снимок с датой `as_of`; у каждой записи — статус протокола (исследование 04, §3)."""
    a = by_sub(sub) or {"sub": sub, "given_name": "", "family_name": "", "results": [], "ranks": []}
    return {"as_of": AS_OF, "athlete": {"sub": a["sub"], "name": full_name(a)}, "results": a["results"],
            "ranks": a["ranks"]}
