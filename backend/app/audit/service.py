import uuid

from sqlalchemy.orm import Session

from app.audit.models import AuditLog


def audit(
    db: Session,
    actor_id: uuid.UUID | None,
    action: str,
    object_type: str,
    object_id: str,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id, action=action, object_type=object_type,
            object_id=object_id, details=details or {},
        )
    )
