from fastapi import APIRouter, HTTPException, status

from db.connection import SessionDep

# Schemas
from schemas.auth import RegisterPayload

# Services
from services.user import create_user

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)


@router.post("/login")
async def login():
    return {"message": "Login successful"}


@router.post("/courier/register")
async def register(session: SessionDep, payload: RegisterPayload):
    try:
        data = create_user(session, payload)
        return {"message": "Register successful", "data": data}
    except Exception as e:
        print(f"Register failed: {str(e)}")
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Register failed: {str(e)}",
        )
