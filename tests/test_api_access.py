from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.auth_dependencies import get_current_user
from app.database.database import get_db
from app.database.models import UserRole
from app.main import app


@pytest.fixture
def patient():
    return SimpleNamespace(
        id=uuid4(),
        email="patient-test@example.com",
        phone=None,
        role=UserRole.PATIENT,
        is_active=True,
        doctor_profile=None,
    )


@pytest.fixture
def doctor():
    return SimpleNamespace(
        id=uuid4(),
        email="doctor-test@example.com",
        phone=None,
        role=UserRole.DOCTOR,
        is_active=True,
        doctor_profile=SimpleNamespace(id=uuid4()),
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def override_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


def test_patient_can_access_patient_only_endpoint(client, patient):
    override_user(patient)

    response = client.get("/api/v1/auth/patient-only")

    assert response.status_code == 200
    assert response.json()["role"] == "PATIENT"


def test_doctor_cannot_access_patient_only_endpoint(client, doctor):
    override_user(doctor)

    response = client.get("/api/v1/auth/patient-only")

    assert response.status_code == 403


def test_authenticated_user_can_access_me(client, patient):
    override_user(patient)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "patient-test@example.com"


def test_booking_requires_idempotency_key(client, patient):
    override_user(patient)

    response = client.post(
        "/api/v1/consultations/book",
        json={
            "slot_id": str(uuid4()),
            "reason": "General consultation",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Idempotency-Key header is required"


def test_doctor_cannot_book_consultation(client, doctor):
    override_user(doctor)

    response = client.post(
        "/api/v1/consultations/book",
        headers={"Idempotency-Key": "test-booking-key"},
        json={
            "slot_id": str(uuid4()),
            "reason": "General consultation",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only patients can book consultations"


def test_patient_booking_calls_service(client, patient):
    override_user(patient)

    consultation_id = uuid4()
    slot_id = uuid4()
    now = datetime.now(timezone.utc)

    mocked_consultation = SimpleNamespace(
        id=consultation_id,
        patient_id=patient.id,
        doctor_id=uuid4(),
        slot_id=slot_id,
        status="BOOKED",
        reason="General consultation",
        created_at=now,
        updated_at=now,
    )

    with patch(
        "app.api.consultations.ConsultationService.book_consultation",
        return_value=mocked_consultation,
    ) as mocked_book:
        response = client.post(
            "/api/v1/consultations/book",
            headers={"Idempotency-Key": "test-booking-key"},
            json={
                "slot_id": str(slot_id),
                "reason": "General consultation",
            },
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(consultation_id)
    mocked_book.assert_called_once()