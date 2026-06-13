"""Matching tools for the AI assistant — reads DB/user from contextvars."""
import json
import re
import unicodedata
import uuid

from sqlalchemy import select, or_

from db.models.matching import Like, Match
from db.models.profile import UserProfile
from db.models.user import User as UserModel
from common.enums import LikeStatus, MatchStatus
from modules.assistant.tools import current_db, current_user_id
from modules.matching import service as matching_service


def _normalize_vn(text: str) -> str:
    """Strip Vietnamese accents, lowercase. 'Khánh' → 'khanh'."""
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.lower().strip()


def _fuzzy_match_name(query: str, candidates: list[dict]) -> list[dict]:
    """Fuzzy match a name against a list of candidate dicts (each has 'display_name').

    Tries in order:
    1. Exact case-insensitive match
    2. Normalized (no-accent) match
    3. Partial normalized match (query is substring)

    Returns matching candidates (best matches first).
    """
    q = query.strip()
    q_norm = _normalize_vn(q)

    exact = [c for c in candidates if c.get('display_name', '').strip().lower() == q.lower()]
    if exact:
        return exact

    norm_matches = [c for c in candidates if _normalize_vn(c.get('display_name', '')) == q_norm]
    if norm_matches:
        return norm_matches

    partial = [c for c in candidates if q_norm in _normalize_vn(c.get('display_name', ''))]
    return partial


async def search_candidates(limit: int = 5) -> dict:
    """Search for compatible dating candidates for the current user.

    Args:
        limit: Maximum number of candidates to return (1-10, default 5).

    Returns:
        List of candidate cards with compatibility scores, reasons, and considerations.
    """
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    cards = await matching_service.search_candidates(db, uuid.UUID(user_id_str), limit)
    return {
        "total": len(cards),
        "candidates": cards,
    }


async def like_candidate(candidate_user_id: str) -> dict:
    """Like a candidate. If mutual (they already liked you), creates a match automatically.

    Args:
        candidate_user_id: The UUID of the candidate to like.

    Returns:
        Result with match info if mutual, or just like confirmation.
    """
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    result = await matching_service.like_candidate(
        db, uuid.UUID(user_id_str), uuid.UUID(candidate_user_id)
    )
    if result["is_mutual"]:
        return {
            "message": "🎉 Chúc mừng! Cả hai đã thích nhau. Bạn có thể bắt đầu chat ngay!",
            "match_id": str(result["match_id"]),
            "matched_user": result["user"],
            "is_mutual": True,
        }
    return {
        "message": "Đã gửi lời thích! Khi người ấy thích lại, hai bạn sẽ được match.",
        "is_mutual": False,
    }


async def pass_candidate(candidate_user_id: str) -> dict:
    """Skip/pass a candidate — they won't appear in future recommendations.

    Args:
        candidate_user_id: The UUID of the candidate to pass.
    """
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    await matching_service.pass_candidate(db, uuid.UUID(user_id_str), uuid.UUID(candidate_user_id))
    return {"message": "Đã bỏ qua. Mình sẽ tìm người khác phù hợp hơn cho bạn!"}


async def list_my_matches() -> dict:
    """List all matches for the current user: matched (mutual) + pending.

    Returns:
        Dict with matched, pending_sent, and pending_received lists.
    """
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    result = await matching_service.list_matches(db, uuid.UUID(user_id_str))
    return result


