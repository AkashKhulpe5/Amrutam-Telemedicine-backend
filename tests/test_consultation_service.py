from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.database.models import Consultation, ConsultationStatus
from app.schemas.consultation import BookConsultationRequest
from app.services.consultation_service import ConsultationService


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def service(db):
    consultation_service = ConsultationService(db)
    consultation_service.audit_service = MagicMock()
    return consultation_service


def make_booking_request(slot_id):
    return BookConsultationRequest(
        slot_id=slot_id,
        reason="General consultation",
    )


def make_idempotency_record(patient_id, request_hash, consultation_id=None):
    return SimpleNamespace(
        user_id=patient_id,
        key="test-idempotency-key",
        request_hash=request_hash,
        consultation_id=consultation_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )


def test_booking_success(service, db):
    patient_id = uuid4()
    doctor_id = uuid4()
    slot_id = uuid4()

    request = make_booking_request(slot_id)
    request_hash = service._request_hash(request)

    idempotency_record = make_idempotency_record(
        patient_id,
        request_hash,
    )

    slot = SimpleNamespace(
        id=slot_id,
        doctor_id=doctor_id,
        is_booked=False,
    )

    db.scalar.side_effect = [idempotency_record, slot]

    def fake_flush():
        # Simulate the database assigning the primary key on insert.
        for item in db.add.call_args_list:
            obj = item.args[0]
            if isinstance(obj, Consultation) and obj.id is None:
                obj.id = uuid4()

    db.flush.side_effect = fake_flush

    result = service.book_consultation(
        patient_id,
        request,
        "test-idempotency-key",
    )

    assert result.patient_id == patient_id
    assert result.doctor_id == doctor_id
    assert result.slot_id == slot_id
    assert result.status == ConsultationStatus.BOOKED
    assert slot.is_booked is True
    assert idempotency_record.consultation_id == result.id

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)
    service.audit_service.log_event.assert_called_once()


def test_booking_rejects_reused_key_with_different_request(service, db):
    patient_id = uuid4()
    slot_id = uuid4()

    request = make_booking_request(slot_id)

    record = make_idempotency_record(
        patient_id,
        request_hash="different-request-hash",
    )

    db.scalar.return_value = record

    with pytest.raises(
        ValueError,
        match="already used with a different request",
    ):
        service.book_consultation(
            patient_id,
            request,
            "test-idempotency-key",
        )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_booking_rejects_already_booked_slot(service, db):
    patient_id = uuid4()
    doctor_id = uuid4()
    slot_id = uuid4()

    request = make_booking_request(slot_id)
    request_hash = service._request_hash(request)

    record = make_idempotency_record(patient_id, request_hash)

    slot = SimpleNamespace(
        id=slot_id,
        doctor_id=doctor_id,
        is_booked=True,
    )

    db.scalar.side_effect = [record, slot]

    with pytest.raises(
        ValueError,
        match="Availability slot is already booked",
    ):
        service.book_consultation(
            patient_id,
            request,
            "test-idempotency-key",
        )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_booking_rejects_blank_idempotency_key(service, db):
    patient_id = uuid4()
    request = make_booking_request(uuid4())

    with pytest.raises(
        ValueError,
        match="Idempotency-Key header is required",
    ):
        service.book_consultation(patient_id, request, "   ")

    db.execute.assert_not_called()
    db.commit.assert_not_called()


def test_booking_replays_existing_idempotent_request(service, db):
    patient_id = uuid4()
    slot_id = uuid4()
    existing_consultation_id = uuid4()

    request = make_booking_request(slot_id)
    request_hash = service._request_hash(request)

    record = make_idempotency_record(
        patient_id,
        request_hash,
        consultation_id=existing_consultation_id,
    )

    existing_consultation = SimpleNamespace(
        id=existing_consultation_id,
        patient_id=patient_id,
        slot_id=slot_id,
    )

    db.scalar.return_value = record
    db.get.return_value = existing_consultation

    result = service.book_consultation(
        patient_id,
        request,
        "test-idempotency-key",
    )

    assert result is existing_consultation
    db.get.assert_called_once_with(
        Consultation,
        existing_consultation_id,
    )
    db.commit.assert_called_once()
    db.add.assert_not_called()


def test_cancellation_success_releases_slot(service, db):
    patient_id = uuid4()
    doctor_id = uuid4()
    consultation_id = uuid4()
    slot_id = uuid4()

    consultation = SimpleNamespace(
        id=consultation_id,
        patient_id=patient_id,
        doctor_id=doctor_id,
        slot_id=slot_id,
        status=ConsultationStatus.BOOKED,
    )

    slot = SimpleNamespace(
        id=slot_id,
        is_booked=True,
    )

    db.scalar.side_effect = [consultation, slot]

    result = service.cancel_consultation(
        consultation_id,
        patient_id,
    )

    assert result is consultation
    assert consultation.status == ConsultationStatus.CANCELLED
    assert slot.is_booked is False

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(consultation)
    service.audit_service.log_event.assert_called_once()


def test_cancellation_rejects_wrong_patient(service, db):
    consultation_id = uuid4()
    owner_patient_id = uuid4()
    other_patient_id = uuid4()

    consultation = SimpleNamespace(
        id=consultation_id,
        patient_id=owner_patient_id,
        doctor_id=uuid4(),
        slot_id=uuid4(),
        status=ConsultationStatus.BOOKED,
    )

    db.scalar.return_value = consultation

    with pytest.raises(
        ValueError,
        match="do not have permission to modify",
    ):
        service.cancel_consultation(
            consultation_id,
            other_patient_id,
        )

    db.commit.assert_not_called()


def test_cancellation_rejects_completed_consultation(service, db):
    patient_id = uuid4()
    consultation_id = uuid4()

    consultation = SimpleNamespace(
        id=consultation_id,
        patient_id=patient_id,
        doctor_id=uuid4(),
        slot_id=uuid4(),
        status=ConsultationStatus.COMPLETED,
    )

    db.scalar.return_value = consultation

    with pytest.raises(
        ValueError,
        match="Invalid status transition",
    ):
        service.cancel_consultation(
            consultation_id,
            patient_id,
        )

    db.commit.assert_not_called()