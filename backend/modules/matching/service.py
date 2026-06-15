"""Matching service — candidate search, like, pass, list matches, unmatch."""
import json
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User
from db.models.profile import UserProfile, ProfileEmbedding
from db.models.matching import Like, Match, Recommendation
from db.models.chat import ChatMessage
from db.models.moderation import Block
from modules.matching.scoring import compute_score, score_tier_for
from common.events import event_bus, Event
from modules.profiles import service as profile_service
from common.errors import NotFoundError, ValidationError, ConflictError
from common.enums import (
    LikeStatus, MatchStatus, RecommendationStatus, VisibilityStatus, UserStatus
)

logger = logging.getLogger(__name__)


async def search_candidates(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 5, filters: dict | None = None
) -> list[dict]:
    """Search for compatible candidates. Returns ranked candidate cards."""
    user_profile = await profile_service.get_my_profile(db, user_id)
    user_data = _profile_to_dict(user_profile)

    # Get blocked/banned user IDs to exclude
    blocked_ids = await _get_blocked_user_ids(db, user_id)

    # Query active candidates
    stmt = (
        select(User, UserProfile)
        .join(UserProfile, UserProfile.user_id == User.id)
        .where(
            User.id != user_id,
            User.status == UserStatus.ACTIVE,
            UserProfile.visibility_status == VisibilityStatus.ACTIVE,
            User.id.notin_(blocked_ids),
        )
        .limit(limit * 5)  # Fetch more for scoring
    )
    result = await db.execute(stmt)
    candidates = result.all()

    # Get embedding for user (if available)
    user_embedding = None
    emb_result = await db.execute(
        select(ProfileEmbedding).where(ProfileEmbedding.user_id == user_id)
    )
    emb_row = emb_result.scalar_one_or_none()
    if emb_row and emb_row.embedding:
        user_embedding = emb_row.embedding

    # Score each candidate
    scored = []
    for user, profile in candidates:
        # Check already liked/passed
        existing = await db.execute(
            select(Recommendation).where(
                Recommendation.user_id == user_id,
                Recommendation.candidate_user_id == user.id,
            )
        )
        rec = existing.scalar_one_or_none()

        like_status = "none"
        if rec:
            if rec.status == RecommendationStatus.LIKED:
                like_status = "liked"
            elif rec.status == RecommendationStatus.PASSED:
                like_status = "passed"

        cand_data = _profile_to_dict(profile, user=user)
        score, reasons, tier = compute_score(user_data, cand_data)

        # Generate considerations
        considerations = _generate_considerations(user_data, cand_data)

        # Save recommendation
        if rec is None:
            rec = Recommendation(
                user_id=user_id,
                candidate_user_id=user.id,
                score=score,
                reason_codes=reasons,
                explanation="; ".join(reasons),
            )
            db.add(rec)
        else:
            rec.score = score
            rec.reason_codes = reasons

        scored.append({
            "type": "candidate",
            "candidate_user_id": user.id,
            "display_name": profile.display_name,
            "age": _calculate_age(user.date_of_birth),
            "city": profile.city,
            "avatar_url": profile.avatar_url,
            "dating_goal": profile.dating_goal.value if profile.dating_goal else None,
            "score": score,
            "score_tier": tier or score_tier_for(score),
            "reasons": _generate_reason_texts(user_data, cand_data, reasons),
            "considerations": considerations,
            "reason_codes": reasons,
            "like_status": like_status,
        })

    await db.commit()

    # Sort by score desc, return top N
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


