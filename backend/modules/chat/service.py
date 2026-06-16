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
from common.events import event_bus, Event

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

    # Auto-mark unread messages from the other user as READ
    unread_ids = [
        m.id for m in messages
        if m.sender_user_id != user_id and m.status != MessageStatus.READ
    ]
    if unread_ids:
        await mark_read(db, user_id, match_id, unread_ids)

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

    # Determine recipient and emit notification event
    other_user_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
    event_bus.emit(Event("message_received", {
        "match_id": str(match_id),
        "message_id": str(msg.id),
        "sender_user_id": str(user_id),
        "recipient_user_id": str(other_user_id),
        "content_preview": content[:60],
        "content": content,
        "message_type": message_type,
    }))

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
    """Generate AI-suggested replies using ConversationCoachAgent directly.

    Bypasses the coordinator — invokes ConversationCoachAgent with match context
    to produce 2-3 personalized Vietnamese reply suggestions.
    Per v0.2 §5.2: always 2-3 items, each ≤35 words, correct tone.
    """
    await _verify_match_participant(db, user_id, match_id)

    # Get the other user's name for fallback
    match = await db.get(Match, match_id)
    other_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
    other_profile = await db.execute(
        select(UserProfile).where(UserProfile.user_id == other_id)
    )
    profile = other_profile.scalar_one_or_none()
    other_name = profile.display_name if profile and profile.display_name else "bạn"

    try:
        suggestions = await _ai_suggest_replies(db, user_id, match_id, tone)
        if suggestions and len(suggestions) >= 2:
            return suggestions[:3]
    except Exception as e:
        logger.warning(f"AI suggest_reply failed, falling back to templates: {e}")

    # Fallback to template-based suggestions
    return _fallback_template_suggestions(other_name, tone)


async def _ai_suggest_replies(
    db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID, tone: str,
) -> list[str] | None:
    """Invoke ConversationCoachAgent directly to generate AI reply suggestions."""
    from google.adk import Runner
    from google.genai.types import Content, Part

    from modules.assistant.agents import build_conversation_coach_agent
    from modules.assistant.session import get_session_service
    from modules.assistant.tools import current_db, current_user_id

    # Set contextvars for tool access
    token_db = current_db.set(db)
    token_user = current_user_id.set(str(user_id))

    try:
        agent = build_conversation_coach_agent()
        session_service = get_session_service()
        session_id = f"suggest_{match_id}_{tone}"
        adk_session = await session_service.get_session(
            app_name="zvibe_suggest",
            user_id=str(user_id),
            session_id=session_id,
        )
        if adk_session is None:
            adk_session = await session_service.create_session(
                app_name="zvibe_suggest",
                user_id=str(user_id),
                session_id=session_id,
            )

        runner = Runner(
            agent=agent,
            app_name="zvibe_suggest",
            session_service=session_service,
        )

        prompt = (
            f"Hãy gợi ý 2-3 câu trả lời bằng tiếng Việt với tone {tone} "
            f"cho cuộc trò chuyện ở match {match_id}. "
            f"Gọi tool get_match_context('{match_id}') để lấy ngữ cảnh trước. "
            f"Sau đó dựa vào ngữ cảnh để tạo câu gợi ý phù hợp. "
            f"Xuất kết quả dưới dạng danh sách, mỗi câu trên một dòng, bắt đầu bằng dấu gạch ngang (-). "
            f"Không kèm giải thích dài dòng."
        )

        response_text = ""
        async for event in runner.run_async(
            user_id=str(user_id),
            session_id=session_id,
            new_message=Content(role="user", parts=[Part(text=prompt)]),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    # Skip thinking/reasoning parts (Gemma, Qwen, DeepSeek-R1, etc.)
                    is_thought = getattr(part, 'thought', False)
                    if part.text and not is_thought:
                        response_text += part.text

        # Strip any remaining thinking XML tags (fallback safety net)
        response_text = _strip_thinking(response_text)

        # Parse suggestions from response
        suggestions = _parse_suggestions(response_text)
        return suggestions if suggestions else None

    finally:
        current_db.reset(token_db)
        current_user_id.reset(token_user)


def _parse_suggestions(text: str) -> list[str]:
    """Parse AI response into a list of suggestion strings.

    Handles common formats: dash-prefixed lines, numbered lines, or newline-separated.
    """
    lines = text.strip().split("\n")
    suggestions = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove common prefixes: "- ", "1. ", "2. ", "• ", "* "
        for prefix in ("- ", "• ", "* "):
            if line.startswith(prefix):
                line = line[len(prefix):]
                break
        else:
            # Check for numbered prefix like "1. " or "1)"
            import re
            line = re.sub(r"^\d+[.)]\s*", "", line)
        if line and len(line) >= 5:
            suggestions.append(line)
    return suggestions


def _strip_thinking(text: str) -> str:
    """Remove thinking/reasoning blocks from model output (fallback).

    Primary filtering happens in the event loop via part.thought check.
    This handles cases where the model embeds thinking as raw XML tags
    in the text stream (some Qwen/DeepSeek deployments).
    """
    import re

    for tag in ("think", "thinking", "thought"):
        text = re.sub(
            rf"<{tag}>.*?</{tag}>", "", text,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _fallback_template_suggestions(other_name: str, tone: str) -> list[str]:
    """Minimal fallback when AI is unavailable."""
    templates = {
        "natural": [
            f"Mình thấy {other_name} có vẻ thú vị đó. Kể thêm về bản thân bạn đi!",
            f"Vibe của {other_name} khá hợp gu mình nè. Bạn thích làm gì cuối tuần?",
            f"{other_name} có vẻ chân thành. Mình cũng đang tìm kiếm điều tương tự.",
        ],
        "humorous": [
            f"Haha, {other_name} làm mình cười đó. Bạn có khiếu hài hước ghê!",
            f"Trời ơi, {other_name} nói chuyện duyên dữ vậy. Bạn ở đâu ra vậy?",
            f"Cười xỉu với vibe của {other_name}. Cuối tuần đi cà phê kể chuyện đi!",
        ],
        "proactive": [
            f"Hay là cuối tuần này mình đi cà phê đi {other_name}?",
            f"Mình muốn rủ {other_name} đi xem phim. Bạn thích thể loại gì?",
            f"{other_name} ơi, mình nói chuyện hợp vibe quá. Gặp nhau thực tế nha?",
        ],
        "gentle": [
            f"Dạ, cảm ơn {other_name} đã chia sẻ. Mình rất trân trọng điều đó.",
            f"Thật nhẹ nhàng khi nói chuyện với {other_name}. Chúc bạn ngày mới vui vẻ!",
            f"Cảm ơn {other_name}. Mình hy vọng sẽ được biết thêm về bạn.",
        ],
    }
    defaults = templates.get(tone, templates["natural"])
    return defaults[:3]


async def _verify_match_participant(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> Match:
    """Verify user is a participant in the match."""
    match = await db.get(Match, match_id)
    if match is None or (match.user_a_id != user_id and match.user_b_id != user_id):
        raise ForbiddenError(code="MATCH_NOT_PARTICIPANT", message="You are not a participant in this match")
    return match
