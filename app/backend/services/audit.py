from __future__ import annotations

import json

from sqlalchemy.orm import Session

from models import AuditLog


def record_audit(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    entity_type: str = "",
    entity_id: str | int | None = None,
    detail=None,
):
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id="" if entity_id is None else str(entity_id),
            detail_json=json.dumps(detail or {}, ensure_ascii=False)[:8000],
        )
    )
    db.commit()
