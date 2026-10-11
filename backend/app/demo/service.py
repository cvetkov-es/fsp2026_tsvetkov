from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import Role, User
from app.common.clock import now

BASE_PERSONAS = (
    ("demo.candidate@fsp-hiring.local", Role.candidate, 2001),
    ("demo.employer@fsp-hiring.local", Role.employer, None),
    ("demo.moderator@fsp-hiring.local", Role.moderator, None),  # очередь споров о голосах (план 07b1)
)


def ensure_demo_personas(db: Session) -> list[User]:
    users = []
    for email, role, birth_year in BASE_PERSONAS:
        u = db.scalar(select(User).where(User.email == email))
        if u is None:
            u = User(email=email, role=role, birth_year=birth_year, is_demo=True,
                     email_verified_at=now())
            db.add(u)
        users.append(u)
    db.commit()
    return users
