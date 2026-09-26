from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import AvailabilitySlot, Doctor
from app.schemas.doctor import (
    AvailabilitySlotCreateRequest,
    DoctorCreateRequest,
)
from app.services.audit_service import AuditService


class DoctorService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    # =====================================================
    # CREATE DOCTOR PROFILE
    # =====================================================

    def create_doctor_profile(
        self,
        user_id: UUID,
        data: DoctorCreateRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Doctor:
        existing_doctor = self.db.scalar(
            select(Doctor).where(
                Doctor.user_id == user_id
            )
        )

        if existing_doctor:
            raise ValueError(
                "Doctor profile already exists"
            )

        existing_license = self.db.scalar(
            select(Doctor).where(
                Doctor.license_number == data.license_number
            )
        )

        if existing_license:
            raise ValueError(
                "License number is already registered"
            )

        doctor = Doctor(
            user_id=user_id,
            specialization=data.specialization,
            license_number=data.license_number,
            experience_years=data.experience_years,
            consultation_fee=data.consultation_fee,
        )

        self.db.add(doctor)
        self.db.flush()

        self.audit_service.log_event(
            action="DOCTOR_PROFILE_CREATED",
            resource_type="DOCTOR",
            actor_user_id=user_id,
            resource_id=doctor.id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata={
                "specialization": doctor.specialization,
                "experience_years": doctor.experience_years,
            },
        )

        self.db.commit()
        self.db.refresh(doctor)

        return doctor

    # =====================================================
    # SEARCH / FILTER DOCTORS
    # =====================================================

    def search_doctors(
        self,
        page: int = 1,
        page_size: int = 20,
        specialization: str | None = None,
        min_experience: int | None = None,
        max_experience: int | None = None,
        min_fee: float | None = None,
        max_fee: float | None = None,
        verified_only: bool = True,
    ) -> tuple[list[Doctor], int]:

        filters = []

        # Only verified doctors by default
        if verified_only:
            filters.append(
                Doctor.is_verified.is_(True)
            )

        # Case-insensitive specialization search
        if specialization:
            filters.append(
                Doctor.specialization.ilike(
                    f"%{specialization.strip()}%"
                )
            )

        if min_experience is not None:
            filters.append(
                Doctor.experience_years >= min_experience
            )

        if max_experience is not None:
            filters.append(
                Doctor.experience_years <= max_experience
            )

        if min_fee is not None:
            filters.append(
                Doctor.consultation_fee >= min_fee
            )

        if max_fee is not None:
            filters.append(
                Doctor.consultation_fee <= max_fee
            )

        # Total count
        count_statement = select(
            func.count(Doctor.id)
        ).where(*filters)

        total = self.db.scalar(count_statement) or 0

        # Pagination
        offset = (page - 1) * page_size

        statement = (
            select(Doctor)
            .where(*filters)
            .order_by(
                Doctor.experience_years.desc(),
                Doctor.id.asc(),
            )
            .offset(offset)
            .limit(page_size)
        )

        doctors = list(
            self.db.scalars(statement).all()
        )

        return doctors, total

    # =====================================================
    # CREATE AVAILABILITY SLOT
    # =====================================================

    def create_availability_slot(
        self,
        doctor_id: UUID,
        data: AvailabilitySlotCreateRequest,
        *,
        actor_user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AvailabilitySlot:

        if data.end_time <= data.start_time:
            raise ValueError(
                "End time must be after start time"
            )

        existing_slot = self.db.scalar(
            select(AvailabilitySlot).where(
                AvailabilitySlot.doctor_id == doctor_id,
                AvailabilitySlot.start_time == data.start_time,
                AvailabilitySlot.end_time == data.end_time,
            )
        )

        if existing_slot:
            raise ValueError(
                "This availability slot already exists"
            )

        slot = AvailabilitySlot(
            doctor_id=doctor_id,
            start_time=data.start_time,
            end_time=data.end_time,
        )

        self.db.add(slot)
        self.db.flush()

        self.audit_service.log_event(
            action="AVAILABILITY_SLOT_CREATED",
            resource_type="AVAILABILITY_SLOT",
            actor_user_id=actor_user_id,
            resource_id=slot.id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata={
                "doctor_id": str(doctor_id),
                "start_time": slot.start_time.isoformat(),
                "end_time": slot.end_time.isoformat(),
            },
        )

        self.db.commit()
        self.db.refresh(slot)

        return slot

    # =====================================================
    # GET AVAILABLE SLOTS
    # =====================================================

    def get_available_slots(
        self,
        doctor_id: UUID,
    ) -> list[AvailabilitySlot]:

        now = datetime.now().astimezone()

        statement = (
            select(AvailabilitySlot)
            .where(
                AvailabilitySlot.doctor_id == doctor_id,
                AvailabilitySlot.is_booked.is_(False),
                AvailabilitySlot.start_time > now,
            )
            .order_by(
                AvailabilitySlot.start_time.asc()
            )
        )

        return list(
            self.db.scalars(statement).all()
        )