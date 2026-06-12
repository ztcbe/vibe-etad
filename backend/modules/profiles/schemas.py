import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    gender: str | None = None
    interested_in: str | None = None
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    dating_goal: str | None = None
    relationship_status: str | None = None
    bio: str | None = None
    personality_traits: list | dict | None = None
    hobbies: list | dict | None = None
    values: dict | None = None
    lifestyle: dict | None = None
    communication_style: str | None = None
    deal_breakers: dict | None = None
    preferences: dict | None = None
    avatar_url: str | None = None
    public_summary: str | None = None
    visibility_status: str | None = None


class ProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str | None
    gender: str | None
    interested_in: str | None
    city: str | None
    lat: float | None
    lng: float | None
    dating_goal: str | None
    relationship_status: str | None
    bio: str | None
    personality_traits: list | dict | None
    hobbies: list | dict | None
    values: dict | None
    lifestyle: dict | None
    communication_style: str | None
    deal_breakers: dict | None
    preferences: dict | None
    avatar_url: str | None
    public_summary: str | None
    completeness_score: int
    visibility_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompletenessBreakdown(BaseModel):
    basic_info: dict  # {"score": int, "max": int}
    dating_goal: dict
    personality_hobbies: dict
    preferences: dict
    bio_summary: dict


class CompletenessResponse(BaseModel):
    completeness_score: int
    breakdown: CompletenessBreakdown
    missing_fields: list[str]


class PublicProfileResponse(BaseModel):
    user_id: uuid.UUID
    display_name: str | None
    age: int | None
    city: str | None
    avatar_url: str | None
    public_summary: str | None
    dating_goal: str | None
    top_hobbies: list[str]

    model_config = {"from_attributes": True}
