import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.consultations import router as consultations_router
from app.api.doctors import router as doctors_router
from app.api.prescriptions import router as prescriptions_router
from app.config import settings
from app.database.database import engine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("amrutam.api")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Production-oriented telemedicine backend for Amrutam "
        "with authentication, RBAC, doctor availability, "
        "consultation booking, prescriptions, idempotent writes, "
        "admin audit logs, analytics, and Prometheus metrics."
    ),
)

app.include_router(auth_router)
app.include_router(doctors_router)
app.include_router(consultations_router)
app.include_router(prescriptions_router)
app.include_router(admin_router)


# Collect HTTP request metrics and expose them at /metrics.
Instrumentator().instrument(app).expose(
    app,
    endpoint="/metrics",
    include_in_schema=False,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "%s %s | status=%s | duration_ms=%.2f",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )


@app.get("/health/live", tags=["Health"], summary="Liveness check")
def liveness():
    """
    Lightweight health check used by load balancers/orchestrators.
    It does not depend on the database.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": "1.0.0",
    }


@app.get("/health/ready", tags=["Health"], summary="Readiness check")
def readiness():
    """
    Readiness check verifies that the application can reach PostgreSQL.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except SQLAlchemyError:
        logger.exception("Database readiness check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable"},
        )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """
    Prevent raw database errors from being exposed to clients.
    """
    logger.exception("Database error while handling request")

    return JSONResponse(
        status_code=500,
        content={"detail": "A database error occurred."},
    )