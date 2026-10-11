from sqlalchemy import func, select

from app.auth.models import User
from app.auth.service import create_session
from app.candidates.models import CandidateProfile
from app.demo.seed import (
    DEMO_COMPANY,
    FSP_ATHLETES,
    INTERNSHIP_TITLE,
    JUNIOR,
    MARKET,
    STRONG,
    VOTERS,
    WEAK,
    seed_all,
)
from app.employers.models import Company, Need


def test_seed_small_and_idempotent(db):
    r = seed_all(db, n_per_cell=4)
    assert r.pop("votes") > 0  # история найма: голоса трёх компаний (план 07b1)
    assert r == {"candidates": 3 * 3 * 4 + 2 + len(FSP_ATHLETES) + 1, "needs": 4}  # +1 юный кандидат, +1 стажировка демо-компании
    assert seed_all(db, n_per_cell=4) == {"skipped": True}
    statuses = set(db.scalars(select(CandidateProfile.grade_status).where(CandidateProfile.synthetic.is_(True))))
    assert statuses == {"confirmed", "not_confirmed"}
    assert db.scalar(select(func.count()).select_from(Need)) == 3 * (1 + len(VOTERS) + len(MARKET)) + 1  # демо-компания, компании засева, рынок для спроса и стажировка


def _demo_need(db, spec: str) -> Need:
    return db.scalar(select(Need).join(Company, Company.id == Need.company_id)
                     .where(Company.name == DEMO_COMPANY, Need.specialization == spec, Need.employment == "full"))


def test_guide_personas_strong_test_above_fsp_prize(db, client):
    seed_all(db, n_per_cell=4)
    emp = db.scalar(select(User).where(User.email == "demo.employer@fsp-hiring.local"))
    client.cookies.set("fsp_session", create_session(db, emp))
    need = _demo_need(db, "backend")
    blocks = client.get(f"/api/v1/employer/needs/{need.id}/selection").json()["blocks"]
    order = [i["ref"] for b in blocks for i in b["items"]]
    refs = {p.full_name: p.public_ref for p in db.scalars(
        select(CandidateProfile).where(CandidateProfile.full_name.in_((STRONG, WEAK))))}
    assert order.index(refs[STRONG]) < order.index(refs[WEAK])
    s = {p.full_name: p.s_cache for p in db.scalars(
        select(CandidateProfile).where(CandidateProfile.full_name.in_((STRONG, WEAK))))}
    assert s == {STRONG: 0.79, WEAK: 0.51}  # контрольный случай 1 процесса (6.4)


def test_seed_hiring_history_shows_badges_and_a_board(db, client):
    seed_all(db, n_per_cell=4)
    emp = db.scalar(select(User).where(User.email == "demo.employer@fsp-hiring.local"))
    client.cookies.set("fsp_session", create_session(db, emp))
    need = _demo_need(db, "backend")
    cards = [i for b in client.get(f"/api/v1/employer/needs/{need.id}/selection").json()["blocks"] for i in b["items"]]
    assert any(c["interview_badge"] == "Подтверждено на собеседованиях (3)" for c in cards)
    board = client.get(f"/api/v1/employer/needs/{need.id}/board").json()
    assert "offer" in {c["stage"] for c in board["cards"]} and board["votes_used"] == 0  # голоса засева — старше 30 дней


def test_seed_links_fsp_athletes_and_team(db):
    from app.fsp.teams import prize_teams

    seed_all(db, n_per_cell=2)
    teams = prize_teams(db)
    assert teams and teams[0]["team_name"] == "Byte Force" and teams[0]["on_platform"] == 2
    by_name = {p.full_name: p for p in db.scalars(select(CandidateProfile).where(
        CandidateProfile.full_name.in_(("Глеб Тихонов", "Егор Лебедев", "Анна Кузнецова"))))}
    assert by_name["Глеб Тихонов"].fsp_f < 0.06 and by_name["Егор Лебедев"].fsp_status == "LINKED_EMPTY"
    assert by_name["Анна Кузнецова"].fsp_summary.startswith("ФСП: призёр 2 стартов")


def test_seed_reviewed_persona_has_reviews_and_an_open_dispute(db, client):
    from app.demo.seed import REVIEWED
    from app.moderation.models import Case

    seed_all(db, n_per_cell=12)
    u = db.scalar(select(User).where(User.email == REVIEWED))
    assert u is not None and u.is_demo
    client.cookies.set("fsp_session", create_session(db, u))
    states = sorted(r["state"] for r in client.get("/api/v1/candidate/reviews").json())
    assert states == ["active", "disputed", "pending"]
    assert db.scalar(select(Case).where(Case.type == "vote_dispute", Case.status == "open")) is not None


