from app.auth.models import User
from app.auth.service import create_session
from app.employers.models import Company
from tests.employers.helpers import NEED, employer

INVITE = {"salary_from": 200000, "salary_to": 300000, "gross_net": "gross", "description": "Платежи",
          "why_you": "Middle подтверждён тестом", "next_step": "Созвон 30 минут", "contact_method": "chat"}


def as_user(client, db, user_id) -> None:
    client.cookies.set("fsp_session", create_session(db, db.get(User, user_id)))


class Scene:
    """Работодатель с компанией и потребностью Backend Middle; кандидаты — через make_candidate."""

    def __init__(self, client, db, trust_level="L0", email="hr@corp.ru", company="Корп"):
        self.client, self.db = client, db
        self.employer = employer(client, db, email)
        client.put("/api/v1/employer/company", json={"name": company, "industry": "финтех"})
        self.company = db.query(Company).filter(Company.name == company).one()
        self.company.trust_level = trust_level
        db.commit()
        self.need_id = client.post("/api/v1/employer/needs", json=NEED).json()["id"]

    def as_employer(self):
        as_user(self.client, self.db, self.employer.id)

    def invite(self, ref, **kw):
        self.as_employer()
        return self.client.post(f"/api/v1/employer/needs/{self.need_id}/invitations", json={**INVITE, "ref": ref, **kw})