async def like_candidate(db: AsyncSession, user_id: uuid.UUID, candidate_user_id: uuid.UUID) -> dict:
    """Like a candidate. If mutual, create a match."""
    # Validate candidate exists and is active
    cand_result = await db.execute(
        select(User, UserProfile)
        .join(UserProfile, UserProfile.user_id == User.id)
        .where(User.id == candidate_user_id, User.status == UserStatus.ACTIVE)
    )
    row = cand_result.one_or_none()
    if row is None:
        raise NotFoundError(code="CANDIDATE_NOT_FOUND", message="Candidate not found")

    cand_user, cand_profile = row

    # Check if already liked
    existing_like = await db.execute(
        select(Like).where(
            Like.from_user_id == user_id,
            Like.to_user_id == candidate_user_id,
            Like.status == LikeStatus.ACTIVE,
        )
    )
    if existing_like.scalar_one_or_none():
        raise ConflictError(code="ALREADY_LIKED", message="You already liked this user")

    # Create like record
    like = Like(from_user_id=user_id, to_user_id=candidate_user_id)
    db.add(like)

    # Create/update recommendation
    rec_result = await db.execute(
        select(Recommendation).where(
            Recommendation.user_id == user_id,
            Recommendation.candidate_user_id == candidate_user_id,
        )
    )
    rec = rec_result.scalar_one_or_none()
    if rec:
        rec.status = RecommendationStatus.LIKED
    else:
        rec = Recommendation(
            user_id=user_id,
            candidate_user_id=candidate_user_id,
            score=0,
            reason_codes=[],
            status=RecommendationStatus.LIKED,
        )
        db.add(rec)

    # Check if mutual (candidate already liked user)
    mutual_result = await db.execute(
        select(Like).where(
            Like.from_user_id == candidate_user_id,
            Like.to_user_id == user_id,
            Like.status == LikeStatus.ACTIVE,
        )
    )
    mutual_like = mutual_result.scalar_one_or_none()

    is_mutual = False
    match_record = None

    if mutual_like:
        is_mutual = True
        # Create match
        match_record = Match(
            user_a_id=user_id,
            user_b_id=candidate_user_id,
            status=MatchStatus.ACTIVE,
            last_message_at=datetime.now(timezone.utc),
        )
        db.add(match_record)

        # Update mutual like's recommendation status
        mutual_rec = await db.execute(
            select(Recommendation).where(
                Recommendation.user_id == candidate_user_id,
                Recommendation.candidate_user_id == user_id,
            )
        )
        mr = mutual_rec.scalar_one_or_none()
        if mr:
            mr.status = RecommendationStatus.LIKED

    await db.commit()

    # Emit events for notification system
    if is_mutual:
        event_bus.emit(Event("match_created", {
            "match_id": str(match_record.id),
            "user_a_id": str(user_id),
            "user_b_id": str(candidate_user_id),
        }))
    else:
        event_bus.emit(Event("like_received", {
            "from_user_id": str(user_id),
            "to_user_id": str(candidate_user_id),
        }))

    result = {
        "match_id": match_record.id if match_record else None,
        "is_mutual": is_mutual,
        "user": {
            "user_id": cand_user.id,
            "display_name": cand_profile.display_name,
            "age": _calculate_age(cand_user.date_of_birth),
            "avatar_url": cand_profile.avatar_url,
        },
    }

    return result


async def pass_candidate(db: AsyncSession, user_id: uuid.UUID, candidate_user_id: uuid.UUID) -> None:
    """Pass on a candidate."""
    rec_result = await db.execute(
        select(Recommendation).where(
            Recommendation.user_id == user_id,
            Recommendation.candidate_user_id == candidate_user_id,
        )
    )
    rec = rec_result.scalar_one_or_none()
    if rec:
        rec.status = RecommendationStatus.PASSED
    else:
        rec = Recommendation(
            user_id=user_id,
            candidate_user_id=candidate_user_id,
            score=0,
            reason_codes=[],
            status=RecommendationStatus.PASSED,
        )
        db.add(rec)
    await db.commit()


