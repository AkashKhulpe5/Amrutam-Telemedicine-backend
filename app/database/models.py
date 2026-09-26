import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


# ============================================================
# ENUMS
# ============================================================

class UserRole(str, enum.Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"


class ConsultationStatus(str, enum.Enum):
    BOOKED = "BOOKED"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


# ============================================================
# USER
# ============================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.PATIENT,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    doctor_profile: Mapped["Doctor | None"] = relationship(
        back_populates="user",
        uselist=False,
    )

    patient_consultations: Mapped[list["Consultation"]] = relationship(
        foreign_keys="Consultation.patient_id",
        back_populates="patient",
    )

    idempotency_keys: Mapped[list["IdempotencyKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    prescriptions: Mapped[list["Prescription"]] = relationship(
        foreign_keys="Prescription.patient_id",
        back_populates="patient",
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        foreign_keys="AuditLog.actor_user_id",
        back_populates="actor",
    )


# ============================================================
# DOCTOR
# ============================================================

class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    specialization: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    license_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    experience_years: Mapped[int] = mapped_column(
        nullable=False,
    )

    consultation_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    user: Mapped["User"] = relationship(
        back_populates="doctor_profile",
    )

    availability_slots: Mapped[list["AvailabilitySlot"]] = relationship(
        back_populates="doctor",
        cascade="all, delete-orphan",
    )

    consultations: Mapped[list["Consultation"]] = relationship(
        back_populates="doctor",
    )

    prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="doctor",
    )

    # --------------------------------------------------------
    # Constraints / Indexes
    # --------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "experience_years >= 0",
            name="ck_doctors_experience_non_negative",
        ),
        CheckConstraint(
            "consultation_fee > 0",
            name="ck_doctors_consultation_fee_positive",
        ),
        Index(
            "ix_doctors_specialization_verified",
            "specialization",
            "is_verified",
        ),
    )


# ============================================================
# AVAILABILITY SLOT
# ============================================================

class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    is_booked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    doctor: Mapped["Doctor"] = relationship(
        back_populates="availability_slots",
    )

    consultation: Mapped["Consultation | None"] = relationship(
        back_populates="slot",
        uselist=False,
    )

    # --------------------------------------------------------
    # Constraints / Indexes
    # --------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="ck_availability_end_after_start",
        ),
        UniqueConstraint(
            "doctor_id",
            "start_time",
            "end_time",
            name="uq_doctor_availability_time",
        ),
        Index(
            "ix_availability_doctor_booked_start",
            "doctor_id",
            "is_booked",
            "start_time",
        ),
    )


# ============================================================
# CONSULTATION
# ============================================================

class Consultation(Base):
    __tablename__ = "consultations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("availability_slots.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )

    status: Mapped[ConsultationStatus] = mapped_column(
        Enum(
            ConsultationStatus,
            name="consultation_status",
        ),
        nullable=False,
        default=ConsultationStatus.BOOKED,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    patient: Mapped["User"] = relationship(
        foreign_keys=[patient_id],
        back_populates="patient_consultations",
    )

    doctor: Mapped["Doctor"] = relationship(
        back_populates="consultations",
    )

    slot: Mapped["AvailabilitySlot"] = relationship(
        back_populates="consultation",
    )

    idempotency_keys: Mapped[list["IdempotencyKey"]] = relationship(
        back_populates="consultation",
    )

    prescription: Mapped["Prescription | None"] = relationship(
        back_populates="consultation",
        uselist=False,
    )

    # --------------------------------------------------------
    # Indexes
    # --------------------------------------------------------

    __table_args__ = (
        Index(
            "ix_consultations_patient_status_created",
            "patient_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_consultations_doctor_status_created",
            "doctor_id",
            "status",
            "created_at",
        ),
    )


# ============================================================
# PRESCRIPTION
# ============================================================

class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    medicines: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    dosage: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    frequency: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    duration: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    instructions: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    consultation: Mapped["Consultation"] = relationship(
        back_populates="prescription",
    )

    doctor: Mapped["Doctor"] = relationship(
        back_populates="prescriptions",
    )

    patient: Mapped["User"] = relationship(
        foreign_keys=[patient_id],
        back_populates="prescriptions",
    )

    # --------------------------------------------------------
    # Constraints / Indexes
    # --------------------------------------------------------

    __table_args__ = (
        Index(
            "ix_prescriptions_patient_created",
            "patient_id",
            "created_at",
        ),
        Index(
            "ix_prescriptions_doctor_created",
            "doctor_id",
            "created_at",
        ),
    )


# ============================================================
# IDEMPOTENCY KEYS
# ============================================================

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    consultation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    user: Mapped["User"] = relationship(
        back_populates="idempotency_keys",
    )

    consultation: Mapped["Consultation | None"] = relationship(
        back_populates="idempotency_keys",
    )

    # --------------------------------------------------------
    # Constraints / Indexes
    # --------------------------------------------------------

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "key",
            name="uq_idempotency_user_key",
        ),
        Index(
            "ix_idempotency_user_created",
            "user_id",
            "created_at",
        ),
    )


# ============================================================
# AUDIT LOG
# ============================================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # "metadata" is the PostgreSQL column name.
    # "event_metadata" is the Python/SQLAlchemy attribute name
    # because "metadata" is reserved by SQLAlchemy Declarative API.
    event_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    actor: Mapped["User | None"] = relationship(
        foreign_keys=[actor_user_id],
        back_populates="audit_logs",
    )

    # --------------------------------------------------------
    # Indexes
    # --------------------------------------------------------

    __table_args__ = (
        Index(
            "ix_audit_logs_actor_created",
            "actor_user_id",
            "created_at",
        ),
        Index(
            "ix_audit_logs_resource_created",
            "resource_type",
            "resource_id",
            "created_at",
        ),
    )