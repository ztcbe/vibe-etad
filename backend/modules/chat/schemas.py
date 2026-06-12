"""Chat module schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    content: str
    message_type: str = "text"  # text, image


class MessageResponse(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    sender_user_id: uuid.UUID
    content: str
    message_type: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SuggestReplyRequest(BaseModel):
    message_id: uuid.UUID | None = None
    tone: str = "natural"  # natural, humorous, subtle, proactive, gentle, concise


class SuggestReplyResponse(BaseModel):
    suggestions: list[str]


# ── WebSocket payloads ──

class WsSendMessage(BaseModel):
    action: str = "send_message"
    content: str
    message_type: str = "text"


class WsMarkRead(BaseModel):
    action: str = "mark_read"
    message_ids: list[uuid.UUID]


class WsTyping(BaseModel):
    action: str = "typing_started"  # or typing_stopped
