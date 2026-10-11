"""Короткое объяснение для карточки (техдизайн, решение 6): шаблон сразу, перефразирование LLM — по запросу.

Перефразирование принимается, только если в тексте нет чисел и технологий, которых нет во входных фактах.
"""
import hashlib
import json
import re

from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.employers.service import get_need
from app.llm.client import LLM, LLMOut
from app.matching.explain import counterfactual
from app.matching.models import ExplanationCache
from app.matching.scoring import rank
from app.matching.service import _percentiles, card, load_rows, need_facts
from app.matching.stack_dict import find_techs
from app.matching.text_rules import grades_in

SYSTEM = (
    "Ты помогаешь работодателю быстро понять, почему кандидат стоит в подборке. По фактам из JSON напиши одно-два "
    "коротких предложения на русском. Пиши нейтрально, без оценки личности и без указания пола: «кандидат». "
    "Используй только факты из JSON: не добавляй чисел, технологий и навыков, которых там нет. "
    "Не называй баллы, места и проценты, если их нет в фактах."
)
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


class SummaryLLM(LLMOut):
    text: str = Field(min_length=10, max_length=PARAMS.summary_max_chars)


def candidate_card(db: Session, user: User, need_id, ref: str) -> tuple[dict, object, str]:
    """Карточка кандидата в контексте потребности (без фильтров), его user_id и название потребности."""
    n = get_need(db, user, need_id)
    need = need_facts(n)
    rows = load_rows(db, n.specialization, n.company_id)
    t = now()
    ranked = rank((r.facts for r in rows), need, t)
    idx = next((i for i, r in enumerate(ranked) if r.c.ref == ref), None)
    if idx is None:
        raise AppError(404, "candidate_not_found", "Кандидат не найден в подборке")
    row = next(r for r in rows if r.facts.ref == ref)
    c = card(row, ranked[idx], need, _percentiles(rows).get(ref), counterfactual(ranked, idx, need, t))
    return c, row.profile.user_id, n.title


def facts_of(c: dict) -> dict:
    e = c["explanation"]
    return {"грейд": e["lines"][0], "стек": e["lines"][1], "ФСП": e["lines"][2],
            "чего не хватает": e["missing"], "готовность": (c.get("readiness") or {}).get("tooltip")}


def template_text(facts: dict) -> str:
    return f"{facts['грейд']}. {facts['стек']}. {facts['ФСП']}."


def fact_check(text: str, facts: dict) -> bool:
    blob = json.dumps(facts, ensure_ascii=False)
    return (set(_NUM.findall(text)) <= set(_NUM.findall(blob))
            and set(find_techs(text)) <= set(find_techs(blob))
            and set(grades_in(text)) <= set(grades_in(blob))  # «Senior» про подтверждённого Middle — выдумка
            and "[" not in text)


def _cached(db: Session, need_id, candidate_id, digest: str) -> ExplanationCache | None:
    return db.scalar(select(ExplanationCache).where(
        ExplanationCache.need_id == need_id, ExplanationCache.user_id == candidate_id,
        ExplanationCache.facts_hash == digest))


def summary(db: Session, user: User, need_id, ref: str, llm: LLM) -> dict:
    c, candidate_id, _ = candidate_card(db, user, need_id, ref)
    facts = facts_of(c)
    digest = hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    cached = _cached(db, need_id, candidate_id, digest)
    if cached:
        return {"text": cached.llm_text, "source": "llm"}
    tpl = template_text(facts)
    res = llm.json("runtime", SYSTEM, json.dumps(facts, ensure_ascii=False), SummaryLLM)
    if res is None or not fact_check(res[0].text, facts):
        return {"text": tpl, "source": "template"}
    # Параллельное раскрытие той же карточки уже могло сохранить текст — конфликт не ошибка
    db.execute(pg_insert(ExplanationCache).values(
        need_id=need_id, user_id=candidate_id, facts_hash=digest, template_text=tpl, llm_text=res[0].text,
        model=res[1], created_at=now()).on_conflict_do_nothing(index_elements=["need_id", "user_id", "facts_hash"]))
    # Факты сменились (окно поиска, стек) — прежние тексты больше не понадобятся
    db.execute(delete(ExplanationCache).where(ExplanationCache.need_id == need_id,
                                              ExplanationCache.user_id == candidate_id,
                                              ExplanationCache.facts_hash != digest))
    db.commit()
    return {"text": res[0].text, "source": "llm"}
