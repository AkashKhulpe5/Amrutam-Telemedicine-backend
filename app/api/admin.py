from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth_dependencies import require_role
from app.database.database import get_db
from app.database.models import User, UserRole
from app.schemas.admin import (
    AdminAnalyticsResponse,
    AuditLogListResponse,
)
from app.services.admin_service import AdminService


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
)


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="List audit logs",
)
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None, min_length=1, max_length=100),
    resource_type: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    actor_user_id: UUID | None = Query(default=None),
    current_user: User = Depends(
        require_role(UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
):
    service = AdminService(db)

    logs, total = service.list_audit_logs(
        page=page,
        page_size=page_size,
        action=action,
        resource_type=resource_type,
        actor_user_id=str(actor_user_id) if actor_user_id else None,
    )

    return AuditLogListResponse(
        items=logs,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get(
    "/analytics",
    response_model=AdminAnalyticsResponse,
    summary="Get admin analytics",
)
def get_admin_analytics(
    current_user: User = Depends(
        require_role(UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
):
    service = AdminService(db)

    return service.get_analytics()