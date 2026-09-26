from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    user_agent: str | None
    event_metadata: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ConsultationStatusCount(BaseModel):
    status: str
    count: int


class AdminAnalyticsResponse(BaseModel):
    total_users: int
    active_users: int
    total_patients: int
    total_doctors: int
    verified_doctors: int
    total_consultations: int
    consultations_by_status: list[ConsultationStatusCount]
    total_prescriptions: int
    total_audit_events: int