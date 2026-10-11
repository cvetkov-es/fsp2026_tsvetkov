"""Демо-база: синтетические кандидаты через движок теста, демо-компания и потребности, персоны гида."""
import math
import random
import uuid
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.assessment.bank.areas import AREAS
from app.assessment.bank_sync import EXPERT_VERSION, ensure_thresholds
from app.assessment.engine.levels import Grade, Thresholds
from app.assessment.engine.rules import AttemptConfig, Decision
from app.assessment.engine.selection import FamilyRef
from app.assessment.engine.simulate import simulate_attempt, synthetic_bank
from app.assessment.models import Attempt
from app.assessment.phrases import ru_plural
from app.auth.consents import DISTRIBUTION_PRESETS, ConsentType, record_consent
from app.auth.models import ExternalIdentity, Role, User
from app.candidates.models import CandidateProfile, CandidateStack, SkillResult
from app.common.clock import now
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.contacts.models import Contact
from app.demo.service import ensure_demo_personas
from app.employer_tasks.models import EmployerTask
from app.employers.models import Company, CompanyMember, Need
from app.fsp.sync import FSP_PROVIDER, apply_snapshot
from app.hiring.models import PipelineStage, Vote
from app.hiring.votes import vote_weight
from app.integrations.models import WebhookEndpoint
from app.integrations.webhooks import new_secret
from app.matching.stack_dict import SKILL_TECHS, SPEC_POOL
from app.mocks.fsp.fixtures import ATHLETES, full_name, payload_for
from app.moderation.service import open_case
from app.vacancies.models import Vacancy

DEMO_COMPANY = "Демо-компания"
DEMO_INN, DEMO_LEGAL = "7701001005", "ООО «Компания 1005»"  # юрлицо из мока DaData: уровень L2 без проверки руками
INTERNSHIP_TITLE = "Стажировка в бэкенд"
JUNIOR = "Демо: юный кандидат"  # 15 лет, согласие представителя есть: виден только в стажировке и каникулах
STRONG = "Демо: сильный тест без ФСП"
WEAK = "Демо: слабый тест, призёр ФСП"
# Город, коэффициент к медиане, доля кандидатов. Коэффициенты и медианы «на руки» по грейдам —
# Ориентир по медианным зарплатам — Хабр Карьера, 1-е полугодие 2026
CITIES = (("Москва", 1.23, 0.35), ("Санкт-Петербург", 1.05, 0.15), ("Казань", 0.84, 0.1),
          ("Новосибирск", 0.84, 0.1), ("Екатеринбург", 0.84, 0.1), ("Нижний Новгород", 0.84, 0.1),
          ("Томск", 0.84, 0.1))
MEDIAN_NET = {"junior": 100_000, "middle": 200_000, "senior": 330_000}
EXP = {"junior": (0, 2), "middle": (2, 5), "senior": (5, 10)}
NEEDS = (
    dict(title="Python-разработчик в команду платежей", specialization="backend", grades=["middle", "senior"],
         must=["Python", "PostgreSQL", "Docker"], nice=["Kafka", "Redis"], formats=["remote", "hybrid"],
         salary_from=250_000, salary_to=350_000, gross_net="gross"),
    dict(title="Фронтенд-разработчик в личный кабинет", specialization="frontend", grades=["junior"],
         must=["JavaScript", "React", "TypeScript"], nice=[], formats=["office", "hybrid"],
         salary_from=120_000, salary_to=160_000, gross_net="net"),
    dict(title="Аналитик данных в продуктовую команду", specialization="data", grades=["middle"],
         must=["SQL", "Python"], nice=["Airflow"], formats=["remote"],
         salary_from=220_000, salary_to=300_000, gross_net="gross"),
)

INTERNSHIP = dict(title=INTERNSHIP_TITLE, specialization="backend", grades=["junior"], must=["Python"], nice=["SQL"],
                  formats=["remote"], salary_from=40_000, salary_to=60_000, gross_net="net", employment="internship")


def _salary(rng: random.Random, grade: str, coef: float) -> int | None:
    if rng.random() < 0.25:
        return None
    return int(round(MEDIAN_NET[grade] * coef * math.exp(rng.gauss(0, 0.25)) / 5000) * 5000)


