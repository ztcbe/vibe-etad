"""ADK tool context — uses contextvars to inject DB session and user info."""
import contextvars

from sqlalchemy.ext.asyncio import AsyncSession

current_db: contextvars.ContextVar[AsyncSession | None] = contextvars.ContextVar("db", default=None)
current_user_id: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")
current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="")
