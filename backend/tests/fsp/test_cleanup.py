from datetime import timedelta

from sqlalchemy import func, select

from app.common.clock import now
from app.config.params import PARAMS
from app.fsp.models import FspResult, FspSnapshot, OidcPending, OidcState
from app.fsp.sync import sync
from app.mocks.fsp.models import MockFspCode
from app.worker import run_once
from tests.contacts.test_worker_notifications import FakeMailer
from tests.fsp.helpers import SUB, FakeHttp, link


def _count(db, model, *where):
    return db.scalar(select(func.count()).select_from(model).where(*where))


def test_purge_drops_expired_oidc_rows_and_old_snapshots(db, make_candidate):
    t = now()
    old = t - timedelta(minutes=PARAMS.oidc_ttl_min + 1)
    db.add_all([OidcState(state="old", nonce="n", code_verifier="v", purpose="login", created_at=old),
                OidcState(state="fresh", nonce="n", code_verifier="v", purpose="login", created_at=t),
                OidcPending(ticket="old-ticket", subject="s", access_token="tok", created_at=old),
                MockFspCode(code="old-code", subject="s", client_id="c", redirect_uri="r", nonce="n",
                            code_challenge="x", scope="openid", expires_at=old)])
    p = link(db, make_candidate(), SUB["Кузнецова"])  # удачный снимок, на него ссылаются fsp_results
    for _ in range(PARAMS.fsp_snapshots_keep + 2):
        sync(db, FakeHttp(fail=True), p.user_id, "tok")  # ФСП долго недоступен: снимки-ошибки копятся
    db.commit()
    assert run_once(db, FakeMailer())["fsp_purged"] > 0
    assert {s for s in db.scalars(select(OidcState.state))} == {"fresh"}
    assert _count(db, OidcPending) == 0 and _count(db, MockFspCode) == 0
    snaps = _count(db, FspSnapshot, FspSnapshot.user_id == p.user_id)
    assert snaps == PARAMS.fsp_snapshots_keep + 1  # последние N и снимок, на котором стоят результаты
    assert _count(db, FspResult, FspResult.user_id == p.user_id) == 3


def test_worker_runs_purge(db):
    assert run_once(db, FakeMailer())["fsp_purged"] == 0
