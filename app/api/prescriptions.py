from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user
from app.database.database import get_db
from app.database.models import User, UserRole
from app.schemas.prescription import (
    PrescriptionCreateRequest,
    PrescriptionResponse,
)
from app.services.prescription_service import PrescriptionService


router = APIRouter(
    prefix="/api/v1/prescriptions",
    tags=["Prescriptions"],
)


# ============================================================
# CREATE PRESCRIPTION
# ============================================================

@router.post(
    "",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prescription(
    data: PrescriptionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can create prescriptions",
        )

    service = PrescriptionService(db)

    try:
        return service.create_prescription(
            doctor_user_id=current_user.id,
            data=data,
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message:
            status_code_value = status.HTTP_404_NOT_FOUND
        elif "permission" in message:
            status_code_value = status.HTTP_403_FORBIDDEN
        elif "only be created" in message:
            status_code_value = status.HTTP_400_BAD_REQUEST
        elif "already exists" in message:
            status_code_value = status.HTTP_409_CONFLICT
        else:
            status_code_value = status.HTTP_400_BAD_REQUEST

        raise HTTPException(
            status_code=status_code_value,
            detail=message,
        ) from exc


# ============================================================
# GET PRESCRIPTION BY CONSULTATION
# ============================================================

@router.get(
    "/consultation/{consultation_id}",
    response_model=PrescriptionResponse,
)
def get_prescription_by_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = PrescriptionService(db)

    try:
        return service.get_prescription_by_consultation(
            consultation_id=consultation_id,
            user=current_user,
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message:
            status_code_value = status.HTTP_404_NOT_FOUND
        else:
            status_code_value = status.HTTP_403_FORBIDDEN

        raise HTTPException(
            status_code=status_code_value,
            detail=message,
        ) from exc


# ============================================================
# GET PRESCRIPTION BY ID
# ============================================================

@router.get(
    "/{prescription_id}",
    response_model=PrescriptionResponse,
)
def get_prescription(
    prescription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = PrescriptionService(db)

    try:
        return service.get_prescription(
            prescription_id=prescription_id,
            user=current_user,
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message:
            status_code_value = status.HTTP_404_NOT_FOUND
        else:
            status_code_value = status.HTTP_403_FORBIDDEN

        raise HTTPException(
            status_code=status_code_value,
            detail=message,
        ) from exc