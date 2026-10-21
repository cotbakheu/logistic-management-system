from sqlmodel import insert, select

from db.connection import SessionDep

# Schemas
from schemas.user import User, UserRole

# Core
from core.security import hash_password


def create_user(session: SessionDep, user: User):
    password_hash = hash_password(user.password)
    db_user = User(
        name=user.name,
        password_hash=password_hash,
        role=UserRole.COURIER,
        phone=user.phone,
        email=user.email,
        is_active=True,
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user
