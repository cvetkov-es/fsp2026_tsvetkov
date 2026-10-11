"""Продуктовые параметры — единственный источник чисел.

Числа описаны в документации: архитектура и параметры — docs/architecture.md,
тест — docs/testing.md, подбор — docs/matching.md. Переопределяются через
переменные окружения с префиксом FSP_P_ (например, FSP_P_TEST_MAX=12).
"""
import math

from pydantic_settings import BaseSettings, SettingsConfigDict


class Params(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FSP_P_", frozen=True)

    # --- Тест (2.4, 3.2–3.4, 6.1)
    b_levels: tuple[float, float, float, float, float] = (-2.0, -1.0, 0.0, 1.0, 2.0)
    b_expert_offset: float = 0.3
    rp: float = 0.67  # RP67 для порогов грейдов
    senior_virtual_gap: float = 1.0
    prior_sd: float = 1.0
    p_decide: float = 0.90
    test_min: int = 10
    test_max: int = 15  # ограничивает фазу 1
    express_max: int = 8
    n_min_decide: int = 6  # минимум ответов до любого решения
    attempt_autoclose_hours: int = 72
    item_time_factor: float = 3.0
    extra_time: float = 0.5
    d45_output_share: float = 0.20
    randomesque_k: int = 3
    se_penalty: float = 0.5

    # --- Банк (3.5–3.6, техдизайн 9)
    families_per_cell: int = 2
    families_per_cell_cut: int = 3
    families_per_skill: int = 10
    ai_families: int = 30
    interview_q_per_area: int = 8
    exposure_honest: float = 0.5
    gen_check_instances: int = 50
    gen_unique_share: float = 0.95
    gen_space_min: int = 10_000
    manual_review_share: float = 0.20
    gen_space_sample: int = 2000  # экземпляров для оценки размера пространства
    gen_min_distinct_answers: int = 3  # различных ответов на GEN_CHECK_INSTANCES экземплярах
    # Песочница SQLite (техдизайн 5.2)
    sandbox_max_rows: int = 200
    sandbox_max_steps: int = 500_000
    sandbox_timeout_s: float = 1.0
    sandbox_max_value_bytes: int = 1_000_000

    # --- Навыки (2.5)
    skill_len: int = 6
    ai_verdicts: int = 12
    ai_minutes: int = 10
    ai_defect_share: tuple[float, float] = (0.35, 0.65)
    ai_confident_error_weight: float = 2.0
    ai_pass_accuracy: float = 0.75
    ai_pass_miss: float = 0.25
    sql_input_max_rows: int = 20
    ai_ambiguous: int = 2  # неоднозначных требований в попытке (из AI_VERDICTS)
    ai_sql: int = 4  # SQL-вердиктов в попытке; остальные — Python
    ai_sql_timeout_s: int = 15  # подпроцесс проверки SQL-данных кандидата, включая запуск интерпретатора

    # --- Кулдауны и сроки (2.6, 2.8, 4.x)
    cooldown_same_days: int = 30
    cooldown_up_days: int = 90
    cooldown_skill_days: int = 14
    open_window_days: int = 14
    invite_ttl_days: int = 5
    counter_ttl_days: int = 5
    reinvite_days: int = 30
    invite_remind_hours: int = 24  # напоминание кандидату до истечения приглашения
    group_ttl_days: int = 7
    reminder_days: tuple[int, int] = (7, 21)

    # --- Инициатива и спрос (2.9, 6.4)
    signals_per_quarter: int = 3
    demand_min_employers: int = 5
    demand_delay_days: int = 7
    signal_ttl_days: int = 90  # сколько действует «Хочу к вам»
    demand_window_days: int = 30  # окно потребностей для агрегата спроса
    market_min_n: int = 10  # минимум порогов в категории для медианы ожиданий (k-анонимность)
    activity_days: int = 30

    # --- Задачи работодателей и вакансии (4.6, 4.8)
    task_text_max: int = 2000
    task_answer_max: int = 5000
    task_ttl_days: int = 14  # самый поздний срок задачи от публикации
    vacancy_text_max: int = 4000

    # --- Интеграции (4.7, техдизайн 4.8)
    webhook_max_attempts: int = 5
    webhook_backoff_min: tuple[int, ...] = (1, 5, 30, 120)  # пауза перед каждым из четырёх повторов, минуты
    webhook_timeout_s: float = 5.0
    webhook_batch: int = 50
    webhook_tick_budget_s: float = 20.0  # сколько тик worker тратит на вебхуки, чтобы не задерживать письма
    webhook_endpoints_max: int = 5  # вебхуков на компанию

    # --- Юниорский трек, модерация, помощник (2.10, 4.7, 7)
    adult_age: int = 18
    minor_hours_week: tuple[int, int] = (24, 35)  # ст. 92 ТК РФ: 14–15 и 16–17 лет, каникулы
    minor_school_factor: float = 0.5  # в учебный год — половина
    guardian_token_ttl_days: int = 7
    helper_questions: int = 10
    helper_window_days: int = 30  # окно месячного лимита помощника
    guardian_resend_minutes: int = 5  # новую ссылку представителю — не чаще
    art16_days: int = 30  # срок ответа на возражение по ст. 16 152-ФЗ

    # --- Работодатель (4.1, 4.4, 4.5, 4.7)
    quota_l0: int = 3
    quota_l1: int = 10
    quota_l2: int = 20
    needs_l0: int = 1
    needs_l1: int = 3
    needs_l2: int = 10
    complaint_quota_penalty: int = 1
    complaint_penalty_days: int = 30
    team_min_on_platform: int = 2
    helper_monthly: int = 30

    # --- Собеседования (5)
    vote_w_l1: float = 0.5
    vote_w_l2: float = 1.0
    vote_ttl_months: int = 12
    vote_dispute_days: int = 7
    vote_monthly: int = 30
    votes_unlock: int = 2
    m_boost: float = 0.20
    badge_min: int = 3
    badge_share: float = 2 / 3
    calib_min_n: int = 30

    # --- Ранжирование (6)
    fsp_pts_win: float = 3.0
    fsp_pts_prize: float = 2.0
    fsp_pts_final: float = 1.0
    fsp_pts_online: float = 0.3
    fsp_pts_rank_ms: float = 3.0
    fsp_pts_rank_kms: float = 2.0
    fsp_pts_rank_1: float = 1.0
    fsp_saturation: float = 6.0
    fsp_weight: float = 0.25
    stack_declared: float = 0.5
    stack_unknown: float = 0.5
    nice_bonus: float = 0.05
    fit_w_stack: float = 0.5
    fit_w_r: float = 0.5
    must_missing_penalty: float = 0.9
    hard_salary_gap: float = 0.20
    ndfl: float = 0.13  # пересчёт «до вычета» → «на руки» (упрощение: единая ставка)
    format_compatible: float = 0.7
    window_expired: float = 0.3
    activity_none: float = 0.6
    signal_floor_ok: float = 0.8
    signal_floor_low: float = 0.6
    score_base: float = 0.8

    # --- Техдизайн, раздел 9
    session_ttl_days: int = 7
    verify_ttl_hours: int = 24  # срок ссылки подтверждения почты
    min_age: int = 14  # минимальный возраст регистрации кандидата
    oidc_ttl_min: int = 10  # state входа через FSP ID и «билет» нового аккаунта
    fsp_http_timeout_s: int = 5  # запросы к FSP ID и API достижений
    fsp_snapshots_keep: int = 3  # снимков ФСП на кандидата хранится, кроме того, на котором стоят результаты
    llm_timeout_s: int = 8
    llm_cb_errors: int = 3
    llm_cb_cooldown_min: int = 10
    llm_timeout_pd_s: int = 25  # разбор резюме: пользователь ждёт загрузку, ответ длинный
    llm_timeout_offline_s: int = 60  # лаборатория: решатель банка и судья, никто не ждёт ответа в интерфейсе
    llm_max_input_chars: int = 12_000  # обрезка текста резюме и вакансии перед LLM
    summary_max_chars: int = 400  # перефразированное объяснение
    resume_max_mb: int = 5
    resume_max_pages: int = 5
    resume_min_chars_per_page: int = 50  # меньше — похоже на скан
    pdf_parse_timeout_s: int = 10
    ner_timeout_s: int = 20
    pdf_parse_mem_mb: int = 384  # RLIMIT_AS подпроцесса pdfium (пик на 5 страницах ≈ 75 МБ)
    ner_mem_mb: int = 640  # RLIMIT_AS подпроцесса natasha (пик ≈ 370 МБ виртуальной, 225 МБ RSS)
    grade_hint_years: tuple[float, float] = (2.0, 5.0)  # опыт → подсказка грейда: < 2 J, 2–5 M, ≥ 5 S
    lab_max_pop: int = 3000
    lab_run_stale_min: int = 60  # прогон дольше часа (или без worker в очереди) считается прерванным
    seed_candidates: int = 450

    @property
    def logit_rp(self) -> float:
        return math.log(self.rp / (1 - self.rp))

    @property
    def cut_j(self) -> float:
        return self.b_levels[1] + self.logit_rp

    @property
    def cut_m(self) -> float:
        return self.b_levels[2] + self.logit_rp

    @property
    def cut_s(self) -> float:
        return self.b_levels[3] + self.logit_rp

    @property
    def cut_s_virtual(self) -> float:
        return self.cut_s + self.senior_virtual_gap

    @property
    def skill_cut(self) -> float:
        return self.cut_j

    @property
    def r_max(self) -> float:
        return (1 + self.fsp_weight) * (1 + self.m_boost)


PARAMS = Params()
