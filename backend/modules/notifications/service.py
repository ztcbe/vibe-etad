"""Notification service — create, read, push, and event-driven notification logic."""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.notification import Notification
from db.models.assistant import AssistantSession, AssistantMessage, AssistantRole
from db.models.profile import UserProfile
from common.enums import NotificationType
from common.events import Event, event_bus
from modules.notifications.websocket import push_to_user, is_user_online
from modules.notifications.schemas import (
    NotificationResponse,
    UnreadCountResponse,
    ManualNotifyRequest,
)
from db.session import async_session

logger = logging.getLogger(__name__)


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: NotificationType,
    title: str,
    body: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: uuid.UUID | None = None,
    is_one_shot: bool = True,
    extra_data: dict | None = None,
) -> Notification | None:
    """Create a notification. If is_one_shot, skip if unread notification for same entity exists."""
    if is_one_shot and related_entity_type and related_entity_id:
        existing = await db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.related_entity_type == related_entity_type,
                Notification.related_entity_id == related_entity_id,
                Notification.is_read == False,
            )
        )
        if existing.scalar_one_or_none():
            return None  # Already have unread notification for this entity

    notif = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        is_one_shot=is_one_shot,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        extra_data=extra_data or {},
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)

    # Push via WebSocket if user is online
    await _push_notification(notif)

    return notif


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> UnreadCountResponse:
    """Get unread notification count + unread assistant messages count."""
    notif_result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
    )
    unread_notifs = notif_result.scalar() or 0

    msg_result = await db.execute(
        select(func.count(AssistantMessage.id)).where(
            AssistantMessage.user_id == user_id,
            AssistantMessage.role == AssistantRole.ASSISTANT,
            AssistantMessage.is_read == False,
        )
    )
    unread_msgs = msg_result.scalar() or 0

    return UnreadCountResponse(
        unread_notifications=unread_notifs,
        unread_assistant_messages=unread_msgs,
        total=unread_notifs + unread_msgs,
    )


async def list_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    unread_only: bool = False,
) -> list[NotificationResponse]:
    """List notifications for user, newest first."""
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
    stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    notifs = result.scalars().all()
    return [NotificationResponse.model_validate(n) for n in notifs]


