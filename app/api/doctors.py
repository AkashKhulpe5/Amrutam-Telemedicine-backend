from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.auth_dependencies import require_role
from app.database.database import get_db
from app.database.models import User, UserRole
from app.schemas.doctor import (
    AvailabilitySlotCreateRequest,
    AvailabilitySlotResponse,
    DoctorCreateRequest,
    DoctorListResponse,
    DoctorResponse,
)
from app.services.doctor_service import DoctorService


router = APIRouter(
    prefix="/api/v1/doctors",
    tags=["Doctors"],
)


# =========================================================
# SEARCH / FILTER DOCTORS
# =========================================================

@router.get(
    "",
    response_model=DoctorListResponse,
)
def search_doctors(
    page: int = Query(
        default=1,
        ge=1,
        description="Page number",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of doctors per page",
    ),
    specialization: str | None = Query(
        default=None,
        min_length=2,
        max_length=100,
        description="Search by specialization",
    ),
    min_experience: int | None = Query(
        default=None,
        ge=0,
        le=60,
        description="Minimum years of experience",
    ),
    max_experience: int | None = Query(
        default=None,
        ge=0,
        le=60,
        description="Maximum years of experience",
    ),
    min_fee: float | None = Query(
        default=None,
        ge=0,
        description="Minimum consultation fee",
    ),
    max_fee: float | None = Query(
        default=None,
        ge=0,
        description="Maximum consultation fee",
    ),
    verified_only: bool = Query(
        default=True,
        description="Return only verified doctors",
    ),
    db: Session = Depends(get_db),
):
    if (
        min_experience is not None
        and max_experience is not None
        and min_experience > max_experience
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_experience cannot be greater than max_experience",
        )

    if (
        min_fee is not None
        and max_fee is not None
        and min_fee > max_fee
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_fee cannot be greater than max_fee",
        )

    service = DoctorService(db)

    doctors, total = service.search_doctors(
        page=page,
        page_size=page_size,
        specialization=specialization,
        min_experience=min_experience,
        max_experience=max_experience,
        min_fee=min_fee,
        max_fee=max_fee,
        verified_only=verified_only,
    )

    total_pages = ceil(total / page_size) if total else 0

    return DoctorListResponse(
        items=doctors,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# =========================================================
# CREATE DOCTOR PROFILE
# =========================================================

@router.post(
    "/profile",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_doctor_profile(
    data: DoctorCreateRequest,
    request: Request,
    current_user: User = Depends(
        require_role(UserRole.DOCTOR)
    ),
    db: Session = Depends(get_db),
):
    service = DoctorService(db)

    try:
        return service.create_doctor_profile(
            user_id=current_user.id,
            data=data,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# =========================================================
# CREATE AVAILABILITY SLOT
# =========================================================

@router.post(
    "/availability",
    response_model=AvailabilitySlotResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_availability_slot(
    data: AvailabilitySlotCreateRequest,
    request: Request,
    current_user: User = Depends(
        require_role(UserRole.DOCTOR)
    ),
    db: Session = Depends(get_db),
):
    service = DoctorService(db)

    doctor = current_user.doctor_profile

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found",
        )

    try:
        return service.create_availability_slot(
            doctor_id=doctor.id,
            data=data,
            actor_user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# =========================================================
# GET DOCTOR AVAILABILITY
# =========================================================

@router.get(
    "/{doctor_id}/availability",
    response_model=list[AvailabilitySlotResponse],
)
def get_doctor_availability(
    doctor_id: UUID,
    db: Session = Depends(get_db),
):
    service = DoctorService(db)

    return service.get_available_slots(
        doctor_id=doctor_id,
    )