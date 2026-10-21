from datetime import datetime

from sqlmodel import Field, SQLModel, Column, DateTime, func

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    COURIER = "COURIER"
    CUSTOMER = "CUSTOMER"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    password_hash: str
    role: UserRole = Field(index=True)
    phone: str | None = None
    email: str = Field(index=True, unique=True)
    is_active: bool = True
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )

    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
