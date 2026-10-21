from pydantic import BaseModel


class LoginPayload(BaseModel):
    username: str
    password: str


class RegisterPayload(BaseModel):
    name: str
    password: str
    email: str
    phone: str
