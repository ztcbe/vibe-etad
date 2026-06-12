"""Chat service — message CRUD, suggest-reply."""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.chat import ChatMessage
from db.models.matching import Match
from db.models.user import User
from db.models.profile import UserProfile
from common.errors import NotFoundError, ForbiddenError, ValidationError
from common.enums import MessageStatus, MessageType, MatchStatus

logger = logging.getLogger(__name__)


async def get_messages(
    db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID,
    limit: int = 50, before_id: uuid.UUID | None = None,
) -> list[ChatMessage]:
    """Get paginated message history for a match thread."""
    await _verify_match_participant(db, user_id, match_id)

    stmt = select(ChatMessage).where(ChatMessage.match_id == match_id)
    if before_id:
        # Cursor-based pagination — get messages older than before_id
        ref = await db.get(ChatMessage, before_id)
        if ref:
            stmt = stmt.where(ChatMessage.created_at < ref.created_at)
    stmt = stmt.order_by(ChatMessage.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    messages = list(result.scalars().all())
    messages.reverse()  # Return chronological order
    return messages


async def send_message(
    db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID,
    content: str, message_type: str = "text",
) -> ChatMessage:
    """Send a message in a match thread."""
    match = await _verify_match_participant(db, user_id, match_id)

    # Verify match is active
    if match.status != MatchStatus.ACTIVE:
        raise ValidationError(code="MATCH_INACTIVE", message="Cannot send messages to an inactive match")

    msg = ChatMessage(
        match_id=match_id,
        sender_user_id=user_id,
        content=content,
        message_type=MessageType(message_type) if message_type in {"text", "image"} else MessageType.TEXT,
        status=MessageStatus.SENT,
    )
    db.add(msg)

    # Update match denormalized fields
    match.last_message_at = datetime.now(timezone.utc)
    match.last_message_preview = content[:80]
    match.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(msg)
    return msg


async def mark_read(
    db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID,
    message_ids: list[uuid.UUID],
) -> None:
    """Mark messages as read."""
    await _verify_match_participant(db, user_id, match_id)

    await db.execute(
        select(ChatMessage).where(
            ChatMessage.id.in_(message_ids),
            ChatMessage.match_id == match_id,
            ChatMessage.sender_user_id != user_id,
        )
    )
    result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.id.in_(message_ids),
            ChatMessage.match_id == match_id,
            ChatMessage.sender_user_id != user_id,
        )
    )
    messages = result.scalars().all()
    for msg in messages:
        msg.status = MessageStatus.READ
    await db.commit()


async def suggest_reply(
    db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID,
    tone: str = "natural", message_id: uuid.UUID | None = None,
) -> list[str]:
    """Generate AI-suggested replies based on chat context.

    In production, this calls the LLM. For MVP, returns template suggestions.
    Per v0.2 §5.2: always 2-3 items, each ≤35 words, correct tone.
    """
    await _verify_match_participant(db, user_id, match_id)

    # Get recent messages for context
    recent = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.match_id == match_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    recent_msgs = list(recent.scalars().all())
    recent_msgs.reverse()

    # Get the other user's name
    match = await db.get(Match, match_id)
    other_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
    other_profile = await db.execute(
        select(UserProfile).where(UserProfile.user_id == other_id)
    )
    profile = other_profile.scalar_one_or_none()
    other_name = profile.display_name if profile and profile.display_name else "bạn"

    # Get last message from the other person
    last_other_msg = None
    for msg in reversed(recent_msgs):
        if msg.sender_user_id != user_id:
            last_other_msg = msg.content
            break

    # Generate tone-appropriate suggestions
    suggestions = _generate_template_suggestions(other_name, last_other_msg, tone)
    return suggestions[:3]


def _generate_template_suggestions(other_name: str, last_msg: str | None, tone: str) -> list[str]:
    """Generate contextual Vietnamese reply suggestions."""
    tone_prefixes = {
        "natural": ["Mình thấy", "Nghe có vẻ", "Bạn có vẻ"],
        "humorous": ["Haha,", "Trời ơi,", "Cười xỉu,"],
        "subtle": ["Có lẽ", "Mình nghĩ", "Cảm giác"],
        "proactive": ["Hay là", "Cuối tuần này", "Mình muốn rủ"],
        "gentle": ["Dạ,", "Cảm ơn bạn,", "Thật nhẹ nhàng,"],
        "concise": ["Ok,", "Hay!", "Đồng ý nha,"],
    }

    prefixes = tone_prefixes.get(tone, tone_prefixes["natural"])

    templates = [
        f"{prefixes[0]} {other_name} có vẻ là người thú vị đó. Kể thêm về bản thân bạn đi!",
        f"{prefixes[1]} vibe của {other_name} khá hợp gu mình. Bạn thích làm gì cuối tuần?",
        f"{prefixes[2]} {other_name} rất chân thành. Mình cũng đang tìm kiếm điều tương tự nè.",
    ]

    # If there's a last message, add a context-aware suggestion
    if last_msg:
        if "?" in last_msg:
            templates.insert(0, f"Về câu hỏi của {other_name}, mình nghĩ là...")
        elif len(last_msg) > 50:
            templates.insert(0, f"Cảm ơn {other_name} đã chia sẻ. Mình cũng có trải nghiệm tương tự!")

    return templates


async def _verify_match_participant(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> Match:
    """Verify user is a participant in the match."""
    match = await db.get(Match, match_id)
    if match is None or (match.user_a_id != user_id and match.user_b_id != user_id):
        raise ForbiddenError(code="MATCH_NOT_PARTICIPANT", message="You are not a participant in this match")
    return match
