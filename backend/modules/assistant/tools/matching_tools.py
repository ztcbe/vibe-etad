"""Matching tools for the AI assistant — reads DB/user from contextvars."""
import uuid

from modules.assistant.tools import current_db, current_user_id
from modules.matching import service as matching_service


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