async def list_matched_profiles() -> dict:
    """List all matched users with basic profile info for the current user.

    Use this as a LOOKUP TABLE when the user mentions someone by name but
    find_user_by_name or check_relationship_status returns not_found.
    The user may have mistyped the name or used a nickname. Present the
    list to the user and ask which person they meant.

    Also use this BEFORE get_matched_user_profile when the exact name is
    uncertain — search through this list to find the right person.

    Returns:
        Dict with 'matched' list of {user_id, display_name, age, city, dating_goal, match_id}.
    """
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    current_uid = uuid.UUID(user_id_str)

    # Get active matches
    match_result = await db.execute(
        select(Match).where(
            or_(Match.user_a_id == current_uid, Match.user_b_id == current_uid),
            Match.status == MatchStatus.ACTIVE,
        ).order_by(Match.last_message_at.desc().nulls_last())
    )
    matches = match_result.scalars().all()

    profiles = []
    for match in matches:
        other_id = match.user_b_id if match.user_a_id == current_uid else match.user_a_id
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == other_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            continue

        user_result = await db.execute(select(UserModel).where(UserModel.id == other_id))
        user = user_result.scalar_one_or_none()
        age = None
        if user and user.date_of_birth:
            from datetime import date
            today = date.today()
            age = today.year - user.date_of_birth.year - (
                (today.month, today.day) < (user.date_of_birth.month, user.date_of_birth.day)
            )

        profiles.append({
            "user_id": str(other_id),
            "display_name": profile.display_name,
            "age": age,
            "city": profile.city,
            "dating_goal": profile.dating_goal.value if profile.dating_goal else None,
            "match_id": str(match.id),
        })

    return {"matched": profiles, "total": len(profiles)}


async def find_user_by_name(name: str) -> dict:
    """Search for users by display name (case-insensitive partial match).

    Use this when the user mentions someone by name (e.g. "tôi thích Phúc")
    and you need to find that person's profile to check relationship status
    or get their user ID.

    Args:
        name: Display name or partial name to search for.

    Returns:
        Dict with 'found' (bool) and 'users' (list of {user_id, display_name, city, age, dating_goal}).
    """
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    current_uid = uuid.UUID(user_id_str)

    # Case-insensitive partial match on display_name
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.display_name.ilike(f"%{name}%"),
            UserProfile.user_id != current_uid,
        ).limit(5)
    )
    profiles = result.scalars().all()

    from db.models.user import User as UserModel
    users = []
    for p in profiles:
        user_result = await db.execute(
            select(UserModel).where(UserModel.id == p.user_id)
        )
        user = user_result.scalar_one_or_none()
        age = None
        if user and user.date_of_birth:
            from datetime import date
            today = date.today()
            age = today.year - user.date_of_birth.year - (
                (today.month, today.day) < (user.date_of_birth.month, user.date_of_birth.day)
            )
        users.append({
            "user_id": str(p.user_id),
            "display_name": p.display_name,
            "city": p.city,
            "age": age,
            "dating_goal": p.dating_goal.value if p.dating_goal else None,
        })

    return {
        "found": len(users) > 0,
        "users": users,
    }


async def get_candidate_profile(candidate_user_id: str) -> dict:
    """Get the PUBLIC profile of a candidate by user ID.

    Use this when the user asks about a candidate the assistant just suggested
    via search_candidates. For example: "kể thêm về người đầu tiên đi",
    "ứng viên thứ 2 có tính cách gì?", "người này thích gì?".

    This works for ANY user in the system — matched or not.
    Only returns public-facing fields. Does NOT reveal private info.

    Args:
        candidate_user_id: The UUID of the candidate (from search_candidates result).

    Returns:
        Dict with profile details.
    """
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    try:
        candidate_uid = uuid.UUID(candidate_user_id)
    except (ValueError, AttributeError):
        return {"found": False, "reason": "invalid_id", "message": "ID không hợp lệ."}

    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == candidate_uid)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        return {"found": False, "reason": "not_found", "message": "Không tìm thấy hồ sơ của người này."}

    user_result = await db.execute(select(UserModel).where(UserModel.id == candidate_uid))
    user = user_result.scalar_one_or_none()
    age = None
    if user and user.date_of_birth:
        from datetime import date
        today = date.today()
        age = today.year - user.date_of_birth.year - (
            (today.month, today.day) < (user.date_of_birth.month, user.date_of_birth.day)
        )

    # Check relationship status for context
    relation = "none"
    match_id = None
    current_uid = uuid.UUID(user_id_str)
    match_result = await db.execute(
        select(Match).where(
            Match.status == MatchStatus.ACTIVE,
            or_(
                (Match.user_a_id == current_uid) & (Match.user_b_id == candidate_uid),
                (Match.user_a_id == candidate_uid) & (Match.user_b_id == current_uid),
            ),
        )
    )
    existing_match = match_result.scalar_one_or_none()
    if existing_match:
        relation = "matched"
        match_id = str(existing_match.id)

    return {
        "found": True,
        "relation": relation,
        "match_id": match_id,
        "profile": {
            "display_name": profile.display_name,
            "age": age,
            "city": profile.city,
            "dating_goal": profile.dating_goal.value if profile.dating_goal else None,
            "bio": profile.bio,
            "personality_traits": profile.personality_traits or [],
            "hobbies": profile.hobbies or [],
            "values": profile.values or [],
            "communication_style": profile.communication_style,
            "public_summary": profile.public_summary,
        },
    }


