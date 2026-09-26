# Amrutam Telemedicine Backend

A REST API backend for a telemedicine platform, built with **FastAPI**, **SQLAlchemy**, and **PostgreSQL**. The application supports authentication, role-based access, doctor availability, consultation booking and lifecycle management, prescriptions, audit logging, and administrative endpoints.

## Project Status

| Area | Status |
|---|---|
| REST API | Implemented |
| Authentication and role-based access | Implemented |
| Doctor availability and consultations | Implemented |
| Prescription and audit-log functionality | Implemented |
| PostgreSQL database and Alembic migrations | Configured |
| Health checks and Prometheus metrics endpoint | Implemented |
| Automated tests | 22 passed in the latest recorded run |
| Prometheus/Grafana configuration files | Present in `monitoring/` |
| Production deployment and load testing | Not yet verified |

The test suite includes mocked service tests. Passing tests do not by themselves establish production performance, availability, or real-database concurrency behavior.

## Features

### Authentication and Authorization
- User registration and login
- JWT-based authentication
- Role-based access for patients, doctors, and administrators
- Protected API endpoints

### Doctor Availability
- Doctor profiles and availability slots
- Availability booking status
- Database constraints for availability records

### Consultation Management
- Patient consultation booking
- Consultation lifecycle statuses:
  - `BOOKED`
  - `CONFIRMED`
  - `IN_PROGRESS`
  - `COMPLETED`
  - `CANCELLED`
  - `NO_SHOW`
- Patient and doctor ownership checks
- Idempotency-key support for booking requests
- Transaction-based booking and cancellation logic
- Slot locking in the service implementation

### Prescriptions
- Prescription records associated with consultations, doctors, and patients

### Audit Logging
- Persisted audit events for selected authentication, availability, and consultation actions

### Administration
- Administrative audit-log endpoint
- Administrative analytics endpoint
- Admin-only access controls

### Health and Monitoring
- Liveness endpoint: `/health/live`
- Readiness endpoint: `/health/ready`
- Prometheus metrics endpoint: `/metrics`
- Request logging middleware
- Prometheus and Grafana configuration files under `monitoring/`

## Technology Stack

- Python 3.11
- FastAPI
- SQLAlchemy 2
- PostgreSQL
- Neon PostgreSQL
- Alembic
- Pydantic
- JWT authentication
- Prometheus instrumentation
- Grafana configuration
- Pytest
- Uvicorn
- uv

## Project Structure

```text
AMRUTAM-TELEMEDICINE/
├── alembic/
│   ├── versions/
│   ├── env.py
│   ├── README
│   └── script.py.mako
├── app/
│   ├── api/
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── auth_dependencies.py
│   │   ├── consultations.py
│   │   ├── doctors.py
│   │   └── prescriptions.py
│   ├── database/
│   │   ├── database.py
│   │   └── models.py
│   ├── schemas/
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── consultation.py
│   │   ├── doctor.py
│   │   └── prescription.py
│   ├── security/
│   │   ├── jwt.py
│   │   └── password.py
│   ├── services/
│   │   ├── admin_service.py
│   │   ├── audit_service.py
│   │   ├── auth_service.py
│   │   ├── consultation_service.py
│   │   ├── doctor_service.py
│   │   └── prescription_service.py
│   ├── config.py
│   └── main.py
├── monitoring/
│   ├── amrutam-dashboard.json
│   ├── grafana-dashboards.yaml
│   ├── grafana-datasources.yaml
│   └── prometheus.yml
├── tests/
│   ├── test_api_access.py
│   ├── test_auth_security.py
│   ├── test_consultation.py
│   └── test_consultation_concurrency.py
├── .gitignore
├── .python-version
├── alembic.ini
├── create_doctor.py
├── main.py
├── pyproject.toml
├── requirements.txt
├── uv.lock
├── README.md
└── LICENSE
```

Generated folders such as `.venv/`, `.pytest_cache/`, and `__pycache__/` are intentionally omitted from this overview.

## Prerequisites

- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL database
- Git

The project has been used with a PostgreSQL database hosted on Neon.

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/AkashKhulpe5/Amrutam-Telemedicine-backend.git
cd Amrutam-Telemedicine-backend
```

### 2. Install dependencies

```bash
uv sync
```

Alternatively, install from the requirements file:

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a local `.env` file in the project root and configure the environment variables required by the application.

Use `app/config.py` to identify the required variable names.

**Never commit `.env` files, database URLs, passwords, JWT secrets, API keys, or other credentials to GitHub.**

### 4. Apply database migrations

```bash
uv run alembic upgrade head
```

Run migrations only against the database configured for your environment. Use a separate test database for integration tests that create, update, or delete database records.

### 5. Start the API server

```bash
uv run uvicorn app.main:app --reload
```

The local development server is available at:

```text
http://127.0.0.1:8000
```

## API Documentation

After starting the server, open:

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc
- **OpenAPI schema:** http://127.0.0.1:8000/openapi.json

Use Swagger UI to inspect the registered API routes, request and response schemas, and authorization requirements.

## Health and Metrics Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health/live` | Checks whether the application process is running |
| `GET /health/ready` | Checks application readiness, including database connectivity |
| `GET /metrics` | Exposes application metrics in Prometheus format |

Prometheus and Grafana configuration files are included in `monitoring/`. Their successful deployment and operation should be verified separately.

## Running Tests

Run the full test suite:

```bash
uv run pytest -v
```

Run an individual test file:

```bash
uv run pytest tests/test_consultation.py -v
```

### Latest Recorded Test Result

```text
22 passed, 1 warning
```

The test suite covers API access, authentication requirements, consultation rules, booking validation, idempotency behavior, and cancellation logic.

Some service tests use mocked database sessions. They do not independently verify real PostgreSQL locking, concurrent booking behavior, or production transaction behavior. The Starlette test-client deprecation warning observed in the latest run was non-blocking.

## Security Considerations

The application includes authentication, role-based access checks, password hashing, and protected endpoints. The database model includes an MFA-enabled field; the existence of that field alone does not establish that MFA is enforced.

Before production deployment, verify:

- Secret management and credential rotation
- HTTPS/TLS configuration
- MFA enforcement requirements
- Rate limiting and abuse protection
- Database access controls and encrypted connections
- Backup and restore procedures
- Security testing and audit-log retention

Do not use real patient information in public demonstrations, test fixtures, screenshots, or repository examples.

## Performance and Scalability

The data model includes indexes and constraints for common access patterns and data consistency. Consultation booking and cancellation use transaction logic and row-level locking in the service implementation.

The assignment's performance and availability objectives require reproducible load testing and operational measurements. The current automated test results do not establish throughput, p95 latency, or 99.95% availability.

## Monitoring and Deployment

Monitoring configuration files are stored in `monitoring/`, including Prometheus and Grafana configuration.

The application can be run locally using Uvicorn. Production infrastructure, monitoring deployment, dashboards, backup/restore procedures, disaster recovery, and deployment automation must be validated before claiming production readiness.

Docker is not required for the local development commands in this README.


## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Use this license section only if you own the code and are permitted to license it under MIT.
