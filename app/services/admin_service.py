from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    AuditLog,
    Consultation,
    ConsultationStatus,
    Doctor,
    Prescription,
    User,
    UserRole,
)


class AdminService:
    def __init__(self, db: Session):
        self.db = db

    def list_audit_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        action: str | None = None,
        resource_type: str | None = None,
        actor_user_id: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        filters = []

        if action:
            filters.append(AuditLog.action == action)

        if resource_type:
            filters.append(
                AuditLog.resource_type == resource_type
            )

        if actor_user_id:
            filters.append(
                AuditLog.actor_user_id == actor_user_id
            )

        total = self.db.scalar(
            select(func.count(AuditLog.id)).where(*filters)
        ) or 0

        statement = (
            select(AuditLog)
            .where(*filters)
            .order_by(
                AuditLog.created_at.desc(),
                AuditLog.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        logs = list(self.db.scalars(statement).all())

        return logs, total

    def get_analytics(self) -> dict:
        total_users = self.db.scalar(
            select(func.count(User.id))
        ) or 0

        active_users = self.db.scalar(
            select(func.count(User.id)).where(
                User.is_active.is_(True)
            )
        ) or 0

        total_patients = self.db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.PATIENT
            )
        ) or 0

        total_doctors = self.db.scalar(
            select(func.count(Doctor.id))
        ) or 0

        verified_doctors = self.db.scalar(
            select(func.count(Doctor.id)).where(
                Doctor.is_verified.is_(True)
            )
        ) or 0

        total_consultations = self.db.scalar(
            select(func.count(Consultation.id))
        ) or 0

        status_rows = self.db.execute(
            select(
                Consultation.status,
                func.count(Consultation.id),
            ).group_by(Consultation.status)
        ).all()

        consultations_by_status = [
            {
                "status": status.value,
                "count": count,
            }
            for status, count in status_rows
        ]

        total_prescriptions = self.db.scalar(
            select(func.count(Prescription.id))
        ) or 0

        total_audit_events = self.db.scalar(
            select(func.count(AuditLog.id))
        ) or 0

        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "verified_doctors": verified_doctors,
            "total_consultations": total_consultations,
            "consultations_by_status": consultations_by_status,
            "total_prescriptions": total_prescriptions,
            "total_audit_events": total_audit_events,
        }