def _fsp_summary(rng: random.Random) -> str:
    k, n = rng.randint(1, 3), rng.randint(1, 5)
    return (f"ФСП: призёр {k} {ru_plural(k, 'старта', 'стартов', 'стартов')}, участие в {n} "
            f"{ru_plural(n, 'онлайн-отборе', 'онлайн-отборах', 'онлайн-отборах')}")


def _candidate(db: Session, rng: random.Random, i: int, spec: str, grade: str, t: Thresholds,
               bank: list[FamilyRef], *, preset: str | None = None, with_skill: bool = True) -> CandidateProfile:
    u = User(email=f"seed-{i:04d}@synthetic.fsp-hiring.local", role=Role.candidate, email_verified_at=now())
    db.add(u)
    db.flush()
    preset = preset or ("minimal" if rng.random() < 0.15 else "standard")
    record_consent(db, u.id, ConsentType.processing)
    record_consent(db, u.id, ConsentType.distribution,
                   scope={"preset": preset, "fields": DISTRIBUTION_PRESETS[preset]})
    cfg = AttemptConfig(Grade(grade), t, PARAMS.test_max)
    ev = simulate_attempt(t.cut(Grade(grade)) + rng.gauss(0.4, 0.6), cfg, bank, AREAS[spec],
                          rng_seed=rng.randrange(10**9))
    decision = ev.decision or Decision.not_confirmed
    decided = now() - timedelta(days=rng.randint(1, 60))
    a = Attempt(user_id=u.id, kind="grade", specialization=spec, target_grade=grade, item_cap=PARAMS.test_max,
                thresholds_version=t.version, status="completed", decision=decision.value,
                decided_at_n=ev.decided_at, border=ev.border, confident=ev.confident, theta=ev.theta, se=ev.se,
                p_confirm=ev.p_confirm, s=ev.s, synthetic=True, started_at=decided, last_activity_at=decided,
                decided_at=decided, finished_at=decided)
    db.add(a)
    db.flush()
    city, coef, _ = rng.choices(CITIES, weights=[c[2] for c in CITIES])[0]
    has_fsp = rng.random() < 0.2
    window = timedelta(days=rng.randint(1, 14)) if rng.random() < 0.7 else -timedelta(days=rng.randint(1, 30))
    idle = rng.randint(0, 29) if rng.random() < 0.75 else rng.randint(31, 120)
    p = CandidateProfile(
        user_id=u.id, specialization=spec, claimed_grade=grade, grade_status=decision.value,
        confirmed_grade=grade if decision == Decision.confirmed else None, status_attempt_id=a.id,
        theta=ev.theta, se=ev.se, s_cache=ev.s, synthetic=True,
        full_name=f"Синтетический кандидат {i}", contacts={"email": u.email},
        experience_years=round(rng.uniform(*EXP[grade]), 1),
        formats=rng.sample(["office", "hybrid", "remote"], rng.randint(1, 2)), city=city,
        salary_threshold=_salary(rng, grade, coef), salary_gross_net="net",
        open_until=now() + window, last_activity_at=now() - timedelta(days=idle),
        fsp_status="LINKED" if has_fsp else "NOT_LINKED",
        fsp_f=round(rng.uniform(0.3, 0.9), 2) if has_fsp else 0.0,
        fsp_summary=_fsp_summary(rng) if has_fsp else None)
    db.add(p)
    techs = rng.sample(SPEC_POOL[spec], rng.randint(4, 8))
    db.add_all(CandidateStack(user_id=u.id, tech=x) for x in techs)
    if with_skill and rng.random() < 0.4:
        skills = [s for s, ts in SKILL_TECHS.items() if set(ts) & set(techs)]
        if skills:
            db.add(SkillResult(user_id=u.id, skill_code=rng.choice(skills), passed=True))
    return p


