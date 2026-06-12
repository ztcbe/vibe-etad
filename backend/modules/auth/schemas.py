import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)
    date_of_birth: date


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None
    role: str
    status: str
    date_of_birth: date
    is_age_verified: bool
    completeness_score: int
    avatar_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
