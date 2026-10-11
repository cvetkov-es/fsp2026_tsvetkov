"""Тип обращения «Спор о голосе» (процесс 7, 07b1): карточка для модератора и исполнение решения."""
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assessment.phrases import GRADE_TITLES
from app.candidates.models import CandidateProfile
from app.common.clock import now
from app.config.params import PARAMS
from app.employers.models import Company
from app.hiring.models import PipelineStage, Vote
from app.hiring.votes import LEVEL_TITLES
from app.matching.service import alias
from app.moderation.models import Case
from app.moderation.types import CaseType, register, row

DISPUTE_TITLES = {"no_interview": "собеседования не было", "wrong_stage": "оценка не на этом этапе",
                  "wrong_company": "не та компания"}
STAGE_TITLES = {"first": "Первичное интервью", "technical": "Техническое интервью", "offer": "Оффер", "hired": "Найм",
                "rejected": "Отказ"}


def _day(dt) -> str:
    return dt.strftime("%d.%m.%Y")


def summary(db: Session, case: Case) -> list[dict]:
    v = db.get(Vote, uuid.UUID(case.refs["vote_id"]))
    if v is None:  # удалён вместе с контактом или аккаунтом — обращение закрывается без действия
        return [row("Оценка", "удалена вместе с контактом или аккаунтом. Обращение можно закрыть")]
    stages = db.scalars(select(PipelineStage).where(PipelineStage.contact_id == v.contact_id)
                        .order_by(PipelineStage.at, PipelineStage.id))
    out = [row("Компания", db.get(Company, v.company_id).name), row("Кандидат", alias(db.get(CandidateProfile, v.user_id))),
           row("Оценка", f"«{LEVEL_TITLES[v.value]}» (грейд {GRADE_TITLES.get(v.grade_at_vote, v.grade_at_vote)}, "
                         f"{_day(v.answered_at)})"),
           row("Причина спора", DISPUTE_TITLES.get(v.dispute_reason or "", v.dispute_reason))]
    if v.pending_value:  # компания ответила заново во время спора: «оставить в силе» применит этот ответ
        out.append(row("Ответ во время спора", f"«{LEVEL_TITLES[v.pending_value]}». Применится, если оставить оценку в силе"))
    out.append(row("Этапы", " → ".join(f"{STAGE_TITLES.get(s.stage, s.stage)} {_day(s.at)}" for s in stages) or "нет"))
    return out


def apply(db: Session, case: Case, action: str) -> str:
    v = db.get(Vote, uuid.UUID(case.refs["vote_id"]), with_for_update=True)
    if v is None:
        return "оценка уже удалена"
    if action == "annul":
        v.status, result = "annulled", "оценка аннулирована"
    elif v.pending_value and v.pending_value != v.value:
        # спор отклонён, но компания успела ответить заново — действует её последний ответ, с новым окном спора
        t = now()
        v.value, v.status, v.answered_at = v.pending_value, "pending", t
        v.effective_at = t + timedelta(days=PARAMS.vote_dispute_days)
        result = "спор отклонён, действует последний ответ компании"
    else:
        v.status, result = "upheld", "оценка оставлена в силе"
    v.pending_value = None
    return result


register("vote_dispute", CaseType(
    title="Спор об оценке", actions={"annul": "Аннулировать оценку", "uphold": "Оставить в силе"}, summary=summary,
    apply=apply, notify_kind="vote_dispute_resolved", link="/candidate/reviews"))