def _personas(db: Session, rng: random.Random, i: int, t: Thresholds) -> int:
    """Пара для гида жюри: контрольный случай 1 процесса (6.4) на живых данных."""
    bank = synthetic_bank(AREAS["backend"])
    for name, s, f in ((STRONG, 0.79, 0.0), (WEAK, 0.51, 0.74)):  # числа контрольного случая 1 (процесс 6.4)
        i += 1
        p = _candidate(db, rng, i, "backend", "middle", t, bank, preset="standard", with_skill=False)
        a = db.get(Attempt, p.status_attempt_id)
        a.decision, a.s = Decision.confirmed.value, s
        p.full_name, p.s_cache, p.grade_status, p.confirmed_grade = name, s, "confirmed", "middle"
        p.fsp_f, p.fsp_status = f, ("LINKED" if f else "NOT_LINKED")
        p.fsp_summary = "ФСП: призёр 2 стартов, участие в 5 онлайн-отборах" if f else None
        p.formats, p.salary_threshold, p.salary_gross_net = ["remote"], 220_000, "net"
        p.open_until, p.last_activity_at = now() + timedelta(days=10), now()
        db.flush()
        db.execute(delete(CandidateStack).where(CandidateStack.user_id == p.user_id))
        db.add_all(CandidateStack(user_id=p.user_id, tech=x) for x in ("Python", "PostgreSQL", "Docker"))
    return i


# Спортсмены с привязанным FSP ID (исследование 04, §2: демо-персоны). Вера и Иван остаются вне платформы:
# Вера даёт «2 из 3 участников на платформе», Иван — вход через FSP ID в гиде жюри
FSP_ATHLETES = ((ATHLETES[0], "backend", "senior"), (ATHLETES[1], "frontend", "middle"), (ATHLETES[3], "backend", "middle"),
                (ATHLETES[4], "data", "middle"), (ATHLETES[5], "backend", "junior"), (ATHLETES[6], "data", "junior"))


def _fsp_athletes(db: Session, rng: random.Random, i: int, t: Thresholds) -> int:
    """Данные ФСП — из тех же фикстур, что отдаёт мок: засеву не нужна сеть."""
    # issuer берётся из PUBLIC_BASE_URL: при смене адреса стенда базу засевают заново (make seed на пустой БД)
    issuer = get_settings().fsp_issuer
    for athlete, spec, grade in FSP_ATHLETES:
        i += 1
        p = _candidate(db, rng, i, spec, grade, t, synthetic_bank(AREAS[spec]), preset="standard")
        p.full_name = full_name(athlete)
        db.add(ExternalIdentity(user_id=p.user_id, provider=FSP_PROVIDER, issuer=issuer, subject=athlete["sub"]))
        db.flush()
        apply_snapshot(db, p.user_id, payload_for(athlete["sub"]))
    return i


# Другие компании платформы: их голоса о кандидатах засева показывают бейдж и прибавку m в подборке (процесс 5)
VOTERS = (("Северный код", "L1"), ("Байкал Софт", "L2"))
# Отрасль, описание и названия потребностей компаний засева: кандидат видит их в приглашениях и списке компаний
VOTER_PROFILES = {
    "Северный код": ("заказная разработка",
                     "Делаем софт для банков и страховых на заказ. Офисы в Петрозаводске и Мурманске, "
                     "половина команды работает из дома.",
                     {"backend": "Python-разработчик на банковский проект",
                      "frontend": "Junior фронтенд-разработчик на проект для страховой",
                      "data": "Аналитик данных на проект для банка"}),
    "Байкал Софт": ("розничная торговля",
                    "Продуктовая компания из Иркутска. Пишем кассовый софт и учёт для магазинов.",
                    {"backend": "Бэкенд-разработчик в кассовый сервис",
                     "frontend": "Фронтенд-разработчик в веб-кассу",
                     "data": "Аналитик продаж"}),
}
# Ответы трёх компаний (демо L2, «Северный код» L1, «Байкал Софт» L2 — веса 1, 0.5, 1) о Middle каждой специализации:
# три положительных — бейдж и m ≈ 1.11; одна «ниже» — прибавка меньше, бейджа нет; три «ниже» — m = 1, наружу ничего
VOTE_PATTERNS = (("meets", "above", "meets"), ("above", "meets", "above"), ("meets", "meets", "meets"),
                 ("meets", "below", "meets"), ("below", "below", "below"))
