from datetime import timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.models import EmailToken, Role, User
from app.common import clock
from app.common.errors import AppError
from app.common.security import hash_token


@pytest.fixture
def committed_token(engine):
    """Пользователь и токен, видимые из разных соединений (без общей тестовой транзакции)."""
    with Session(engine) as s:
        u = User(email="race@x.ru", role=Role.candidate, password_hash="x")
        s.add(u)
        s.flush()
        s.add(EmailToken(user_id=u.id, purpose="verify", token_hash=hash_token("race-token"),
                         expires_at=clock.now() + timedelta(hours=1)))
        s.commit()
        uid = u.id
    yield "race-token"
    with Session(engine) as s:
        s.execute(delete(User).where(User.id == uid))
        s.commit()


def test_verify_token_cannot_be_used_twice_concurrently(engine, committed_token, monkeypatch):
    """Второй запрос с тем же токеном успевает между чтением и записью первого."""
    real_now = clock.now
    state = {"raced": False}

    def racing_now():
        if not state["raced"]:
            state["raced"] = True
            with Session(engine) as other:
                service.verify_email(other, committed_token)
        return real_now()

    monkeypatch.setattr(service, "now", racing_now)
    with Session(engine) as s, pytest.raises(AppError) as exc:
        service.verify_email(s, committed_token)
    assert exc.value.code == "token_invalid"
