"""Shared ADK session service for zvibe.

Uses DatabaseSessionService for persistent session storage (PostgreSQL via asyncpg).
Sessions survive server restarts and are shared across all workers.

Usage:
    from modules.assistant.session import get_session_service, init_session_service, shutdown_session_service

    # At startup:
    await init_session_service(settings.DATABASE_URL)

    # In request handlers:
    session_service = get_session_service()
    session = await session_service.get_session(app_name="zvibe", user_id=uid, session_id=sid)

    # At shutdown:
    await shutdown_session_service()
"""
import logging

from google.adk.sessions import DatabaseSessionService

logger = logging.getLogger(__name__)

_session_service: DatabaseSessionService | None = None


async def init_session_service(db_url: str) -> DatabaseSessionService:
    """Initialize the shared DatabaseSessionService.

    Call once at application startup. Tables are auto-created by ADK.

    Eagerly triggers table creation (via a no-op get_session call) so that
    session tables (sessions, events, app_states, user_states) are guaranteed
    to exist before the first chat request. This prevents lazy-creation race
    conditions that can cause silent conversation history loss.

    Args:
        db_url: Async SQLAlchemy database URL (e.g. postgresql+asyncpg://...).

    Returns:
        The initialized DatabaseSessionService instance.
    """
    global _session_service
    if _session_service is not None:
        logger.warning("Session service already initialized, closing old instance")
        await _session_service.close()

    logger.info("Initializing DatabaseSessionService with db_url: %s", db_url)
    _session_service = DatabaseSessionService(db_url=db_url)

    # Eagerly create tables to avoid lazy-creation races on first request.
    # A get_session call with a non-existent session triggers _prepare_tables
    # which creates all ADK tables (sessions, events, app_states, user_states).
    try:
        await _session_service.get_session(
            app_name="zvibe",
            user_id="__init__",
            session_id="__init__",
        )
        logger.info("DatabaseSessionService tables ready")
    except Exception:
        logger.exception("Failed to initialize ADK session tables")
        raise

    return _session_service


async def shutdown_session_service() -> None:
    """Close the shared session service and release connections."""
    global _session_service
    if _session_service is not None:
        await _session_service.close()
        _session_service = None
        logger.info("DatabaseSessionService closed")


def get_session_service() -> DatabaseSessionService:
    """Get the shared session service instance.

    Raises RuntimeError if not yet initialized.
    """
    if _session_service is None:
        raise RuntimeError(
            "Session service not initialized. Call init_session_service() at startup."
        )
    return _session_service
