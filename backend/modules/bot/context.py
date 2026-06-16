"""Bot context helper — fetch match context for bot reply generation."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User
from db.models.profile import UserProfile
from db.models.matching import Match
from db.models.chat import ChatMessage


def _calc_age(dob) -> int | None:
    if not dob:
        return None
    today = datetime.now(timezone.utc).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


async def get_match_context_for_bot(
    db: AsyncSession, bot_user_id: uuid.UUID, match_id: uuid.UUID,
) -> dict:
    """Fetch chat history + other user's profile for bot to generate a reply.

    Returns a dict with chat_history and other_user profile.
    """
    match = await db.get(Match, match_id)
    if not match:
        return {"error": "Match not found"}

    other_id = match.user_b_id if match.user_a_id == bot_user_id else match.user_a_id

    # Get other user's public profile
    other_user = await db.get(User, other_id)
    other_profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == other_id)
    )
    other_profile = other_profile_result.scalar_one_or_none()

    # Get recent chat messages (last 10, chronological order)
    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.match_id == match_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    chat_messages = messages_result.scalars().all()[::-1]  # reverse to chronological

    return {
        "match_id": str(match_id),
        "other_user": {
            "user_id": str(other_id),
            "display_name": other_profile.display_name if other_profile else "ai đó",
            "age": _calc_age(other_user.date_of_birth) if other_user and other_user.date_of_birth else None,
            "city": other_profile.city if other_profile else None,
            "dating_goal": other_profile.dating_goal.value if other_profile and other_profile.dating_goal else None,
        },
        "chat_history": [
            {
                "sender_user_id": str(msg.sender_user_id),
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in chat_messages
        ],
    }
