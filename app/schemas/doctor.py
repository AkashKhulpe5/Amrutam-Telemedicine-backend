from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DoctorCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    specialization: str = Field(min_length=2, max_length=100)
    license_number: str = Field(min_length=3, max_length=100)
    experience_years: int = Field(ge=0, le=60)
    consultation_fee: float = Field(gt=0)


class DoctorResponse(BaseModel):
    id: UUID
    user_id: UUID
    specialization: str
    license_number: str
    experience_years: int
    consultation_fee: float
    is_verified: bool

    model_config = ConfigDict(from_attributes=True)


class DoctorListResponse(BaseModel):
    items: list[DoctorResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AvailabilitySlotCreateRequest(BaseModel):
    start_time: datetime
    end_time: datetime


class AvailabilitySlotResponse(BaseModel):
    id: UUID
    doctor_id: UUID
    start_time: datetime
    end_time: datetime
    is_booked: bool

    model_config = ConfigDict(from_attributes=True)