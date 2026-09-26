import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database.models import (
    AvailabilitySlot,
    Consultation,
    ConsultationStatus,
    Doctor,
    IdempotencyKey,
)
from app.schemas.consultation import BookConsultationRequest
from app.services.audit_service import AuditService


IDEMPOTENCY_TTL_DAYS = 7


class ConsultationService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    # =========================================================
    # BOOKING
    # =========================================================

    @staticmethod
    def _request_hash(data: BookConsultationRequest) -> str:
        payload = {
            "slot_id": str(data.slot_id),
            "reason": data.reason,
        }

        canonical_payload = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            canonical_payload.encode("utf-8")
        ).hexdigest()

    def book_consultation(
        self,
        patient_id: UUID,
        data: BookConsultationRequest,
        idempotency_key: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Consultation:

        idempotency_key = idempotency_key.strip()

        if not idempotency_key:
            raise ValueError("Idempotency-Key header is required")

        if len(idempotency_key) > 255:
            raise ValueError("Idempotency-Key is too long")

        request_hash = self._request_hash(data)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=IDEMPOTENCY_TTL_DAYS)

        statement = (
            insert(IdempotencyKey)
            .values(
                key=idempotency_key,
                user_id=patient_id,
                request_hash=request_hash,
                consultation_id=None,
                created_at=now,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "key"]
            )
        )

        self.db.execute(statement)

        idempotency_record = self.db.scalar(
            select(IdempotencyKey)
            .where(
                IdempotencyKey.user_id == patient_id,
                IdempotencyKey.key == idempotency_key,
            )
            .with_for_update()
        )

        if not idempotency_record:
            self.db.rollback()
            raise ValueError("Unable to create idempotency record")

        if idempotency_record.request_hash != request_hash:
            self.db.rollback()
            raise ValueError(
                "Idempotency-Key was already used with a different request"
            )

        if idempotency_record.consultation_id is not None:
            consultation = self.db.get(
                Consultation,
                idempotency_record.consultation_id,
            )

            if consultation:
                self.db.commit()
                return consultation

            self.db.rollback()
            raise ValueError(
                "Idempotency record references a missing consultation"
            )

        if idempotency_record.expires_at <= now:
            self.db.rollback()
            raise ValueError(
                "Idempotency-Key has expired. Please use a new key."
            )

        # Lock the slot so concurrent requests cannot book it twice.
        slot = self.db.scalar(
            select(AvailabilitySlot)
            .where(AvailabilitySlot.id == data.slot_id)
            .with_for_update()
        )

        if not slot:
            self.db.rollback()
            raise ValueError("Availability slot not found")

        if slot.is_booked:
            self.db.rollback()
            raise ValueError("Availability slot is already booked")

        consultation = Consultation(
            patient_id=patient_id,
            doctor_id=slot.doctor_id,
            slot_id=slot.id,
            status=ConsultationStatus.BOOKED,
            reason=data.reason,
        )

        slot.is_booked = True

        self.db.add(consultation)
        self.db.flush()

        idempotency_record.consultation_id = consultation.id

        self.audit_service.log_event(
            action="CONSULTATION_BOOKED",
            resource_type="CONSULTATION",
            actor_user_id=patient_id,
            resource_id=consultation.id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata={
                "doctor_id": str(slot.doctor_id),
                "slot_id": str(slot.id),
                "status": ConsultationStatus.BOOKED.value,
            },
        )

        self.db.commit()
        self.db.refresh(consultation)

        return consultation

    # =========================================================
    # CONSULTATION RETRIEVAL
    # =========================================================

    def get_consultation(
        self,
        consultation_id: UUID,
        user_id: UUID,
        role: str,
    ) -> Consultation:

        consultation = self.db.get(
            Consultation,
            consultation_id,
        )

        if not consultation:
            raise ValueError("Consultation not found")

        # Patient ownership:
        # consultation.patient_id points directly to users.id.
        if role == "PATIENT":
            if consultation.patient_id != user_id:
                raise ValueError(
                    "You do not have permission to view this consultation"
                )

        # Doctor ownership:
        # consultation.doctor_id points to doctors.id,
        # NOT users.id.
        elif role == "DOCTOR":
            doctor = self.db.scalar(
                select(Doctor).where(
                    Doctor.user_id == user_id
                )
            )

            if not doctor:
                raise ValueError("Doctor profile not found")

            if consultation.doctor_id != doctor.id:
                raise ValueError(
                    "You do not have permission to view this consultation"
                )

        # ADMIN can access any consultation.

        return consultation

    def list_consultations(
        self,
        user_id: UUID,
        role: str,
        page: int = 1,
        page_size: int = 20,
        consultation_status: ConsultationStatus | None = None,
    ) -> tuple[list[Consultation], int]:

        if page < 1:
            raise ValueError(
                "Page must be greater than or equal to 1"
            )

        if page_size < 1 or page_size > 100:
            raise ValueError(
                "Page size must be between 1 and 100"
            )

        # -----------------------------------------------------
        # Base query
        # -----------------------------------------------------

        statement = select(Consultation)

        count_statement = select(
            func.count(Consultation.id)
        )

        # -----------------------------------------------------
        # Patient filtering
        # -----------------------------------------------------

        if role == "PATIENT":
            statement = statement.where(
                Consultation.patient_id == user_id
            )

            count_statement = count_statement.where(
                Consultation.patient_id == user_id
            )

        # -----------------------------------------------------
        # Doctor filtering
        # -----------------------------------------------------

        elif role == "DOCTOR":
            doctor = self.db.scalar(
                select(Doctor).where(
                    Doctor.user_id == user_id
                )
            )

            if not doctor:
                raise ValueError("Doctor profile not found")

            statement = statement.where(
                Consultation.doctor_id == doctor.id
            )

            count_statement = count_statement.where(
                Consultation.doctor_id == doctor.id
            )

        # -----------------------------------------------------
        # ADMIN
        # -----------------------------------------------------
        # Admin sees all consultations.

        # -----------------------------------------------------
        # Optional status filtering
        # -----------------------------------------------------

        if consultation_status is not None:
            statement = statement.where(
                Consultation.status == consultation_status
            )

            count_statement = count_statement.where(
                Consultation.status == consultation_status
            )

        # -----------------------------------------------------
        # Count
        # -----------------------------------------------------

        total = self.db.scalar(
            count_statement
        ) or 0

        # -----------------------------------------------------
        # Pagination
        # -----------------------------------------------------

        offset = (page - 1) * page_size

        statement = (
            statement
            .order_by(
                Consultation.created_at.desc()
            )
            .offset(offset)
            .limit(page_size)
        )

        consultations = list(
            self.db.scalars(statement).all()
        )

        return consultations, total

    # =========================================================
    # CONSULTATION LIFECYCLE
    # =========================================================

    def _get_consultation_for_update(
        self,
        consultation_id: UUID,
    ) -> Consultation:

        consultation = self.db.scalar(
            select(Consultation)
            .where(Consultation.id == consultation_id)
            .with_for_update()
        )

        if not consultation:
            raise ValueError("Consultation not found")

        return consultation

    @staticmethod
    def _ensure_doctor_owns_consultation(
        consultation: Consultation,
        doctor_id: UUID,
    ) -> None:

        if consultation.doctor_id != doctor_id:
            raise ValueError(
                "You do not have permission to modify this consultation"
            )

    @staticmethod
    def _ensure_patient_owns_consultation(
        consultation: Consultation,
        patient_id: UUID,
    ) -> None:

        if consultation.patient_id != patient_id:
            raise ValueError(
                "You do not have permission to modify this consultation"
            )

    @staticmethod
    def _validate_transition(
        current_status: ConsultationStatus,
        expected_status: ConsultationStatus,
        new_status: ConsultationStatus,
    ) -> None:

        if current_status != expected_status:
            raise ValueError(
                f"Invalid status transition: "
                f"{current_status.value} -> {new_status.value}"
            )

    # =========================================================
    # CONFIRM
    # =========================================================

    def confirm_consultation(
        self,
        consultation_id: UUID,
        doctor_id: UUID,
        *,
        actor_user_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Consultation:

        consultation = self._get_consultation_for_update(
            consultation_id
        )

        self._ensure_doctor_owns_consultation(
            consultation,
            doctor_id,
        )

        self._validate_transition(
            consultation.status,
            ConsultationStatus.BOOKED,
            ConsultationStatus.CONFIRMED,
        )

        previous_status = consultation.status
        consultation.status = ConsultationStatus.CONFIRMED

        self.audit_service.log_event(
            action="CONSULTATION_CONFIRMED",
            resource_type="CONSULTATION",
            actor_user_id=actor_user_id,
            resource_id=consultation.id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata={
                "doctor_id": str(doctor_id),
                "patient_id": str(consultation.patient_id),
                "slot_id": str(consultation.slot_id),
                "from_status": previous_status.value,
                "to_status": consultation.status.value,
            },
        )

        self.db.commit()
        self.db.refresh(consultation)

        return consultation

    # =========================================================
    # START
    # =========================================================

    def start_consultation(
        self,
        consultation_id: UUID,
        doctor_id: UUID,
        *,
        actor_user_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Consultation:

        consultation = self._get_consultation_for_update(
            consultation_id
        )

        self._ensure_doctor_owns_consultation(
            consultation,
            doctor_id,
        )

        self._validate_transition(
            consultation.status,
            ConsultationStatus.CONFIRMED,
            ConsultationStatus.IN_PROGRESS,
        )

        previous_status = consultation.status
        consultation.status = ConsultationStatus.IN_PROGRESS

        self.audit_service.log_event(
            action="CONSULTATION_STARTED",
            resource_type="CONSULTATION",
            actor_user_id=actor_user_id,
            resource_id=consultation.id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata={
                "doctor_id": str(doctor_id),
                "patient_id": str(consultation.patient_id),
                "slot_id": str(consultation.slot_id),
                "from_status": previous_status.value,
                "to_status": consultation.status.value,
            },
        )

        self.db.commit()
        self.db.refresh(consultation)

        return consultation

    # =========================================================
    # COMPLETE
    # =========================================================

    def complete_consultation(
        self,
        consultation_id: UUID,
        doctor_id: UUID,
        *,
        actor_user_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Consultation:

        consultation = self._get_consultation_for_update(
            consultation_id
        )

        self._ensure_doctor_owns_consultation(
            consultation,
            doctor_id,
        )

        self._validate_transition(
            consultation.status,
            ConsultationStatus.IN_PROGRESS,
            ConsultationStatus.COMPLETED,
        )

        previous_status = consultation.status
        consultation.status = ConsultationStatus.COMPLETED

        self.audit_service.log_event(
            action="CONSULTATION_COMPLETED",
            resource_type="CONSULTATION",
            actor_user_id=actor_user_id,
            resource_id=consultation.id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata={
                "doctor_id": str(doctor_id),
                "patient_id": str(consultation.patient_id),
                "slot_id": str(consultation.slot_id),
                "from_status": previous_status.value,
                "to_status": consultation.status.value,
            },
        )

        self.db.commit()
        self.db.refresh(consultation)

        return consultation

    # =========================================================
    # CANCEL
    # =========================================================

    def cancel_consultation(
        self,
        consultation_id: UUID,
        patient_id: UUID,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Consultation:

        consultation = self._get_consultation_for_update(
            consultation_id
        )

        self._ensure_patient_owns_consultation(
            consultation,
            patient_id,
        )

        allowed_statuses = {
            ConsultationStatus.BOOKED,
            ConsultationStatus.CONFIRMED,
        }

        if consultation.status not in allowed_statuses:
            raise ValueError(
                f"Invalid status transition: "
                f"{consultation.status.value} -> "
                f"{ConsultationStatus.CANCELLED.value}"
            )

        # Lock the slot in the same transaction.
        slot = self.db.scalar(
            select(AvailabilitySlot)
            .where(
                AvailabilitySlot.id == consultation.slot_id
            )
            .with_for_update()
        )

        if not slot:
            raise ValueError(
                "Availability slot not found"
            )

        previous_status = consultation.status

        # Cancel consultation and release slot
        # atomically in the same transaction.
        consultation.status = ConsultationStatus.CANCELLED
        slot.is_booked = False

        self.audit_service.log_event(
            action="CONSULTATION_CANCELLED",
            resource_type="CONSULTATION",
            actor_user_id=patient_id,
            resource_id=consultation.id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata={
                "doctor_id": str(consultation.doctor_id),
                "patient_id": str(patient_id),
                "slot_id": str(consultation.slot_id),
                "from_status": previous_status.value,
                "to_status": consultation.status.value,
                "slot_released": True,
            },
        )

        self.db.commit()
        self.db.refresh(consultation)

        return consultation