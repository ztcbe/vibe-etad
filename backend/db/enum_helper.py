"""SQLAlchemy Enum helper that uses .value instead of .name for storage."""
from typing import Any, Type

from sqlalchemy import Enum as SAEnum


def zvibe_enum(enum_cls: Type[Any], **kwargs: Any) -> SAEnum:
    """Create a SQLAlchemy Enum that stores the Python enum's .value (not .name).

    Usage: role: Mapped[UserRole] = mapped_column(zvibe_enum(UserRole))
    """
    return SAEnum(enum_cls, values_callable=lambda obj: [e.value for e in obj], **kwargs)
