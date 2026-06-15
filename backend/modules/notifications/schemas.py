"""Notification schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    body: str | None
    is_read: bool
    is_one_shot: bool
    related_entity_type: str | None
    related_entity_id: uuid.UUID | None
    extra_data: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    unread_notifications: int
    unread_assistant_messages: int
    total: int


class ManualNotifyRequest(BaseModel):
    user_id: uuid.UUID
    title: str
    body: str | None = None
    type: str = "system"
    extra_data: dict | None = None


class MarkReadRequest(BaseModel):
    notification_ids: list[uuid.UUID] | None = None  # None = mark all
