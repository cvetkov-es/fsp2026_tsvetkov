"""Импорт всех моделей, чтобы Base.metadata знала все таблицы.

Каждый новый модуль с моделями добавляет сюда свою строку импорта.
"""
from app.assessment import models as assessment_models  # noqa: F401
from app.audit import models as audit_models  # noqa: F401
from app.auth import models as auth_models  # noqa: F401
from app.candidates import models as candidate_models  # noqa: F401
from app.contacts import models as contact_models  # noqa: F401
from app.employer_tasks import models as employer_task_models  # noqa: F401
from app.employers import models as employer_models  # noqa: F401
from app.fsp import models as fsp_models  # noqa: F401
from app.groups import models as group_models  # noqa: F401
from app.hiring import models as hiring_models  # noqa: F401
from app.initiative import models as initiative_models  # noqa: F401
from app.integrations import models as integration_models  # noqa: F401
from app.lab import models as lab_models  # noqa: F401
from app.matching import models as matching_models  # noqa: F401
from app.mocks.ats import models as mock_ats_models  # noqa: F401
from app.mocks.fsp import models as mock_fsp_models  # noqa: F401
from app.moderation import models as moderation_models  # noqa: F401
from app.notifications import models as notification_models  # noqa: F401
from app.vacancies import models as vacancy_models  # noqa: F401
