import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class CreateSessionRequest(BaseModel):
    """Optional title for the session."""
    title: str | None = None


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    message: str
    context: dict | None = None


class SessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    state: dict | None
    summary: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    metadata: dict | None = Field(default=None, validation_alias="metadata_")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class ActionPayload(BaseModel):
    type: str
    payload: dict | None = None

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    message: str
    actions: list[ActionPayload] | None = None
    requires_confirmation: bool = False
    confirmation_action: dict | None = None