async def check_relationship_status(name: str) -> dict:
    """Check the current relationship status between the logged-in user and a person by name.

    Use this BEFORE giving conversation advice about someone. It tells you:
    - Whether this person exists in the system
    - Whether you've liked them, they've liked you, or it's mutual
    - Whether you're already matched (so you can chat)
    - Whether you've passed on them

    Args:
        name: Display name of the person to check.

    Returns:
        Dict with status details: exists, relation (none/liked_by_me/liked_me/mutual/matched/passed),
        match_id (if matched), and person info.
    """
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    current_uid = uuid.UUID(user_id_str)

    # First, find the person by name
    search = await find_user_by_name(name)
    if not search.get("found"):
        return {
            "exists": False,
            "relation": "not_found",
            "message": f"Không tìm thấy người dùng nào tên '{name}' trong hệ thống.",
        }

    # Take the first match
    person = search["users"][0]
    person_uid = uuid.UUID(person["user_id"])

    # Check likes (both directions)
    i_liked = await db.execute(
        select(Like).where(
            Like.from_user_id == current_uid,
            Like.to_user_id == person_uid,
            Like.status == LikeStatus.ACTIVE,
        )
    )
    i_liked_them = i_liked.scalar_one_or_none() is not None

    they_liked = await db.execute(
        select(Like).where(
            Like.from_user_id == person_uid,
            Like.to_user_id == current_uid,
            Like.status == LikeStatus.ACTIVE,
        )
    )
    they_liked_me = they_liked.scalar_one_or_none() is not None

    # Check if already matched
    match_result = await db.execute(
        select(Match).where(
            Match.status == MatchStatus.ACTIVE,
            or_(
                (Match.user_a_id == current_uid) & (Match.user_b_id == person_uid),
                (Match.user_a_id == person_uid) & (Match.user_b_id == current_uid),
            ),
        )
    )
    existing_match = match_result.scalar_one_or_none()

    # Check if passed
    i_passed = await db.execute(
        select(Like).where(
            Like.from_user_id == current_uid,
            Like.to_user_id == person_uid,
            Like.status == LikeStatus.CANCELLED,
        )
    )
    i_passed_them = i_passed.scalar_one_or_none() is not None

    # Determine relation
    if existing_match:
        relation = "matched"
        match_id = str(existing_match.id)
    elif i_liked_them and they_liked_me:
        relation = "mutual"
        match_id = None
    elif i_liked_them:
        relation = "liked_by_me"
        match_id = None
    elif they_liked_me:
        relation = "liked_me"
        match_id = None
    elif i_passed_them:
        relation = "passed_by_me"
        match_id = None
    else:
        relation = "none"
        match_id = None

    return {
        "exists": True,
        "relation": relation,
        "match_id": match_id,
        "person": person,
        "message": _relation_message(relation, person["display_name"]),
    }


async def get_matched_user_profile(name: str) -> dict:
    """Get the PUBLIC profile of a matched user by their display name.

    Use this when the current user asks about a matched person's character,
    personality, or profile details (e.g. "Khang là người như thế nào?",
    "kể cho tôi về Khang", "Khang thích gì?").

    First tries exact name match via find_user_by_name. If that fails,
    searches through the user's match list with fuzzy matching (handles
    typos, accent variations, nicknames).

    Only returns public-facing fields: display_name, age, city, dating_goal,
    bio, personality_traits, hobbies, values, communication_style, public_summary.
    Does NOT reveal private info (email, location, deal_breakers, etc.).

    Args:
        name: Display name of the matched person.

    Returns:
        Dict with profile details if matched, or error with suggestions if not found.
    """
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    # Step 1: Try exact name match via check_relationship_status
    rel = await check_relationship_status(name)
    if rel.get("exists") and rel.get("relation") == "matched":
        return await _get_profile_by_uid(db, uuid.UUID(rel["person"]["user_id"]), rel)

    # Step 2: If name not found or not matched, try fuzzy search through matches
    matched_list = await list_matched_profiles()
    if matched_list.get("error"):
        return {"found": False, "reason": "error", "message": matched_list["error"]}

    matched_profiles = matched_list.get("matched", [])

    if not matched_profiles:
        return {
            "found": False,
            "reason": "no_matches",
            "message": "Bạn chưa có match nào. Hãy tìm kiếm người phù hợp trước nhé!",
        }

    # Fuzzy match against matched profiles
    fuzzy_results = _fuzzy_match_name(name, matched_profiles)

    if not fuzzy_results:
        # No fuzzy match — return the full match list so LLM can show user
        return {
            "found": False,
            "reason": "no_fuzzy_match",
            "message": f"Không tìm thấy ai tên '{name}' trong danh sách match của bạn.",
            "your_matches": matched_profiles,
        }

    if len(fuzzy_results) == 1:
        # Single match — return their profile
        match = fuzzy_results[0]
        person_uid = uuid.UUID(match["user_id"])
        rel_data = {
            "exists": True,
            "relation": "matched",
            "match_id": match["match_id"],
            "person": match,
            "message": _relation_message("matched", match["display_name"]),
        }
        return await _get_profile_by_uid(db, person_uid, rel_data)

    # Multiple fuzzy matches — return options for the LLM to clarify with user
    return {
        "found": False,
        "reason": "ambiguous",
        "message": f"Có {len(fuzzy_results)} người trong danh sách match có tên gần giống '{name}'.",
        "candidates": fuzzy_results,
    }


async def _get_profile_by_uid(db, person_uid, rel: dict) -> dict:
    """Fetch public profile by user_id. Internal helper."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == person_uid)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return {"found": False, "reason": "profile_missing", "message": "Không tìm thấy hồ sơ của người này."}

    # Compute age
    age = None
    if isinstance(rel.get("person"), dict):
        age = rel["person"].get("age")

    return {
        "found": True,
        "relation": rel.get("relation", "matched"),
        "match_id": rel.get("match_id"),
        "profile": {
            "display_name": profile.display_name,
            "age": age,
            "city": profile.city,
            "dating_goal": profile.dating_goal.value if profile.dating_goal else None,
            "bio": profile.bio,
            "personality_traits": profile.personality_traits or [],
            "hobbies": profile.hobbies or [],
            "values": profile.values or [],
            "communication_style": profile.communication_style,
            "public_summary": profile.public_summary,
        },
    }


def _relation_message(relation: str, name: str) -> str:
    """Human-readable Vietnamese message for relationship status."""
    messages = {
        "matched": f"Bạn và {name} đã match với nhau rồi! Có thể chat ngay.",
        "mutual": f"Bạn và {name} đã thích nhau! Match sẽ sớm được tạo.",
        "liked_by_me": f"Bạn đã gửi lời thích đến {name}. Đang chờ phản hồi từ đối phương.",
        "liked_me": f"{name} đã thích bạn! Bạn có muốn thích lại không?",
        "passed_by_me": f"Bạn đã bỏ qua {name} trước đó. Có thể tìm kiếm lại nếu muốn.",
        "none": f"Bạn chưa có tương tác gì với {name}. Có thể tìm kiếm và gửi lời thích.",
    }
    return messages.get(relation, "")

