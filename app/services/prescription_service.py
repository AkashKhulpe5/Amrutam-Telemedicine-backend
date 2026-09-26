from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Consultation,
    ConsultationStatus,
    Doctor,
    Prescription,
    User,
)
from app.schemas.prescription import PrescriptionCreateRequest


class PrescriptionService:
    def __init__(self, db: Session):
        self.db = db

    # ========================================================
    # CREATE PRESCRIPTION
    # ========================================================

    def create_prescription(
        self,
        doctor_user_id: UUID,
        data: PrescriptionCreateRequest,
    ) -> Prescription:

        # ----------------------------------------------------
        # 1. Find doctor profile belonging to logged-in user
        # ----------------------------------------------------

        doctor = self.db.scalar(
            select(Doctor).where(
                Doctor.user_id == doctor_user_id
            )
        )

        if not doctor:
            raise ValueError("Doctor profile not found")

        # ----------------------------------------------------
        # 2. Get consultation
        # ----------------------------------------------------

        consultation = self.db.scalar(
            select(Consultation).where(
                Consultation.id == data.consultation_id
            )
        )

        if not consultation:
            raise ValueError("Consultation not found")

        # ----------------------------------------------------
        # 3. Verify doctor owns this consultation
        # ----------------------------------------------------

        if consultation.doctor_id != doctor.id:
            raise ValueError(
                "You do not have permission to create a prescription "
                "for this consultation"
            )

        # ----------------------------------------------------
        # 4. Prescription allowed only after completion
        # ----------------------------------------------------

        if consultation.status != ConsultationStatus.COMPLETED:
            raise ValueError(
                "Prescription can only be created for a completed consultation"
            )

        # ----------------------------------------------------
        # 5. Verify patient still exists and is active
        # ----------------------------------------------------

        patient = self.db.scalar(
            select(User).where(
                User.id == consultation.patient_id
            )
        )

        if not patient:
            raise ValueError("Patient not found")

        # ----------------------------------------------------
        # 6. Prevent duplicate prescription
        # ----------------------------------------------------

        existing_prescription = self.db.scalar(
            select(Prescription).where(
                Prescription.consultation_id == consultation.id
            )
        )

        if existing_prescription:
            raise ValueError(
                "A prescription already exists for this consultation"
            )

        # ----------------------------------------------------
        # 7. Create prescription
        # ----------------------------------------------------

        prescription = Prescription(
            consultation_id=consultation.id,
            doctor_id=doctor.id,
            patient_id=consultation.patient_id,
            medicines=data.medicines,
            dosage=data.dosage,
            frequency=data.frequency,
            duration=data.duration,
            instructions=data.instructions,
        )

        self.db.add(prescription)
        self.db.commit()
        self.db.refresh(prescription)

        return prescription

    # ========================================================
    # GET PRESCRIPTION
    # ========================================================

    def get_prescription(
        self,
        prescription_id: UUID,
        user: User,
    ) -> Prescription:

        # ----------------------------------------------------
        # 1. Get prescription
        # ----------------------------------------------------

        prescription = self.db.scalar(
            select(Prescription).where(
                Prescription.id == prescription_id
            )
        )

        if not prescription:
            raise ValueError("Prescription not found")

        # ----------------------------------------------------
        # 2. Admin can access prescription
        # ----------------------------------------------------

        if user.role.value == "ADMIN":
            return prescription

        # ----------------------------------------------------
        # 3. Patient can access only their own prescription
        # ----------------------------------------------------

        if user.role.value == "PATIENT":

            if prescription.patient_id != user.id:
                raise ValueError(
                    "You do not have permission to access this prescription"
                )

            return prescription

        # ----------------------------------------------------
        # 4. Doctor can access only their own prescription
        # ----------------------------------------------------

        if user.role.value == "DOCTOR":

            doctor = self.db.scalar(
                select(Doctor).where(
                    Doctor.user_id == user.id
                )
            )

            if not doctor:
                raise ValueError("Doctor profile not found")

            if prescription.doctor_id != doctor.id:
                raise ValueError(
                    "You do not have permission to access this prescription"
                )

            return prescription

        # ----------------------------------------------------
        # 5. Unknown role
        # ----------------------------------------------------

        raise ValueError(
            "You do not have permission to access this prescription"
        )

    # ========================================================
    # GET PRESCRIPTION FOR CONSULTATION
    # ========================================================

    def get_prescription_by_consultation(
        self,
        consultation_id: UUID,
        user: User,
    ) -> Prescription:

        prescription = self.db.scalar(
            select(Prescription).where(
                Prescription.consultation_id == consultation_id
            )
        )

        if not prescription:
            raise ValueError("Prescription not found")

        # ----------------------------------------------------
        # Admin
        # ----------------------------------------------------

        if user.role.value == "ADMIN":
            return prescription

        # ----------------------------------------------------
        # Patient
        # ----------------------------------------------------

        if user.role.value == "PATIENT":

            if prescription.patient_id != user.id:
                raise ValueError(
                    "You do not have permission to access this prescription"
                )

            return prescription

        # ----------------------------------------------------
        # Doctor
        # ----------------------------------------------------

        if user.role.value == "DOCTOR":

            doctor = self.db.scalar(
                select(Doctor).where(
                    Doctor.user_id == user.id
                )
            )

            if not doctor:
                raise ValueError("Doctor profile not found")

            if prescription.doctor_id != doctor.id:
                raise ValueError(
                    "You do not have permission to access this prescription"
                )

            return prescription

        raise ValueError(
            "You do not have permission to access this prescription"
        )