FRESH_ON_BOARD = 2  # принятых приглашений демо-компании без этапа — их жюри ведёт по доске само
REVIEWED = "demo.reviewed@fsp-hiring.local"  # демо-кандидат с оценками: «Мои оценки» и спор без прохождения пути


def _accepted(db: Session, company: Company, need: Need, p: CandidateProfile, t, texts: dict | None = None) -> Contact:
    """texts — description, why_you и next_step приглашения, которое кандидат засева видит в «Приглашениях»."""
    c = Contact(need_id=need.id, company_id=company.id, user_id=p.user_id, status="accepted",
                salary_from=need.salary_from, salary_to=need.salary_to, gross_net=need.gross_net,
                expires_at=t + timedelta(days=PARAMS.invite_ttl_days),
                contacts_revealed_at=t, created_at=t, **({"description": need.title} | (texts or {})))
    db.add(c)
    record_consent(db, p.user_id, ConsentType.contact_transfer, target_company_id=company.id)
    db.flush()
    return c


def _vote(db: Session, c: Contact, co: Company, p: CandidateProfile, value: str, at, status: str = "pending") -> Vote:
    db.add(PipelineStage(contact_id=c.id, stage="technical", level=value, at=at))
    v = Vote(contact_id=c.id, company_id=co.id, user_id=p.user_id, value=value, weight=vote_weight(co.trust_level),
             trust_at_vote=co.trust_level, spec_at_vote=p.specialization, grade_at_vote="middle", status=status,
             created_at=at, updated_at=at, answered_at=at, effective_at=at + timedelta(days=PARAMS.vote_dispute_days))
    db.add(v)
    db.flush()
    return v


# Приглашения demo.reviewed: стек кандидата засева случайный, поэтому тексты не называют его технологий
REVIEWED_INVITES = {
    "Северный код": dict(
        description="Проект для банка: переносим старые интеграции на новые сервисы. В команде пять человек, проект на год.",
        why_you="Middle по бэкенду подтверждён тестом. На проекте много SQL и чужого кода, нужен человек, "
                "который в этом не потеряется.",
        next_step="Созвон с тимлидом на 40 минут, потом небольшое тестовое"),
    DEMO_COMPANY: dict(
        description="Команда платежей, шесть человек. Сервисы на Python и PostgreSQL, релизим раз в неделю.",
        why_you="Ищем бэкендера на сервис возвратов. Тест подтвердил у вас middle, задачи там как раз такого уровня.",
        next_step="Техническое интервью с тимлидом, около часа"),
    "Байкал Софт": dict(
        description="Кассовый софт для розничных сетей. Нужен человек в команду, которая синхронизирует кассы с учётом.",
        why_you="Понравился ваш профиль. Хотим познакомиться и рассказать, чем занимаемся.",
        next_step="Звонок с HR, 20 минут"),
}


def _reviewed_persona(db: Session, p: CandidateProfile, companies: list[Company], needs: dict) -> None:
    """Действующая оценка, оценка в окне спора и оспоренная с открытым обращением — жюри видит «Мои оценки»
    и очередь модерации сразу, не проходя весь путь от теста до технического интервью."""
    u = db.get(User, p.user_id)
    u.email, u.is_demo, p.full_name = REVIEWED, True, "Демо: кандидат с оценками"
    demo, north, baikal = companies

    def accepted(co: Company, at) -> Contact:
        return _accepted(db, co, needs[(co.id, "backend")], p, at, REVIEWED_INVITES[co.name])

    t = now()
    _vote(db, accepted(north, t - timedelta(days=40)), north, p, "meets", t - timedelta(days=35))
    _vote(db, accepted(demo, t - timedelta(days=4)), demo, p, "below", t - timedelta(days=2))
    v = _vote(db, accepted(baikal, t - timedelta(days=5)), baikal, p, "below", t - timedelta(days=3), status="disputed")
    v.dispute_reason, v.dispute_comment = "wrong_stage", "Оценку поставили после звонка с HR. Технического интервью не было"
    open_case(db, "vote_dispute", {"vote_id": str(v.id), "contact_id": str(v.contact_id)}, p.user_id, v.dispute_comment)


