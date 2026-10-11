import math

import pytest

from app.config.params import PARAMS, Params
from app.config.settings import Settings


def test_cuts_match_process_v4():
    assert PARAMS.cut_j == pytest.approx(-0.29, abs=0.01)
    assert PARAMS.cut_m == pytest.approx(0.71, abs=0.01)
    assert PARAMS.cut_s == pytest.approx(1.71, abs=0.01)
    assert PARAMS.cut_s_virtual == pytest.approx(PARAMS.cut_s + 1.0)
    assert PARAMS.skill_cut == pytest.approx(PARAMS.cut_j)


def test_key_params_verbatim():
    p = Params()
    assert (p.p_decide, p.test_min, p.test_max, p.express_max, p.n_min_decide) == (0.90, 10, 15, 8, 6)
    assert (p.cooldown_same_days, p.cooldown_up_days, p.cooldown_skill_days) == (30, 90, 14)
    assert p.m_boost == 0.20 and p.r_max == pytest.approx(1.5)
    assert (p.stack_declared, p.must_missing_penalty, p.score_base) == (0.5, 0.9, 0.8)
    assert p.gen_space_min == 10_000 and p.gen_unique_share == 0.95
    assert math.isclose(p.badge_share, 2 / 3)


def test_settings_reads_openrouter_aliases(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k-123")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://example.test/api/v1")
    s = Settings(_env_file=None)
    assert s.llm_api_key.get_secret_value() == "k-123"
    assert s.llm_base_url == "https://example.test/api/v1"
    assert s.llm_profile == "dev"


def test_webhook_backoff_has_a_pause_for_every_retry():
    from app.config.params import PARAMS

    assert len(PARAMS.webhook_backoff_min) == PARAMS.webhook_max_attempts - 1  # лишних значений расписания быть не должно