def test_seed_gives_the_demo_candidate_demand_tasks_and_a_vacancy(db, client):
    seed_all(db, n_per_cell=2)
    demo = db.scalar(select(User).where(User.email == "demo.candidate@fsp-hiring.local"))
    client.cookies.set("fsp_session", create_session(db, demo))
    assert client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"}).status_code == 200
    d = client.get("/api/v1/candidate/demand").json()
    assert d["enough"] and d["companies"] == len(MARKET) and d["category"] == "Backend · Middle"
    assert any(x["tech"] == "Docker" and x["share"] == 1.0 for x in d["top"])  # якорь рынка: у каждой потребности Docker
    tasks = client.get("/api/v1/candidate/tasks").json()
    assert sorted(x["has_reference"] for x in tasks) == [False, True]  # одна с эталоном, одна — на проверку работодателем
    assert all(x["company"]["name"] == DEMO_COMPANY and x["company"]["trust_level"] == "L2" for x in tasks)
    vacancies = client.get("/api/v1/candidate/vacancies").json()
    assert len(vacancies) == 1 and vacancies[0]["specialization"] == "backend"


def test_seed_market_is_older_than_the_demand_delay(db):
    from datetime import timedelta

    from app.common.clock import now
    from app.config.params import PARAMS

    seed_all(db, n_per_cell=2)
    market = db.scalars(select(Need).join(Company, Company.id == Need.company_id).where(Company.name.in_(MARKET))).all()
    assert len(market) == 3 * len(MARKET)
    assert all(n.created_at <= now() - timedelta(days=PARAMS.demand_delay_days) for n in market)


def test_seed_demo_company_is_trusted_and_the_queue_has_several_types(db, client):
    from app.auth.models import Role
    from app.moderation.models import Case

    seed_all(db, n_per_cell=12)  # спор о голосе засева появляется, когда в ячейке хватает кандидатов (как в тесте reviewed-персоны)
    demo = db.scalar(select(Company).where(Company.name == DEMO_COMPANY))
    assert demo.trust_level == "L2" and demo.domain == "fsp-hiring.local" and demo.inn == "7701001005"
    assert demo.legal_name == "ООО «Компания 1005»"
    types = {c.type for c in db.scalars(select(Case).where(Case.status == "open"))}
    assert {"vote_dispute", "employer_complaint"} <= types  # модератор жюри сразу видит разные типы
    mod = db.scalar(select(User).where(User.role == Role.moderator))
    client.cookies.set("fsp_session", create_session(db, mod))
    cases = client.get("/api/v1/moderation/cases").json()
    complaint = next(c for c in cases if c["type"] == "employer_complaint")
    assert {r["label"] for r in complaint["summary"]} >= {"Компания", "Кандидат", "Штраф"}


def test_seed_internship_need_and_a_visible_minor(db, client):
    seed_all(db, n_per_cell=2)
    emp = db.scalar(select(User).where(User.email == "demo.employer@fsp-hiring.local"))
    client.cookies.set("fsp_session", create_session(db, emp))
    intern = db.scalar(select(Need).join(Company, Company.id == Need.company_id)
                       .where(Company.name == DEMO_COMPANY, Need.title == INTERNSHIP_TITLE))
    assert intern.employment == "internship" and intern.grades == ["junior"]
    cards = [c for b in client.get(f"/api/v1/employer/needs/{intern.id}/selection").json()["blocks"] for c in b["items"]]
    assert [c["minor"] for c in cards if c["minor"]] == [True]  # юный кандидат с согласием представителя виден в стажировке
    full = _demo_need(db, "backend")
    refs = {c["ref"] for b in client.get(f"/api/v1/employer/needs/{full.id}/selection").json()["blocks"] for c in b["items"]}
    minor = db.scalar(select(CandidateProfile).where(CandidateProfile.full_name == JUNIOR))
    assert minor.public_ref not in refs  # в полной занятости несовершеннолетнего нет


def test_seed_connects_the_demo_company_to_the_mock_ats(db):
    from app.integrations.models import WebhookEndpoint

    seed_all(db, n_per_cell=2)
    demo = db.scalar(select(Company).where(Company.name == DEMO_COMPANY))
    eps = db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.company_id == demo.id)).all()
    assert len(eps) == 1 and eps[0].active and eps[0].secret.startswith("whsec_")
    assert eps[0].url.endswith(f"/mock/ats/{eps[0].id}/webhook")  # события гида жюри видны на странице мока после worker
