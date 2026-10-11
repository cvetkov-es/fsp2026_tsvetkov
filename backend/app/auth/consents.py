"""Тексты согласий (152-ФЗ) и пресеты видимости профиля.

Версия меняется при любом изменении текста; в журнал пишется версия, данная пользователем.
"""
import hashlib
import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from app.auth.models import Consent
from app.config.params import PARAMS, Params

TEXT_DATE = "2026-10-07"
OPERATOR = "Оператор платформы обратного найма ИТ-специалистов (демонстрационный стенд ЛЦТ 2026)"


class ConsentType(StrEnum):
    processing = "processing"
    distribution = "distribution"
    automated_rules = "automated_rules"
    contact_transfer = "contact_transfer"
    guardian = "guardian"


@dataclass(frozen=True)
class ConsentText:
    version: str
    title: str
    body: str


def _version(title: str, body: str) -> str:
    """Дата редакции + отпечаток текста: любое изменение текста меняет версию."""
    return f"{TEXT_DATE}-{hashlib.sha256((title + body).encode()).hexdigest()[:8]}"


def build_consent_texts(p: Params) -> dict[ConsentType, ConsentText]:
    """Тексты согласий. Числа правил берутся из параметров, а не пишутся в текст вручную."""
    raw: dict[ConsentType, tuple[str, str]] = {
        ConsentType.processing: (
            "Согласие на обработку персональных данных",
            f"{OPERATOR} обрабатывает ваши персональные данные: адрес электронной почты, год рождения, "
            "сведения профиля (специализация, стек, опыт, условия работы), результаты тестов и сведения "
            "о достижениях ФСП (если вы привяжете FSP ID). Цели: регистрация и вход, определение "
            "категории по результатам теста, подбор и связь с работодателями по вашему решению. "
            "Действия: сбор, запись, хранение на серверах в РФ, уточнение, использование, обезличивание, "
            "удаление. Срок: до отзыва согласия или удаления аккаунта. Отозвать согласие можно в "
            "настройках; данные будут удалены в течение 30 дней.",
        ),
        ConsentType.distribution: (
            "Согласие на распространение данных профиля (ст. 10.1 152-ФЗ)",
            "Вы разрешаете показывать зарегистрированным работодателям платформы выбранные поля "
            "профиля в псевдонимном виде (без ФИО и контактов): категорию и грейд, подтверждённые "
            "навыки, стек, опыт, формат работы, город, достижения ФСП. ФИО и контакты не "
            "распространяются: работодатель получает их только после того, как вы примете его "
            "приглашение и дадите отдельное согласие. Условие: без передачи третьим лицам. Набор полей "
            "можно изменить, а согласие отозвать в настройках приватности. После отзыва профиль "
            "скрывается сразу.",
        ),
        ConsentType.automated_rules: (
            "Согласие с автоматическими правилами платформы (ст. 16 152-ФЗ)",
            "Грейд подтверждается автоматически по результатам теста. Порядок в выдаче для работодателя "
            "рассчитывается автоматически по результатам теста, подтверждённым навыкам, достижениям "
            "ФСП и подтверждениям на собеседованиях; оценки ниже ожиданий не опускают профиль ниже "
            "нейтрального уровня и не видны работодателям. Между попытками действуют паузы. Тест на тот "
            f"же грейд можно повторить через {p.cooldown_same_days} дней, тест на грейд выше можно пройти "
            f"через {p.cooldown_up_days} дней после подтверждения. "
            "Окончательное решение о найме всегда принимает человек. Вы можете оспорить решение через "
            "форму обращения. Мы ответим не позднее чем через 30 дней.",
        ),
        ConsentType.contact_transfer: (
            "Согласие на передачу контактов компании",
            "Вы разрешаете передать ваши ФИО и контакты компании, приглашение которой принимаете "
            "(или на вакансию которой откликаетесь), для связи по этому предложению. После передачи "
            "компания становится самостоятельным оператором ваших данных. Вы можете скрыть контакты "
            "на платформе в любой момент. Компания получит уведомление об отзыве согласия.",
        ),
        ConsentType.guardian: (
            "Согласие законного представителя несовершеннолетнего (ст. 9, 10.1 152-ФЗ)",
            "Я, законный представитель (родитель, усыновитель или опекун) несовершеннолетнего пользователя "
            "14–17 лет, даю согласие на обработку его персональных данных на платформе обратного найма и на показ "
            "его профиля работодателям в псевдонимном виде только в потребностях «стажировка» и «каникулярная "
            "работа». ФИО и контакты работодатель получает только после принятия приглашения. Работа возможна "
            f"в пределах ст. 92 ТК РФ: до {p.minor_hours_week[0]} часов в неделю в 14–15 лет и до "
            f"{p.minor_hours_week[1]} часов в 16–17 лет в каникулы; в учебный год не больше "
            f"{int(p.minor_school_factor * 100)}% от этих значений. Согласие можно отозвать, написав нам; профиль "
            "несовершеннолетнего после отзыва снова станет черновиком.",
        ),
    }
    return {t: ConsentText(_version(title, body), title, body) for t, (title, body) in raw.items()}


CONSENT_TEXTS: dict[ConsentType, ConsentText] = build_consent_texts(PARAMS)

PROFILE_FIELDS = (
    "full_name", "contacts", "grade", "skills", "stack", "experience",
    "work_format", "city", "fsp_achievements", "photo",
)

DISTRIBUTION_PRESETS: dict[str, dict[str, str]] = {
    "standard": {
        "full_name": "deny", "contacts": "deny", "photo": "deny",
        "grade": "allow", "skills": "allow", "stack": "allow", "experience": "allow",
        "work_format": "allow", "city": "allow", "fsp_achievements": "allow",
    },
    "minimal": {
        "full_name": "deny", "contacts": "deny", "photo": "deny", "city": "deny",
        "grade": "allow", "skills": "allow", "stack": "allow", "experience": "allow",
        "work_format": "allow", "fsp_achievements": "deny",
    },
}


def record_consent(
    db: Session,
    user_id: uuid.UUID,
    ctype: ConsentType,
    scope: dict | None = None,
    target_company_id: uuid.UUID | None = None,
) -> Consent:
    consent = Consent(
        user_id=user_id,
        type=ctype.value,
        version=CONSENT_TEXTS[ctype].version,
        scope=scope or {},
        target_company_id=target_company_id,
    )
    db.add(consent)
    return consent
