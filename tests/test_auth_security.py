from fastapi.testclient import TestClient

from app.main import app


def test_me_rejects_request_without_token():
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_patient_only_rejects_request_without_token():
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/patient-only")

    assert response.status_code == 401