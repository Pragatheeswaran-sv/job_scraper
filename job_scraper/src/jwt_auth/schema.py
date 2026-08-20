from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class LoginRequest(BaseModel):
    email_address: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str

class APIResponse(BaseModel, Generic[T]):
    status_code: int
    message: str
    data: T

class RefreshTokenRequest(BaseModel):
    refresh_token: str