from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.database.models import ConsultationStatus


class BookConsultationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    slot_id: UUID
    reason: str | None = Field(
        default=None,
        max_length=500,
    )


class ConsultationResponse(BaseModel):
    id: UUID
    patient_id: UUID
    doctor_id: UUID
    slot_id: UUID
    status: ConsultationStatus
    reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConsultationListResponse(BaseModel):
    items: list[ConsultationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int