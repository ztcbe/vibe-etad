"""Matching module schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=10)
    filters: dict | None = None


class CandidateCard(BaseModel):
    type: str = "candidate"
    candidate_user_id: uuid.UUID
    display_name: str | None
    age: int | None
    city: str | None
    avatar_url: str | None = None
    dating_goal: str | None
    score: int
    score_tier: str  # high, medium, low
    reasons: list[str] = []
    considerations: list[str] = []
    reason_codes: list[str] = []
    like_status: str = "none"  # none, liked, passed


class MatchProfile(BaseModel):
    user_id: uuid.UUID
    display_name: str | None
    age: int | None
    avatar_url: str | None = None


class LastMessage(BaseModel):
    content: str
    created_at: datetime
    sender_user_id: uuid.UUID


class MatchedItem(BaseModel):
    match_id: uuid.UUID
    user: MatchProfile
    last_message: LastMessage | None = None
    unread_count: int = 0
    matched_at: datetime


class PendingItem(BaseModel):
    user: MatchProfile
    liked_at: datetime


class MatchesResponse(BaseModel):
    matched: list[MatchedItem] = []
    pending_sent: list[PendingItem] = []
    pending_received: list[PendingItem] = []


class MutualMatchResult(BaseModel):
    match_id: uuid.UUID
    user: MatchProfile
    is_mutual: bool = False