async def list_matches(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """List matches in 2 groups: matched + pending. Per v0.2 §3.3 contract."""
    # Get active matches
    match_result = await db.execute(
        select(Match).where(
            or_(Match.user_a_id == user_id, Match.user_b_id == user_id),
            Match.status == MatchStatus.ACTIVE,
        ).order_by(Match.last_message_at.desc().nulls_last())
    )
    matches = match_result.scalars().all()

    # Get pending likes sent by user
    sent_result = await db.execute(
        select(Like, User, UserProfile)
        .join(User, User.id == Like.to_user_id)
        .join(UserProfile, UserProfile.user_id == User.id)
        .where(Like.from_user_id == user_id, Like.status == LikeStatus.ACTIVE)
        .order_by(Like.created_at.desc())
    )
    pending_sent = sent_result.all()

    # Get pending likes received (not yet matched)
    received_result = await db.execute(
        select(Like, User, UserProfile)
        .join(User, User.id == Like.from_user_id)
        .join(UserProfile, UserProfile.user_id == User.id)
        .where(Like.to_user_id == user_id, Like.status == LikeStatus.ACTIVE)
        .order_by(Like.created_at.desc())
    )
    pending_received = received_result.all()

    # Build matched items
    matched_items = []
    for match in matches:
        other_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
        other_user = await db.get(User, other_id)
        other_profile = await db.execute(
            select(UserProfile).where(UserProfile.user_id == other_id)
        )
        profile = other_profile.scalar_one_or_none()

        # Get last message
        last_msg = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.match_id == match.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        last_msg_row = last_msg.scalar_one_or_none()

        # Unread count
        unread = await db.execute(
            select(func.count(ChatMessage.id)).where(
                ChatMessage.match_id == match.id,
                ChatMessage.sender_user_id != user_id,
                ChatMessage.status != "read",
            )
        )
        unread_count = unread.scalar() or 0

        # Compute online status (online if active in last 5 minutes)
        is_online = False
        if other_user and other_user.last_active_at:
            is_online = (datetime.now(timezone.utc) - other_user.last_active_at).total_seconds() < 300

        matched_items.append({
            "match_id": match.id,
            "user": {
                "user_id": other_id,
                "display_name": profile.display_name if profile else None,
                "age": _calculate_age(other_user.date_of_birth) if other_user else None,
                "avatar_url": profile.avatar_url if profile else None,
                "is_online": is_online,
            },
            "last_message": {
                "content": last_msg_row.content,
                "created_at": last_msg_row.created_at.isoformat(),
                "sender_user_id": str(last_msg_row.sender_user_id),
            } if last_msg_row else None,
            "unread_count": unread_count,
            "matched_at": match.created_at.isoformat(),
        })

    # Build pending sent items
    pending_sent_items = []
    for like, user, profile in pending_sent:
        # Skip if already matched
        already_matched = any(
            (m.user_a_id == user_id and m.user_b_id == user.id) or
            (m.user_b_id == user_id and m.user_a_id == user.id)
            for m in matches
        )
        if already_matched:
            continue
        pending_sent_items.append({
            "user": {
                "user_id": user.id,
                "display_name": profile.display_name,
                "age": _calculate_age(user.date_of_birth),
                "avatar_url": profile.avatar_url,
            },
            "liked_at": like.created_at.isoformat(),
        })

    # Build pending received items
    pending_received_items = []
    for like, user, profile in pending_received:
        already_matched = any(
            (m.user_a_id == user_id and m.user_b_id == user.id) or
            (m.user_b_id == user_id and m.user_a_id == user.id)
            for m in matches
        )
        if already_matched:
            continue
        pending_received_items.append({
            "user": {
                "user_id": user.id,
                "display_name": profile.display_name,
                "age": _calculate_age(user.date_of_birth),
                "avatar_url": profile.avatar_url,
            },
            "liked_at": like.created_at.isoformat(),
        })

    return {
        "matched": matched_items,
        "pending_sent": pending_sent_items,
        "pending_received": pending_received_items,
    }


async def unmatch(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> None:
    """Unmatch — set match status to unmatched."""
    match = await db.get(Match, match_id)
    if match is None:
        raise NotFoundError(code="MATCH_NOT_FOUND", message="Match not found")
    if match.user_a_id != user_id and match.user_b_id != user_id:
        raise NotFoundError(code="MATCH_NOT_FOUND", message="Match not found")
    if match.status != MatchStatus.ACTIVE:
        raise ValidationError(code="NOT_ACTIVE_MATCH", message="Match is not active")

    match.status = MatchStatus.UNMATCHED
    match.updated_at = datetime.now(timezone.utc)
    await db.commit()

    event_bus.emit(Event("match_unavailable", {
        "match_id": str(match_id),
        "user_a_id": str(match.user_a_id),
        "user_b_id": str(match.user_b_id),
        "reason": "unmatched",
    }))


# --- Helpers ---

def _profile_to_dict(profile: UserProfile, user: User | None = None) -> dict:
    prefs = profile.preferences or {}
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except (json.JSONDecodeError, TypeError):
            prefs = {}

    return {
        "user_id": str(profile.user_id),
        "display_name": profile.display_name,
        "gender": profile.gender,
        "interested_in": profile.interested_in,
        "city": profile.city,
        "lat": profile.lat,
        "lng": profile.lng,
        "dating_goal": profile.dating_goal.value if profile.dating_goal else None,
        "bio": profile.bio,
        "personality_traits": profile.personality_traits,
        "hobbies": profile.hobbies,
        "values": profile.values,
        "communication_style": profile.communication_style,
        "deal_breakers": profile.deal_breakers,
        "preferences": prefs,
        "public_summary": profile.public_summary,
        "age": _calculate_age(user.date_of_birth) if user else None,
    }


def _calculate_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


async def _get_blocked_user_ids(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Get set of user IDs that are blocked (both directions)."""
    result = await db.execute(
        select(Block).where(
            or_(
                Block.blocker_user_id == user_id,
                Block.blocked_user_id == user_id,
            )
        )
    )
    blocks = result.scalars().all()
    blocked = set()
    for b in blocks:
        blocked.add(b.blocker_user_id)
        blocked.add(b.blocked_user_id)
    blocked.discard(user_id)
    return blocked


def _generate_reason_texts(user: dict, candidate: dict, reason_codes: list[str]) -> list[str]:
    """Generate Vietnamese reason texts from reason codes."""
    texts = []
    for code in reason_codes:
        if code == "shared_interests":
            user_h = set((h or "").lower() for h in (user.get("hobbies") or []))
            cand_h = set((h or "").lower() for h in (candidate.get("hobbies") or []))
            shared = user_h & cand_h
            if shared:
                texts.append(f"Cả hai đều yêu thích {', '.join(list(shared)[:2])}.")
            else:
                texts.append("Cả hai có chung sở thích và gu sống.")
        elif code == "same_dating_goal":
            texts.append("Cả hai đều đang tìm kiếm một mối quan hệ nghiêm túc.")
        elif code == "location_nearby":
            texts.append("Sống gần nhau, thuận tiện gặp gỡ.")
        elif code == "age_preference_match":
            texts.append("Độ tuổi phù hợp với mong muốn của bạn.")
        elif code == "compatible_communication_style":
            texts.append("Phong cách giao tiếp tương đồng.")
        elif code == "dealbreaker_safe":
            texts.append("Không có yếu tố không tương thích.")
    return texts[:3]  # Max 3 reason texts


def _generate_considerations(user: dict, candidate: dict) -> list[str]:
    """Generate consideration/concern texts."""
    considerations = []
    # Age gap consideration
    user_age = user.get("age")
    cand_age = candidate.get("age")
    if user_age and cand_age and abs(user_age - cand_age) > 10:
        considerations.append(f"Chênh lệch tuổi {abs(user_age - cand_age)} tuổi.")

    # Goal mismatch
    user_goal = user.get("dating_goal")
    cand_goal = candidate.get("dating_goal")
    if user_goal and cand_goal and user_goal != cand_goal:
        goal_labels = {"serious": "nghiêm túc", "casual": "tìm bạn", "friends_first": "tìm hiểu", "not_sure": "chưa rõ"}
        considerations.append(
            f"Bạn tìm kiếm {goal_labels.get(user_goal, user_goal)}, "
            f"người này tìm kiếm {goal_labels.get(cand_goal, cand_goal)}."
        )

    # City difference
    user_city = (user.get("city") or "").lower()
    cand_city = (candidate.get("city") or "").lower()
    if user_city and cand_city and user_city != cand_city:
        considerations.append(f"Khác thành phố ({candidate.get('city', 'khác')}).")

    return considerations[:2]  # Max 2 considerations
