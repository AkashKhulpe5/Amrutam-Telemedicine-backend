import pytest

from app.database.models import ConsultationStatus
from app.services.consultation_service import ConsultationService


def test_valid_status_transition_does_not_raise():
    ConsultationService._validate_transition(
        ConsultationStatus.BOOKED,
        ConsultationStatus.BOOKED,
        ConsultationStatus.CONFIRMED,
    )


@pytest.mark.parametrize(
    ("current_status", "expected_status", "new_status"),
    [
        (
            ConsultationStatus.CONFIRMED,
            ConsultationStatus.BOOKED,
            ConsultationStatus.CONFIRMED,
        ),
        (
            ConsultationStatus.BOOKED,
            ConsultationStatus.CONFIRMED,
            ConsultationStatus.IN_PROGRESS,
        ),
        (
            ConsultationStatus.COMPLETED,
            ConsultationStatus.IN_PROGRESS,
            ConsultationStatus.COMPLETED,
        ),
    ],
)
def test_invalid_status_transition_raises(
    current_status,
    expected_status,
    new_status,
):
    with pytest.raises(ValueError, match="Invalid status transition"):
        ConsultationService._validate_transition(
            current_status,
            expected_status,
            new_status,
        )


def test_doctor_ownership_validation_rejects_wrong_doctor():
    from types import SimpleNamespace
    from uuid import uuid4

    consultation = SimpleNamespace(doctor_id=uuid4())

    with pytest.raises(ValueError, match="permission"):
        ConsultationService._ensure_doctor_owns_consultation(
            consultation,
            uuid4(),
        )


def test_patient_ownership_validation_rejects_wrong_patient():
    from types import SimpleNamespace
    from uuid import uuid4

    consultation = SimpleNamespace(patient_id=uuid4())

    with pytest.raises(ValueError, match="permission"):
        ConsultationService._ensure_patient_owns_consultation(
            consultation,
            uuid4(),
        )