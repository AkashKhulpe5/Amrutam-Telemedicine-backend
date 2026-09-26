from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# PRESCRIPTION CREATE REQUEST
# ============================================================

class PrescriptionCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    consultation_id: UUID

    medicines: str = Field(
        min_length=1,
        max_length=2000,
        description="Prescribed medicines, including medicine names and details",
    )

    dosage: str = Field(
        min_length=1,
        max_length=500,
        description="Dosage instructions for the prescribed medicines",
    )

    frequency: str = Field(
        min_length=1,
        max_length=500,
        description="How frequently the medicines should be taken",
    )

    duration: str = Field(
        min_length=1,
        max_length=255,
        description="Duration of the medication",
    )

    instructions: str | None = Field(
        default=None,
        max_length=2000,
        description="Additional instructions for the patient",
    )


# ============================================================
# PRESCRIPTION RESPONSE
# ============================================================

class PrescriptionResponse(BaseModel):
    id: UUID
    consultation_id: UUID
    doctor_id: UUID
    patient_id: UUID
    medicines: str
    dosage: str
    frequency: str
    duration: str
    instructions: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)