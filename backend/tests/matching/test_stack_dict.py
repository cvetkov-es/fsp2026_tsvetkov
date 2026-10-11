from app.matching.stack_dict import SKILL_TECHS, SPEC_CORE, TECHS, expand, normalize, normalize_many


def test_synonyms_including_cyrillic():
    assert normalize("postgres") == "PostgreSQL"
    assert normalize(" Постгрес ") == "PostgreSQL"
    assert normalize("k8s") == "Kubernetes"
    assert normalize("питон") == "Python"
    assert normalize("JS") == "JavaScript"
    assert normalize("неизвестная штука") is None


def test_normalize_many_dedupes_and_reports_unknown():
    known, unknown = normalize_many(["python", "Python", "py", "фреймворк X"])
    assert known == ["Python"] and unknown == ["фреймворк X"]


def test_expand_implies_keeps_strongest_state():
    out = expand({"Django": "declared", "Python": "confirmed", "React": "confirmed"})
    assert out["Python"] == "confirmed" and out["JavaScript"] == "confirmed" and out["Django"] == "declared"


def test_no_synonym_collisions():
    seen: dict[str, str] = {}
    for t in TECHS.values():
        for name in (t.canonical, *t.synonyms):
            key = " ".join(name.strip().lower().split())
            assert seen.setdefault(key, t.canonical) == t.canonical, f"{name}: {seen[key]} и {t.canonical}"


def test_skills_are_narrow():
    assert "React" not in SKILL_TECHS["frontend_basics"] and "Java" not in SKILL_TECHS["backend_basics"]
    assert set(SKILL_TECHS["sql"]) >= {"SQL", "PostgreSQL"} and "Docker" in SKILL_TECHS["devops"]


def test_core_and_skills_reference_known_techs():
    for techs in (*SPEC_CORE.values(), *SKILL_TECHS.values()):
        assert all(t in TECHS for t in techs)
    assert set(SKILL_TECHS) == {"sql", "devops", "frontend_basics", "backend_basics", "ml_basics", "ai"}
