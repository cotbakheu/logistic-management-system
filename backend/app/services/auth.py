from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password, verify_password
from db.models.user import User, UserRole
from schemas.auth import RegisterPayload, LoginPayload

from core.security import create_access_token


async def register_user_service(
    payload: RegisterPayload,
    session: AsyncSession,
) -> User:
    existing_user = await session.scalar(
        select(User).where(User.email == payload.email)
    )

    if existing_user:
        raise ValueError("Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.CUSTOMER,
        phone=payload.phone,
        is_active=True,
    )

    session.add(user)

    try:
        await session.commit()
        await session.refresh(user)
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError(
            "Could not register user due to a database constraint"
        ) from exc

    return user


async def login_user_service(session: AsyncSession, credentials: LoginPayload) -> dict:
    user = await session.scalar(select(User).where(User.email == credentials.email))

    if not user or not verify_password(credentials.password, user.password_hash):
        raise ValueError("Invalid email or password")

    access_token = create_access_token(user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "role": user.role.value,
        },
    }