async def mark_read(
    db: AsyncSession,
    user_id: uuid.UUID,
    notification_ids: list[uuid.UUID] | None = None,
) -> int:
    """Mark notifications as read. If ids is None, mark all. Returns count updated."""
    if notification_ids:
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.id.in_(notification_ids),
                Notification.is_read == False,
            )
            .values(is_read=True)
        )
    else:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def mark_assistant_messages_read(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> int:
    """Mark all unread assistant messages in a session as read."""
    stmt = (
        update(AssistantMessage)
        .where(
            AssistantMessage.session_id == session_id,
            AssistantMessage.user_id == user_id,
            AssistantMessage.role == AssistantRole.ASSISTANT,
            AssistantMessage.is_read == False,
        )
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def get_assistant_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Count unread assistant messages across all sessions."""
    result = await db.execute(
        select(func.count(AssistantMessage.id)).where(
            AssistantMessage.user_id == user_id,
            AssistantMessage.role == AssistantRole.ASSISTANT,
            AssistantMessage.is_read == False,
        )
    )
    return result.scalar() or 0


# ── Push helper ──────────────────────────────────────────────────────────────

async def _push_notification(notif: Notification) -> bool:
    """Push a notification to the user via WebSocket."""
    data = {
        "event": "notification",
        "data": {
            "id": str(notif.id),
            "type": notif.type.value if isinstance(notif.type, NotificationType) else notif.type,
            "title": notif.title,
            "body": notif.body,
            "related_entity_type": notif.related_entity_type,
            "related_entity_id": str(notif.related_entity_id) if notif.related_entity_id else None,
            "extra_data": notif.extra_data,
            "created_at": notif.created_at.isoformat() if notif.created_at else None,
        },
    }
    return await push_to_user(notif.user_id, data)


# ── Proactive assistant message ──────────────────────────────────────────────

async def _create_proactive_assistant_message(
    db: AsyncSession, user_id: uuid.UUID, message: str, metadata: dict | None = None
) -> AssistantMessage | None:
    """Insert a proactive assistant message into the user's latest session.

    If no session exists for the user, one is auto-created so the proactive
    message is always delivered.
    """
    result = await db.execute(
        select(AssistantSession)
        .where(AssistantSession.user_id == user_id)
        .order_by(AssistantSession.updated_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if session is None:
        # Auto-create a session so the proactive message is always delivered
        session = AssistantSession(
            user_id=user_id,
            title="Trợ lý hẹn hò",
            state={},
        )
        db.add(session)
        await db.flush()

    msg = AssistantMessage(
        session_id=session.id,
        user_id=user_id,
        role=AssistantRole.ASSISTANT,
        content=message,
        metadata_=metadata or {},
        is_read=False,
    )
    db.add(msg)
    await db.commit()
    return msg


# ── Event handlers ───────────────────────────────────────────────────────────

async def _on_like_received(event: Event) -> None:
    """Handle like_received event — notify the recipient."""
    payload = event.payload
    from_user_id = uuid.UUID(payload["from_user_id"])
    to_user_id = uuid.UUID(payload["to_user_id"])

    async with async_session() as db:
        try:
            # Look up the liker's display name
            profile_result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == from_user_id)
            )
            from_profile = profile_result.scalar_one_or_none()
            display_name = from_profile.display_name if from_profile else "ai đó"

            notif = await create_notification(
                db=db,
                user_id=to_user_id,
                type=NotificationType.LIKE_RECEIVED,
                title="Có người thích bạn!",
                body=f"{display_name} vừa thích bạn. Hãy xem hồ sơ và quyết định nhé.",
                related_entity_type="like",
                related_entity_id=from_user_id,
                is_one_shot=True,
                extra_data={"display_name": display_name, "from_user_id": str(from_user_id)},
            )
            if notif:
                await _create_proactive_assistant_message(
                    db=db,
                    user_id=to_user_id,
                    message=f"💖 {display_name} vừa thích bạn! Bạn có muốn xem hồ sơ của họ và like lại không?",
                    metadata={"notification_type": "like_received", "from_user_id": str(from_user_id)},
                )
                # Push proactive message via WS
                await push_to_user(to_user_id, {
                    "event": "assistant_message",
                    "data": {
                        "role": "assistant",
                        "content": f"💖 {display_name} vừa thích bạn! Bạn có muốn xem hồ sơ của họ và like lại không?",
                        "metadata": {"notification_type": "like_received"},
                    },
                })
        except Exception:
            logger.exception("Error handling like_received")
            await db.rollback()


async def _on_match_created(event: Event) -> None:
    """Handle match_created event — notify both users."""
    payload = event.payload
    user_a_id = uuid.UUID(payload["user_a_id"])
    user_b_id = uuid.UUID(payload["user_b_id"])
    match_id = uuid.UUID(payload["match_id"])

    async with async_session() as db:
        try:
            # Look up both users' display names from DB
            profiles_result = await db.execute(
                select(UserProfile).where(
                    UserProfile.user_id.in_([user_a_id, user_b_id])
                )
            )
            profiles = {p.user_id: p for p in profiles_result.scalars().all()}
            name_a = profiles.get(user_a_id, None)
            name_a = name_a.display_name if name_a else "ai đó"
            name_b = profiles.get(user_b_id, None)
            name_b = name_b.display_name if name_b else "ai đó"

            # Notify user B (shows user A's name)
            notif_b = await create_notification(
                db=db,
                user_id=user_b_id,
                type=NotificationType.MATCH_CREATED,
                title="Match mới! 💞",
                body=f"Bạn và {name_a} vừa match! Hãy bắt đầu trò chuyện.",
                related_entity_type="match",
                related_entity_id=match_id,
                is_one_shot=True,
                extra_data={"match_id": str(match_id), "display_name": name_a},
            )
            if notif_b:
                await _create_proactive_assistant_message(
                    db=db,
                    user_id=user_b_id,
                    message=f"💞 Bạn vừa match với {name_a}! Chúc mừng bạn! Hãy vào mục Matches để bắt đầu trò chuyện nhé.",
                    metadata={"notification_type": "match_created", "match_id": str(match_id)},
                )
                await push_to_user(user_b_id, {
                    "event": "assistant_message",
                    "data": {
                        "role": "assistant",
                        "content": f"💞 Bạn vừa match với {name_a}! Chúc mừng! Hãy vào mục Matches để bắt đầu trò chuyện.",
                        "metadata": {"notification_type": "match_created"},
                    },
                })

            # Notify user A (shows user B's name)
            notif_a = await create_notification(
                db=db,
                user_id=user_a_id,
                type=NotificationType.MATCH_CREATED,
                title="Match mới! 💞",
                body=f"Bạn và {name_b} vừa match! Hãy bắt đầu trò chuyện.",
                related_entity_type="match",
                related_entity_id=match_id,
                is_one_shot=True,
                extra_data={"match_id": str(match_id), "display_name": name_b},
            )
            if notif_a:
                await _create_proactive_assistant_message(
                    db=db,
                    user_id=user_a_id,
                    message=f"💞 Bạn vừa match với {name_b}! Chúc mừng bạn! Hãy vào mục Matches để bắt đầu trò chuyện nhé.",
                    metadata={"notification_type": "match_created", "match_id": str(match_id)},
                )
                await push_to_user(user_a_id, {
                    "event": "assistant_message",
                    "data": {
                        "role": "assistant",
                        "content": f"💞 Bạn vừa match với {name_b}! Chúc mừng! Hãy vào mục Matches để bắt đầu trò chuyện.",
                        "metadata": {"notification_type": "match_created"},
                    },
                })
        except Exception:
            logger.exception("Error handling match_created")
            await db.rollback()


async def _on_message_received(event: Event) -> None:
    """Handle message_received event — notify the recipient."""
    payload = event.payload
    sender_id = uuid.UUID(payload["sender_user_id"])
    recipient_id = uuid.UUID(payload["recipient_user_id"])
    content_preview = payload.get("content_preview", "")
    match_id = uuid.UUID(payload["match_id"])

    async with async_session() as db:
        try:
            # Look up sender's display name
            profile_result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == sender_id)
            )
            sender_profile = profile_result.scalar_one_or_none()
            sender_name = sender_profile.display_name if sender_profile else "ai đó"

            # Don't create a Notification for chat messages — the unread count
            # is computed from ChatMessage.status by the matches API (match badge).
            # Instead push a WS event to update the match badge in real-time.
            await push_to_user(recipient_id, {
                "event": "unread_message",
                "data": {
                    "match_id": str(match_id),
                    "sender_name": sender_name,
                    "preview": content_preview,
                },
            })
        except Exception:
            logger.exception("Error handling message_received")
            await db.rollback()


async def _on_match_unavailable(event: Event) -> None:
    """Handle match_unavailable event — notify both users."""
    payload = event.payload
    user_a_id = uuid.UUID(payload["user_a_id"])
    user_b_id = uuid.UUID(payload["user_b_id"])
    match_id = uuid.UUID(payload["match_id"])
    reason = payload.get("reason", "unmatched")

    async with async_session() as db:
        try:
            for uid in [user_a_id, user_b_id]:
                await create_notification(
                    db=db,
                    user_id=uid,
                    type=NotificationType.MATCH_UNAVAILABLE,
                    title="Match không còn khả dụng",
                    body=f"Match của bạn không còn khả dụng (lý do: {reason}).",
                    related_entity_type="match",
                    related_entity_id=match_id,
                    is_one_shot=True,
                    extra_data={"match_id": str(match_id), "reason": reason},
                )
        except Exception:
            logger.exception("Error handling match_unavailable")
            await db.rollback()


# ── Register handlers ────────────────────────────────────────────────────────

def register_event_handlers() -> None:
    """Wire event_bus → notification handlers. Called during app startup."""
    event_bus.on("like_received", _on_like_received)
    event_bus.on("match_created", _on_match_created)
    event_bus.on("message_received", _on_message_received)
    event_bus.on("match_unavailable", _on_match_unavailable)
    logger.info("Notification event handlers registered")
