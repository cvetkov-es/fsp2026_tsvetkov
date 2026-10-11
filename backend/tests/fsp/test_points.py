from datetime import date

import pytest

from app.fsp.points import FspRankRec, FspRes, parse, points, rank_valid, summary, tier
from app.matching.scoring import fsp_f
from app.mocks.fsp.fixtures import ATHLETES, payload_for

TODAY = date(2026, 10, 10)
SUB = {a["family_name"]: a["sub"] for a in ATHLETES}


def pts(family: str) -> float:
    results, ranks = parse(payload_for(SUB[family]))
    return points(results, ranks, TODAY)


def test_points_follow_process_table():
    assert pts("Кузнецова") == pytest.approx(4.3)  # 2 призовых + онлайн-отбор в 1 дисциплине; КМС (2) меньше
    assert pts("Орлов") == pytest.approx(4.0)  # командные места — каждому участнику те же баллы
    assert pts("Тихонов") == pytest.approx(0.3)  # 10 онлайн-отборов — одна строка на дисциплину
    assert pts("Миронова") == pytest.approx(2.0)  # разряд I истёк и не считается
    assert pts("Исаева") == pytest.approx(1.0)  # DSQ и предварительный протокол не в баллах
    assert pts("Демидов") == pytest.approx(3.0)  # Σ = max(результаты 3, КМС 2)
    assert pts("Лебедев") == 0.0
    assert fsp_f(pts("Тихонов")) < 0.06  # фармер онлайн-отборов почти ничего не получает


def test_rank_alone_and_lifetime_ms():
    assert points([], [FspRankRec("MS", date(2010, 1, 1), None)], TODAY) == 3.0
    assert rank_valid("MS", None, TODAY) and not rank_valid("KMS", date(2026, 1, 1), TODAY)


def test_tiers():
    base = dict(competition_id="c", competition_title="t", discipline="algo", level="", date=TODAY, field_size=10,
                team_id=None, team_name=None, team_size=None, status="OK", protocol_status="FINAL")
    assert tier(FspRes(stage_type="QUALIFIER", place=1, **base)) == "online"
    assert tier(FspRes(stage_type="FINAL", place=1, **base)) == "winner"
    assert tier(FspRes(stage_type="FINAL", place=3, **base)) == "prize"
    assert tier(FspRes(stage_type="FINAL", place=9, **base)) == "finalist"
    assert tier(FspRes(stage_type="SINGLE", place=9, **base)) == "participant"


def test_summary_lines():
    r, k = parse(payload_for(SUB["Кузнецова"]))
    assert summary(r, k, TODAY) == ("ФСП: призёр 2 стартов, онлайн-отборы в 1 дисциплине, КМС до 12.2028; "
                                    "в составе команды «Byte Force» (3 чел., 2 место из 20)")
    r, k = parse(payload_for(SUB["Демидов"]))
    assert summary(r, k, TODAY).endswith("в составе команды «Neural North» (4 чел., 1 место из 30)")
    r, k = parse(payload_for(SUB["Тихонов"]))
    assert summary(r, k, TODAY) == "ФСП: онлайн-отборы в 1 дисциплине"
    r, k = parse(payload_for(SUB["Лебедев"]))
    assert summary(r, k, TODAY) is None  # «нет истории» — не «0 достижений»
