from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.security.jwt import create_access_token, create_refresh_token
from app.security.password import hash_password, verify_password
from app.services.audit_service import AuditService


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    def register(
        self,
        data: RegisterRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        existing_user = self.db.scalar(
            select(User).where(User.email == data.email)
        )

        if existing_user:
            self.audit_service.log_event(
                action="USER_REGISTRATION_FAILED",
                resource_type="USER",
                ip_address=ip_address,
                user_agent=user_agent,
                event_metadata={
                    "reason": "email_already_registered",
                },
            )
            self.db.commit()

            raise ValueError("Email is already registered")

        user = User(
            email=data.email,
            phone=data.phone,
            password_hash=hash_password(data.password),
        )

        self.db.add(user)
        self.db.flush()

        self.audit_service.log_event(
            action="USER_REGISTERED",
            resource_type="USER",
            actor_user_id=user.id,
            resource_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata={
                "role": user.role.value,
            },
        )

        self.db.commit()
        self.db.refresh(user)

        return user

    def login(
        self,
        data: LoginRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        user = self.db.scalar(
            select(User).where(User.email == data.email)
        )

        if not user or not verify_password(
            data.password,
            user.password_hash,
        ):
            self.audit_service.log_event(
                action="LOGIN_FAILED",
                resource_type="AUTHENTICATION",
                ip_address=ip_address,
                user_agent=user_agent,
                event_metadata={
                    "reason": "invalid_email_or_password",
                },
            )
            self.db.commit()

            raise ValueError("Invalid email or password")

        if not user.is_active:
            self.audit_service.log_event(
                action="LOGIN_FAILED",
                resource_type="AUTHENTICATION",
                actor_user_id=user.id,
                resource_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                event_metadata={
                    "reason": "inactive_account",
                },
            )
            self.db.commit()

            raise ValueError("User account is inactive")

        access_token = create_access_token(
            user_id=str(user.id),
            role=user.role.value,
        )

        refresh_token = create_refresh_token(
            user_id=str(user.id),
        )

        self.audit_service.log_event(
            action="LOGIN_SUCCESS",
            resource_type="AUTHENTICATION",
            actor_user_id=user.id,
            resource_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata={
                "role": user.role.value,
            },
        )

        self.db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }