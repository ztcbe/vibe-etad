"""Bot ADK tools — tool functions for BotAgent to use via FunctionTool.

These tools read `current_db` and `current_user_id` from contextvars
(see modules/assistant/tools/__init__.py), same pattern as assistant tools.
"""
import uuid

from sqlalchemy import select

from db.models.profile import UserProfile
from modules.bot.context import get_match_context_for_bot


async def get_my_bot_profile() -> dict:
    """Get the bot's own dating profile. Returns public-facing profile fields:
    display_name, gender, city, dating_goal, personality_traits, hobbies,
    communication_style, bio.
    """
    from modules.assistant.tools import current_db, current_user_id

    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    bot_uid = uuid.UUID(user_id_str)
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == bot_uid)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return {"error": "Bot profile not found"}

    return {
        "display_name": profile.display_name,
        "gender": profile.gender,
        "city": profile.city,
        "dating_goal": profile.dating_goal.value if profile.dating_goal else None,
        "personality_traits": profile.personality_traits or [],
        "hobbies": profile.hobbies or [],
        "communication_style": profile.communication_style,
        "bio": profile.bio,
    }


async def get_bot_match_context(match_id: str) -> dict:
    """Get match context for generating a reply: recent chat history and
    the other user's simplified profile.

    Returns chat_history (last 10 messages with is_me/is_them labels)
    and other_user info (display_name, age, city).
    """
    from modules.assistant.tools import current_db, current_user_id

    db = current_db.get()
    bot_user_id_str = current_user_id.get()
    if not db or not bot_user_id_str:
        return {"error": "No session context available"}

    raw = await get_match_context_for_bot(
        db, uuid.UUID(bot_user_id_str), uuid.UUID(match_id)
    )
    if "error" in raw:
        return raw

    # Convert to agent-friendly format: label messages as is_me/is_them
    chat_history = []
    for msg in raw.get("chat_history", []):
        chat_history.append({
            "is_me": msg["sender_user_id"] == bot_user_id_str,
            "content": msg["content"],
        })

    return {
        "match_id": raw["match_id"],
        "other_user": raw["other_user"],
        "chat_history": chat_history,
    }
