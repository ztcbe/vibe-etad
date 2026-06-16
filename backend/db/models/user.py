import uuid
from db.enum_helper import zvibe_enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from common.enums import UserRole, UserStatus


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(zvibe_enum(UserRole), default=UserRole.USER, nullable=False)
    status: Mapped[UserStatus] = mapped_column(zvibe_enum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    is_age_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    account_source: Mapped[str] = mapped_column(
        String(20), default="human", nullable=False, server_default="human"
    )
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    profile: Mapped["UserProfile"] = relationship("UserProfile", back_populates="user", uselist=False)  # noqa: F821
