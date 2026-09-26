from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.database.models import AuditLog


class AuditService:
    """Service responsible for creating compliance and security audit events."""

    def __init__(self, db: Session):
        self.db = db

    def log_event(
        self,
        *,
        action: str,
        resource_type: str,
        actor_user_id: UUID | None = None,
        resource_id: UUID | str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        event_metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """
        Create and persist an audit log entry.

        Audit metadata must contain only non-sensitive information.
        Never store passwords, JWTs, refresh tokens, API keys,
        prescription contents, or other secrets here.
        """

        audit_log = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata=event_metadata,
        )

        self.db.add(audit_log)
        self.db.flush()

        return audit_log