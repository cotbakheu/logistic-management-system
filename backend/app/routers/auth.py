from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from db.session import SessionDep

# Models
from db.models.user import User

# Schemas
from schemas.auth import RegisterPayload

# Services
from services.auth import register_user_service

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(session: SessionDep, payload: RegisterPayload):
    try:
        user: User = await register_user_service(
            payload,
            session,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return {
        "status": "success",
        "message": "User registered successfully",
        "data": user,
    }