def _hiring_history(db: Session, demo: Company) -> int:
    """Принятые приглашения, техническое интервью и голоса 35 дней назад: голоса уже действуют (VOTE_DISPUTE прошёл)
    и не занимают месячный лимит (VOTE_MONTHLY — за 30 дней). Карточки демо-компании вчера переведены в «Оффер»:
    засев не вызывает напоминаний REMINDER_DAYS, а жюри может довести их до финала."""
    t = now() - timedelta(days=40)
    companies = [demo]
    for name, level in VOTERS:
        industry, description, titles = VOTER_PROFILES[name]
        co = Company(name=name, description=description, industry=industry, trust_level=level)
        db.add(co)
        db.flush()
        db.add_all(Need(company_id=co.id, contact_method="chat", city=None, **(n | {"title": titles[n["specialization"]]}))
                   for n in NEEDS)
        companies.append(co)
    db.flush()
    needs = {(n.company_id, n.specialization): n
             for n in db.scalars(select(Need).where(Need.company_id.in_([co.id for co in companies]), Need.employment == "full"))}
    n_votes = 0
    for spec in ("backend", "frontend", "data"):
        ps = list(db.scalars(select(CandidateProfile).join(User, User.id == CandidateProfile.user_id).where(
            User.email.like("seed-%"), CandidateProfile.specialization == spec,
            CandidateProfile.grade_status == "confirmed", CandidateProfile.confirmed_grade == "middle")
            .order_by(CandidateProfile.public_ref).limit(len(VOTE_PATTERNS) + FRESH_ON_BOARD + 1)))
        for p, pattern in zip(ps, VOTE_PATTERNS, strict=False):
            for co, value in zip(companies, pattern, strict=True):
                c = _accepted(db, co, needs[(co.id, spec)], p, t)
                _vote(db, c, co, p, value, t + timedelta(days=5))
                if co is demo:
                    db.add(PipelineStage(contact_id=c.id, stage="offer", at=now() - timedelta(days=1)))
                n_votes += 1
        rest = ps[len(VOTE_PATTERNS):]
        for p in rest[:FRESH_ON_BOARD]:
            _accepted(db, demo, needs[(demo.id, spec)], p, now() - timedelta(days=2))
        if spec == "backend" and len(rest) > FRESH_ON_BOARD:
            _reviewed_persona(db, rest[FRESH_ON_BOARD], companies, needs)
    db.commit()
    return n_votes


MARKET = tuple(f"Рынок {k}" for k in range(1, 7))  # ≥ DEMAND_MIN_EMPLOYERS: у демо-кандидата сразу виден спрос
# Отрасль и описание компаний рынка (по порядку MARKET): кандидат видит их в списке компаний
MARKET_PROFILES = (
    ("ритейл", "Сеть продуктовых магазинов. Своя разработка: склад, доставка, приложение для покупателей."),
    ("логистика", "Возим грузы по всей России. Пишем систему для диспетчеров и приложение для водителей."),
    ("медицина", "Сеть клиник в Поволжье, 40 филиалов. Делаем онлайн-запись и электронную медкарту."),
    ("телеком", "Региональный оператор связи. Биллинг, личный кабинет абонента и внутренняя аналитика."),
    ("образование", "Учим подростков программировать. Платформу для уроков и домашних заданий пишем сами."),
    ("недвижимость", "Помогаем снять квартиру надолго: объявления, договор онлайн, платежи за аренду."),
)
MARKET_TITLES = {"backend": "Бэкенд-разработчик", "frontend": "Фронтенд-разработчик", "data": "Аналитик данных"}
# Технология, которую просят все: её подтверждает навык, поэтому в блоке спроса есть призыв «подтвердите навык»
ANCHOR = {"backend": "Docker", "frontend": "CSS", "data": "SQL"}
ALL_GRADES = ["junior", "middle", "senior"]


