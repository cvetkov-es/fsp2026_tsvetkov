import pytest
from sqlalchemy import func, select

from app.auth.models import ExternalIdentity, User
from app.common.errors import AppError
from app.fsp import accounts
from app.fsp.models import FspResult
from app.fsp.oidc import Identity
from app.fsp.sync import sync, unlink
from app.matching.scoring import fsp_f
from app.matching.service import load_rows
from app.mocks.fsp.fixtures import payload_for
from tests.fsp.helpers import SUB, FakeHttp, link


def facts_of(db, profile):
    return next(r for r in load_rows(db) if r.profile.user_id == profile.user_id).facts


def test_apply_snapshot_sets_status_f_and_summary(db, make_candidate):
    p = link(db, make_candidate(), SUB["Кузнецова"])
    assert p.fsp_status == "LINKED" and p.fsp_f == pytest.approx(fsp_f(4.3))
    assert p.fsp_summary.startswith("ФСП: призёр 2 стартов")
    assert db.scalar(select(func.count()).select_from(FspResult).where(FspResult.user_id == p.user_id)) == 3
    assert facts_of(db, p).fsp_visible


def test_linked_without_results(db, make_candidate):
    p = link(db, make_candidate(), SUB["Лебедев"])
    assert (p.fsp_status, p.fsp_f, p.fsp_summary) == ("LINKED_EMPTY", 0.0, None)


def test_sync_calls_api_with_bearer(db, make_candidate):
    p = make_candidate()
    http = FakeHttp(payload_for(SUB["Демидов"]))
    assert sync(db, http, p.user_id, "tok") == "LINKED"
    url, headers = http.calls[0]
    assert url.endswith("/athletes/me/achievements") and headers["Authorization"] == "Bearer tok"


def test_failed_sync_keeps_last_snapshot_as_stale(db, make_candidate):
    p = link(db, make_candidate(), SUB["Кузнецова"])
    before = p.fsp_f
    assert sync(db, FakeHttp(fail=True), p.user_id, "tok") == "SYNC_STALE"
    db.commit()
    assert p.fsp_f == before and p.fsp_summary
    assert db.scalar(select(func.count()).select_from(FspResult).where(FspResult.user_id == p.user_id)) == 3
    assert facts_of(db, p).fsp_visible  # последний снимок с датой продолжает работать


def test_unlink_deletes_data_and_hides_from_employers(db, make_candidate):
    p = link(db, make_candidate(), SUB["Кузнецова"])
    unlink(db, db.get(User, p.user_id))
    assert (p.fsp_status, p.fsp_f, p.fsp_summary) == ("CONSENT_REVOKED", 0.0, None)
    assert db.scalar(select(FspResult).where(FspResult.user_id == p.user_id)) is None
    assert db.scalar(select(ExternalIdentity).where(ExternalIdentity.user_id == p.user_id)) is None
    assert not facts_of(db, p).fsp_visible


@pytest.mark.parametrize("payload", [
    {"results": [{"place": 1}]},  # нет обязательных полей
    {"results": "не список"},
    {"results": [{"competition_id": "c", "competition_title": "t", "discipline": "algo", "stage_type": "FINAL",
                  "date": "2025-01-01", "team": "строка вместо объекта"}]},
    {"ranks": [{"rank": "KMS"}]},
])
def test_malformed_payload_is_stale_not_crash(db, make_candidate, payload):
    p = link(db, make_candidate(), SUB["Кузнецова"])
    before = p.fsp_f
    assert sync(db, FakeHttp(payload), p.user_id, "tok") == "SYNC_STALE"
    assert p.fsp_f == before
    assert db.scalar(select(func.count()).select_from(FspResult).where(FspResult.user_id == p.user_id)) == 3


def test_concurrent_link_of_same_fsp_id_maps_to_conflict(db, make_candidate, monkeypatch):
    a, b = make_candidate(), make_candidate()
    link(db, a, SUB["Орлов"])
    monkeypatch.setattr(accounts, "identity_by_subject", lambda db, subject: None)  # гонка: проверка уже прошла
    with pytest.raises(AppError) as e:
        accounts.link(db, db.get(User, b.user_id), Identity(SUB["Орлов"], None, True, None, "tok"))
    assert e.value.code == "fsp_already_linked"
    assert db.scalar(select(func.count()).select_from(ExternalIdentity)) == 1  # сессия жива, строка одна
