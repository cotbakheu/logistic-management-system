from pydantic import BaseModel


class LoginPayload(BaseModel):
    email: str
    password: str


class RegisterPayload(BaseModel):
    name: str
    password: str
    email: str
    phone: str