def _market(db: Session, rng_seed: int) -> int:
    """Шесть компаний L1 с потребностями по каждой специализации, старше DEMAND_DELAY: спрос считается сразу.
    Отдельный поток случайных чисел, чтобы засев кандидатов остался прежним."""
    rng = random.Random(rng_seed + 1)
    created = now() - timedelta(days=PARAMS.demand_delay_days + 3)
    for name, (industry, description) in zip(MARKET, MARKET_PROFILES, strict=True):
        co = Company(name=name, description=description, industry=industry, trust_level="L1")
        db.add(co)
        db.flush()
        for spec in ("backend", "frontend", "data"):
            pool = [x for x in SPEC_POOL[spec] if x != ANCHOR[spec]]
            picks = rng.sample(pool, 4)  # две первые — кандидаты в must, две последние — в nice
            must, nice = [ANCHOR[spec], *picks[:rng.randint(1, 2)]], picks[2:2 + rng.randint(1, 2)]
            db.add(Need(company_id=co.id, title=MARKET_TITLES[spec], specialization=spec,
                        grades=list(ALL_GRADES), must=must, nice=nice, formats=["remote", "hybrid"],
                        salary_from=150_000, salary_to=300_000, gross_net="net", contact_method="chat",
                        created_at=created))
    db.flush()
    return len(MARKET)


TASKS = (
    dict(title="Посчитать p95 по логу запросов",
         text=("Время ответа 20 запросов в миллисекундах: 120, 95, 310, 88, 140, 205, 99, 450, 130, 110, 87, 92, 160, 175, "
               "101, 98, 133, 125, 400, 90. Посчитайте p95 методом ближайшего ранга и введите число."),
         reference_answer="400", answer_kind="number"),
    dict(title="Спроектировать идемпотентный POST /payments",
         text=("Клиент может отправить запрос на создание платежа дважды, например после таймаута. Опишите, как сделать, "
               "чтобы второй платёж не создался: что вы храните, какие коды ответа возвращаете и что будет, "
               "если два одинаковых запроса придут одновременно."),
         reference_answer=None, answer_kind=None),
)


def _initiative(db: Session, demo: Company, employer: User) -> None:
    """Задачи демо-компании (одна проверяется по эталону, другая — работодателем) и вакансия по бэкенд-потребности."""
    deadline = now() + timedelta(days=10)
    db.add_all(EmployerTask(company_id=demo.id, author_user_id=employer.id, specialization="backend", deadline=deadline, **x)
               for x in TASKS)
    need = db.scalar(select(Need).where(Need.company_id == demo.id, Need.specialization == "backend", Need.employment == "full"))
    db.add(Vacancy(company_id=demo.id, need_id=need.id, title=need.title, specialization=need.specialization,
                   description="Отвечаем за деньги клиентов: приём оплат, возвраты, выплаты партнёрам.\n"
                               "В команде шесть человек. Сервисы на Python и PostgreSQL, всё в Docker, очереди на Kafka.\n"
                               "Релизим раз в неделю. Ближайшая большая задача: оплата через СБП.",
                   grades=list(need.grades), salary_from=need.salary_from, salary_to=need.salary_to,
                   gross_net=need.gross_net, city=need.city, formats=list(need.formats)))


def _minor(db: Session, rng: random.Random, i: int, t: Thresholds) -> int:
    """Юный кандидат (15 лет) с согласием представителя: сразу виден в «Стажировке в бэкенд», в полной занятости — нет."""
    i += 1
    p = _candidate(db, rng, i, "backend", "junior", t, synthetic_bank(AREAS["backend"]), preset="standard", with_skill=False)
    a = db.get(Attempt, p.status_attempt_id)
    a.decision, a.s = Decision.confirmed.value, 0.7
    p.full_name, p.s_cache, p.grade_status, p.confirmed_grade = JUNIOR, 0.7, "confirmed", "junior"
    p.formats, p.salary_threshold, p.salary_gross_net = ["remote"], 40_000, "net"
    p.open_until, p.last_activity_at = now() + timedelta(days=10), now()
    p.guardian_email, p.guardian_consent_at = "demo.guardian@fsp-hiring.local", now()
    u = db.get(User, p.user_id)
    today = now().date()
    u.birth_date, u.birth_year = date(today.year - 15, 1, 1), today.year - 15
    record_consent(db, u.id, ConsentType.guardian, scope={"guardian_email": p.guardian_email, "guardian_name": "Демо Представитель"})
    db.flush()
    db.execute(delete(CandidateStack).where(CandidateStack.user_id == p.user_id))
    db.add_all(CandidateStack(user_id=p.user_id, tech=x) for x in ("Python", "SQL"))
    return i


