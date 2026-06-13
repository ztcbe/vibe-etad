"""Notification tools — check pending events the assistant should surface."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User
from db.models.profile import UserProfile
from db.models.matching import Like, Match
from db.models.chat import ChatMessage
from modules.assistant.tools import current_db, current_user_id
from common.enums import LikeStatus, MatchStatus


async def get_notifications(
    shown_like_user_ids: set[str] | None = None,
    shown_match_ids: set[str] | None = None,
    shown_unread_match_ids: set[str] | None = None,
) -> dict:
    """Check for pending notifications the assistant should surface to the user.

    Returns counts and details for:
    - Pending likes received (someone liked you, need to respond)
    - Unread messages from matched users
    - New matches (recent mutual matches)

    Already-shown notification IDs are filtered out so the assistant
    never repeats the same notification.

    Call this at conversation start or when user asks about notifications.
    """
    db: AsyncSession | None = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    shown_like_user_ids = shown_like_user_ids or set()
    shown_match_ids = shown_match_ids or set()
    shown_unread_match_ids = shown_unread_match_ids or set()

    user_id = uuid.UUID(user_id_str)

    notifications = {
        "pending_likes": [],
        "unread_messages": [],
        "new_matches": [],
        "has_notifications": False,
        "shown_ids": {
            "like_user_ids": [],
            "match_ids": [],
            "unread_match_ids": [],
        },
    }

    # Track IDs that will be shown in this response (to persist back to session state)
    new_shown_like_user_ids = set()
    new_shown_match_ids = set()
    new_shown_unread_match_ids = set()

    # 1. Pending likes received — someone liked this user
    received_result = await db.execute(
        select(Like, User, UserProfile)
        .join(User, User.id == Like.from_user_id)
        .join(UserProfile, UserProfile.user_id == User.id)
        .where(
            Like.to_user_id == user_id,
            Like.status == LikeStatus.ACTIVE,
        )
        .order_by(Like.created_at.desc())
        .limit(5)
    )
    for like, user, profile in received_result:
        user_id_str = str(user.id)
        # Skip if already shown this like notification
        if user_id_str in shown_like_user_ids:
            continue
        # Check not already matched (skip if matched)
        matched_result = await db.execute(
            select(Match).where(
                Match.status == MatchStatus.ACTIVE,
                (
                    ((Match.user_a_id == user_id) & (Match.user_b_id == user.id)) |
                    ((Match.user_b_id == user_id) & (Match.user_a_id == user.id))
                ),
            )
        )
        if matched_result.scalar_one_or_none():
            continue

        notifications["pending_likes"].append({
            "user_id": user_id_str,
            "display_name": profile.display_name if profile else "ai đó",
            "age": _calc_age(user.date_of_birth) if user.date_of_birth else None,
            "liked_at": like.created_at.isoformat() if like.created_at else None,
        })
        new_shown_like_user_ids.add(user_id_str)

    # 2. Unread messages from matched users
    matches_result = await db.execute(
        select(Match).where(
            Match.status == MatchStatus.ACTIVE,
            (Match.user_a_id == user_id) | (Match.user_b_id == user_id),
        )
    )
    matches = list(matches_result.scalars().all())
    for match in matches:
        unread_result = await db.execute(
            select(func.count(ChatMessage.id)).where(
                ChatMessage.match_id == match.id,
                ChatMessage.sender_user_id != user_id,
                ChatMessage.status != "read",
            )
        )
        match_id_str = str(match.id)
        unread_count = unread_result.scalar() or 0
        if unread_count > 0:
            # Skip if this unread notification was already shown
            if match_id_str in shown_unread_match_ids:
                continue
            other_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
            other_profile = await db.execute(
                select(UserProfile).where(UserProfile.user_id == other_id)
            )
            profile = other_profile.scalar_one_or_none()
            # Get last message preview
            last_msg = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.match_id == match.id)
                .order_by(ChatMessage.created_at.desc())
                .limit(1)
            )
            last_msg_row = last_msg.scalar_one_or_none()
            notifications["unread_messages"].append({
                "match_id": match_id_str,
                "from_user_id": str(other_id),
                "display_name": profile.display_name if profile else "ai đó",
                "unread_count": unread_count,
                "last_message_preview": last_msg_row.content[:60] if last_msg_row else "",
            })
            new_shown_unread_match_ids.add(match_id_str)

    # 3. New matches (matched in last 24h)
    recent_cutoff = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    for match in matches:
        match_id_str = str(match.id)
        if match.created_at and match.created_at >= recent_cutoff:
            # Skip if this match notification was already shown
            if match_id_str in shown_match_ids:
                continue
            other_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
            other_profile = await db.execute(
                select(UserProfile).where(UserProfile.user_id == other_id)
            )
            profile = other_profile.scalar_one_or_none()
            notifications["new_matches"].append({
                "match_id": match_id_str,
                "user_id": str(other_id),
                "display_name": profile.display_name if profile else "ai đó",
                "matched_at": match.created_at.isoformat(),
            })
            new_shown_match_ids.add(match_id_str)

    notifications["has_notifications"] = bool(
        notifications["pending_likes"] or
        notifications["unread_messages"] or
        notifications["new_matches"]
    )

    # Return the IDs that were shown in this call so the caller can persist them
    notifications["shown_ids"]["like_user_ids"] = list(new_shown_like_user_ids)
    notifications["shown_ids"]["match_ids"] = list(new_shown_match_ids)
    notifications["shown_ids"]["unread_match_ids"] = list(new_shown_unread_match_ids)

    return notifications


def _calc_age(dob) -> int | None:
    """Calculate age from date of birth."""
    if not dob:
        return None
    today = datetime.now(timezone.utc).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
