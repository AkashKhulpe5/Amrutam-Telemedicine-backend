from math import ceil
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user
from app.database.database import get_db
from app.database.models import ConsultationStatus, User, UserRole
from app.schemas.consultation import (
    BookConsultationRequest,
    ConsultationListResponse,
    ConsultationResponse,
)
from app.services.consultation_service import ConsultationService


router = APIRouter(
    prefix="/api/v1/consultations",
    tags=["Consultations"],
)


# =========================================================
# BOOK CONSULTATION
# =========================================================

@router.post(
    "/book",
    response_model=ConsultationResponse,
    status_code=status.HTTP_201_CREATED,
)
def book_consultation(
    data: BookConsultationRequest,
    request: Request,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.PATIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can book consultations",
        )

    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )

    service = ConsultationService(db)

    try:
        return service.book_consultation(
            patient_id=current_user.id,
            data=data,
            idempotency_key=idempotency_key.strip(),
            ip_address=(
                request.client.host
                if request.client
                else None
            ),
            user_agent=request.headers.get("user-agent"),
        )

    except ValueError as exc:
        message = str(exc)

        if (
            "different request" in message
            or "already booked" in message
            or "expired" in message
        ):
            status_code = status.HTTP_409_CONFLICT

        elif "not found" in message:
            status_code = status.HTTP_404_NOT_FOUND

        else:
            status_code = status.HTTP_409_CONFLICT

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc


# =========================================================
# LIST MY CONSULTATIONS
# IMPORTANT: Must be BEFORE /{consultation_id}
# =========================================================

@router.get(
    "/my",
    response_model=ConsultationListResponse,
)
def list_my_consultations(
    page: int = Query(
        default=1,
        ge=1,
        description="Page number",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of records per page",
    ),
    consultation_status: ConsultationStatus | None = Query(
        default=None,
        alias="status",
        description="Filter by consultation status",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ConsultationService(db)

    try:
        consultations, total = service.list_consultations(
            user_id=current_user.id,
            role=current_user.role.value,
            page=page,
            page_size=page_size,
            consultation_status=consultation_status,
        )

    except ValueError as exc:
        message = str(exc)

        if "Doctor profile not found" in message:
            status_code = status.HTTP_404_NOT_FOUND

        else:
            status_code = status.HTTP_400_BAD_REQUEST

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc

    total_pages = ceil(total / page_size) if total else 0

    return ConsultationListResponse(
        items=consultations,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# =========================================================
# GET SINGLE CONSULTATION
# =========================================================

@router.get(
    "/{consultation_id}",
    response_model=ConsultationResponse,
)
def get_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ConsultationService(db)

    try:
        return service.get_consultation(
            consultation_id=consultation_id,
            user_id=current_user.id,
            role=current_user.role.value,
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message:
            status_code = status.HTTP_404_NOT_FOUND

        elif "permission" in message:
            status_code = status.HTTP_403_FORBIDDEN

        else:
            status_code = status.HTTP_400_BAD_REQUEST

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc


# =========================================================
# CONFIRM CONSULTATION
# =========================================================

@router.post(
    "/{consultation_id}/confirm",
    response_model=ConsultationResponse,
)
def confirm_consultation(
    consultation_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can confirm consultations",
        )

    doctor = current_user.doctor_profile

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found",
        )

    service = ConsultationService(db)

    try:
        return service.confirm_consultation(
            consultation_id=consultation_id,
            doctor_id=doctor.id,
            actor_user_id=current_user.id,
            ip_address=(
                request.client.host
                if request.client
                else None
            ),
            user_agent=request.headers.get("user-agent"),
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message:
            status_code = status.HTTP_404_NOT_FOUND

        elif "permission" in message:
            status_code = status.HTTP_403_FORBIDDEN

        else:
            status_code = status.HTTP_409_CONFLICT

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc


# =========================================================
# START CONSULTATION
# =========================================================

@router.post(
    "/{consultation_id}/start",
    response_model=ConsultationResponse,
)
def start_consultation(
    consultation_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can start consultations",
        )

    doctor = current_user.doctor_profile

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found",
        )

    service = ConsultationService(db)

    try:
        return service.start_consultation(
            consultation_id=consultation_id,
            doctor_id=doctor.id,
            actor_user_id=current_user.id,
            ip_address=(
                request.client.host
                if request.client
                else None
            ),
            user_agent=request.headers.get("user-agent"),
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message:
            status_code = status.HTTP_404_NOT_FOUND

        elif "permission" in message:
            status_code = status.HTTP_403_FORBIDDEN

        else:
            status_code = status.HTTP_409_CONFLICT

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc


# =========================================================
# COMPLETE CONSULTATION
# =========================================================

@router.post(
    "/{consultation_id}/complete",
    response_model=ConsultationResponse,
)
def complete_consultation(
    consultation_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can complete consultations",
        )

    doctor = current_user.doctor_profile

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found",
        )

    service = ConsultationService(db)

    try:
        return service.complete_consultation(
            consultation_id=consultation_id,
            doctor_id=doctor.id,
            actor_user_id=current_user.id,
            ip_address=(
                request.client.host
                if request.client
                else None
            ),
            user_agent=request.headers.get("user-agent"),
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message:
            status_code = status.HTTP_404_NOT_FOUND

        elif "permission" in message:
            status_code = status.HTTP_403_FORBIDDEN

        else:
            status_code = status.HTTP_409_CONFLICT

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc


# =========================================================
# CANCEL CONSULTATION
# =========================================================

@router.post(
    "/{consultation_id}/cancel",
    response_model=ConsultationResponse,
)
def cancel_consultation(
    consultation_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.PATIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can cancel consultations",
        )

    service = ConsultationService(db)

    try:
        return service.cancel_consultation(
            consultation_id=consultation_id,
            patient_id=current_user.id,
            ip_address=(
                request.client.host
                if request.client
                else None
            ),
            user_agent=request.headers.get("user-agent"),
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message:
            status_code = status.HTTP_404_NOT_FOUND

        elif "permission" in message:
            status_code = status.HTTP_403_FORBIDDEN

        else:
            status_code = status.HTTP_409_CONFLICT

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc