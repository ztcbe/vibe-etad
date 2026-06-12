import uuid
from db.enum_helper import zvibe_enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from common.enums import DatingGoal, VisibilityStatus

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    gender: Mapped[str | None] = mapped_column(String(50))
    interested_in: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(100))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    dating_goal: Mapped[DatingGoal | None] = mapped_column(zvibe_enum(DatingGoal))
    relationship_status: Mapped[str | None] = mapped_column(String(50))
    bio: Mapped[str | None] = mapped_column(Text)
    personality_traits: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    hobbies: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    values: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    lifestyle: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    communication_style: Mapped[str | None] = mapped_column(String(100))
    deal_breakers: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    preferences: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    public_summary: Mapped[str | None] = mapped_column(Text)
    private_summary: Mapped[str | None] = mapped_column(Text)
    matching_summary: Mapped[str | None] = mapped_column(Text)
    completeness_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visibility_status: Mapped[VisibilityStatus] = mapped_column(zvibe_enum(VisibilityStatus), default=VisibilityStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="profile")  # noqa: F821


class ProfileEmbedding(Base):
    __tablename__ = "profile_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding = mapped_column(Vector(1536) if Vector else "vector", nullable=True)  # type: ignore
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    source_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