def _complaint(db: Session, company: Company) -> None:
    """Жалоба «спам» на компанию засева: штраф к квоте действует, обращение ждёт модератора — очередь с разными типами."""
    p = db.scalar(select(CandidateProfile).join(User, User.id == CandidateProfile.user_id).where(
        User.email.like("seed-%"), CandidateProfile.specialization == "backend", CandidateProfile.grade_status == "confirmed",
        CandidateProfile.confirmed_grade == "junior").order_by(CandidateProfile.public_ref).limit(1))
    need = db.scalar(select(Need).where(Need.company_id == company.id, Need.specialization == "backend"))
    t = now() - timedelta(days=2)
    c = Contact(need_id=need.id, company_id=company.id, user_id=p.user_id, status="declined", salary_from=need.salary_from,
                salary_to=need.salary_to, gross_net=need.gross_net, description=need.title, why_you="Ваш опыт нам интересен",
                next_step="Созвон с HR", expires_at=t + timedelta(days=PARAMS.invite_ttl_days), decline_reason="spam",
                decline_comment="Зовут на middle и senior, а у меня junior. Похоже на массовую рассылку", created_at=t)
    db.add(c)
    db.flush()
    company.quota_penalty_slots, company.quota_penalty_until = PARAMS.complaint_quota_penalty, now() + timedelta(days=PARAMS.complaint_penalty_days - 2)
    open_case(db, "employer_complaint", {"contact_id": str(c.id), "company_id": str(company.id),
                                         "penalty_until": company.quota_penalty_until.isoformat()}, p.user_id, c.decline_comment)


def _mock_ats(db: Session, demo: Company) -> None:
    """Демо-компания подключена к встроенному моку ATS: события гида жюри видны на его странице после `make worker`."""
    if not get_settings().mocks_on:
        return
    eid = uuid.uuid4()
    db.add(WebhookEndpoint(id=eid, company_id=demo.id, url=f"{get_settings().public_base_url.rstrip('/')}/mock/ats/{eid}/webhook",
                           secret=new_secret(), active=True))


def seed_all(db: Session, n_per_cell: int = PARAMS.seed_candidates // 9, rng_seed: int = 2026) -> dict:
    if db.scalar(select(Company.id).where(Company.name == DEMO_COMPANY)):
        return {"skipped": True}
    ensure_thresholds(db)
    rng = random.Random(rng_seed)
    t = Thresholds.from_params(PARAMS, EXPERT_VERSION)
    i = 0
    for spec in ("backend", "frontend", "data"):
        bank = synthetic_bank(AREAS[spec])
        for grade in ("junior", "middle", "senior"):
            for _ in range(n_per_cell):
                i += 1
                _candidate(db, rng, i, spec, grade, t, bank)
    i = _personas(db, rng, i, t)
    i = _fsp_athletes(db, rng, i, t)
    i = _minor(db, rng, i, t)
    emp = next(u for u in ensure_demo_personas(db) if u.role == Role.employer)
    c = Company(name=DEMO_COMPANY, description="Платёжный сервис для малого бизнеса. Приём оплат, переводы и личный кабинет "
                                               "для клиентов.",
                industry="финтех", trust_level="L2", domain="fsp-hiring.local", inn=DEMO_INN, legal_name=DEMO_LEGAL)
    db.add(c)
    db.flush()
    db.add(CompanyMember(company_id=c.id, user_id=emp.id))
    db.add_all(Need(company_id=c.id, contact_method="chat", city=None, **n) for n in [*NEEDS, INTERNSHIP])
    db.flush()
    _initiative(db, c, emp)
    _market(db, rng_seed)
    _mock_ats(db, c)
    db.commit()
    votes = _hiring_history(db, c)
    _complaint(db, db.scalar(select(Company).where(Company.name == VOTERS[0][0])))
    db.commit()
    return {"candidates": i, "needs": len(NEEDS) + 1, "votes": votes}
