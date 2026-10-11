"""Процесс без ключа LLM (спецификация 5.6): PDF → словарь, вакансия → правила, объяснения → шаблоны."""
from app.auth.consents import DISTRIBUTION_PRESETS, ConsentType, record_consent
from app.candidates.models import CandidateProfile
from tests.candidates.test_profile import login
from tests.employers.helpers import employer
from tests.employers.test_need_parse import VACANCY
from tests.llm.samples import SAMPLES
from tests.pdf_factory import make_pdf


def test_guide_works_without_llm(client, db):
    u = login(client, db)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    draft = client.post("/api/v1/candidate/profile/resume",
                        files={"file": ("cv.pdf", make_pdf(SAMPLES["hh"]), "application/pdf")}).json()
    assert draft["source"] == "rules"
    client.put("/api/v1/candidate/profile/stack", json={"techs": draft["stack"]})
    client.put("/api/v1/candidate/profile/details", json={"formats": draft["formats"], "city": draft["city"],
                                                          "experience_years": draft["experience_years"]})
    record_consent(db, u.id, ConsentType.distribution,
                   scope={"preset": "standard", "fields": DISTRIBUTION_PRESETS["standard"]})
    p = db.get(CandidateProfile, u.id)
    p.grade_status, p.confirmed_grade, p.s_cache, p.theta, p.se = "confirmed", "middle", 0.7, 1.0, 0.4
    db.commit()
    ref = p.public_ref

    employer(client, db)
    client.put("/api/v1/employer/company", json={"name": "Корп"})
    need = client.post("/api/v1/employer/needs/parse", json={"text": VACANCY}).json()
    assert need["source"] == "rules" and not need["missing"]
    body = {k: need[k] for k in ("title", "specialization", "grades", "must", "nice", "formats", "city",
                                 "salary_from", "salary_to", "gross_net")}
    nid = client.post("/api/v1/employer/needs", json={**body, "contact_method": "chat"}).json()["id"]
    refs = [i["ref"] for b in client.get(f"/api/v1/employer/needs/{nid}/selection").json()["blocks"] for i in b["items"]]
    assert ref in refs
    s = client.get(f"/api/v1/employer/needs/{nid}/candidates/{ref}/summary").json()
    assert s["source"] == "template"
    assert client.get(f"/api/v1/employer/needs/{nid}/candidates/{ref}/pdf").status_code == 200
