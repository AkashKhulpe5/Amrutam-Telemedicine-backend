from sqlalchemy import select

from app.database.database import SessionLocal
from app.database.models import User, UserRole
from app.security.password import hash_password


DOCTOR_EMAIL = "doctor@test.com"
DOCTOR_PASSWORD = "Doctor@12345"


def create_doctor_user():
    db = SessionLocal()

    try:
        existing_user = db.scalar(
            select(User).where(User.email == DOCTOR_EMAIL)
        )

        if existing_user:
            print("Doctor user already exists.")
            print(f"Email: {existing_user.email}")
            print(f"Role: {existing_user.role.value}")
            return

        doctor = User(
            email=DOCTOR_EMAIL,
            password_hash=hash_password(DOCTOR_PASSWORD),
            role=UserRole.DOCTOR,
        )

        db.add(doctor)
        db.commit()
        db.refresh(doctor)

        print("Doctor user created successfully.")
        print(f"User ID: {doctor.id}")
        print(f"Email: {doctor.email}")
        print(f"Role: {doctor.role.value}")

    finally:
        db.close()


if __name__ == "__main__":
    create_doctor_user()