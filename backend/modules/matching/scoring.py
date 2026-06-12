"""Hybrid matching scoring algorithm — PRD §12.

final_score = hard_filter_pass * (
    location_score * 0.15 +
    dating_goal_score * 0.20 +
    age_score * 0.10 +
    interest_similarity * 0.20 +
    personality_similarity * 0.20 +
    dealbreaker_score * 0.15
)

score_tier: >=80 → high, 60-79 → medium, <60 → low
"""
import math
from typing import Any

from common.enums import DatingGoal, ScoreTier

# Dating goal compatibility matrix (row=user, col=candidate): 1.0 = perfect match
_GOAL_COMPAT: dict[str, dict[str, float]] = {
    "serious":       {"serious": 1.0, "friends_first": 0.6, "casual": 0.2, "not_sure": 0.5},
    "casual":        {"casual": 1.0, "friends_first": 0.5, "serious": 0.2, "not_sure": 0.6},
    "friends_first": {"friends_first": 1.0, "serious": 0.6, "casual": 0.5, "not_sure": 0.7},
    "not_sure":      {"not_sure": 0.8, "friends_first": 0.7, "casual": 0.6, "serious": 0.5},
}


def compute_score(
    user_profile: dict[str, Any],
    candidate_profile: dict[str, Any],
    user_embedding: list[float] | None = None,
    candidate_embedding: list[float] | None = None,
) -> tuple[int, list[str], str | None]:
    """Compute compatibility score between user and candidate.

    Returns:
        (score 0-100, reason_codes, score_tier_override_or_None)
    """
    # Hard filters
    passed, fail_reason = _hard_filters(user_profile, candidate_profile)
    if not passed:
        return 0, [fail_reason], ScoreTier.LOW.value

    scores: dict[str, float] = {}
    reasons: list[str] = []

    # 1. Location (15%)
    loc, loc_reason = _location_score(user_profile, candidate_profile)
    scores["location"] = loc * 0.15
    if loc > 0.7:
        reasons.append("location_nearby")

    # 2. Dating goal (20%)
    goal, goal_reason = _dating_goal_score(user_profile, candidate_profile)
    scores["dating_goal"] = goal * 0.20
    if goal > 0.7:
        reasons.append("same_dating_goal")
    elif goal < 0.4:
        reasons.append("potential_goal_mismatch")

    # 3. Age preference (10%)
    age, age_reason = _age_score(user_profile, candidate_profile)
    scores["age"] = age * 0.10
    if age > 0.7:
        reasons.append("age_preference_match")

    # 4. Interest similarity (20%)
    interest, interest_reason = _interest_similarity(user_profile, candidate_profile)
    scores["interest"] = interest * 0.20
    if interest > 0.5:
        reasons.append("shared_interests")

    # 5. Personality / embedding similarity (20%)
    personality, pers_reason = _personality_similarity(
        user_profile, candidate_profile, user_embedding, candidate_embedding
    )
    scores["personality"] = personality * 0.20
    if personality > 0.5:
        reasons.append("compatible_communication_style")

    # 6. Dealbreaker avoidance (15%)
    db_score, db_reason = _dealbreaker_safety(user_profile, candidate_profile)
    scores["dealbreaker"] = db_score * 0.15
    if db_score > 0.8:
        reasons.append("dealbreaker_safe")

    raw_score = sum(scores.values())
    # Scale to 0-100
    final_score = min(100, max(0, int(raw_score * 100)))

    # Deduplicate reasons
    reasons = list(dict.fromkeys(reasons))

    return final_score, reasons, score_tier_for(final_score)


def score_tier_for(score: int) -> str:
    if score >= 80:
        return ScoreTier.HIGH.value
    elif score >= 60:
        return ScoreTier.MEDIUM.value
    return ScoreTier.LOW.value


def _hard_filters(user: dict, candidate: dict) -> tuple[bool, str]:
    """Check hard pass/fail conditions."""
    # Gender/interested_in compatibility — split on comma for multi-gender support
    user_gender = (user.get("gender") or "").lower().strip()
    user_interested = (user.get("interested_in") or "").lower().strip()
    cand_gender = (candidate.get("gender") or "").lower().strip()
    cand_interested = (candidate.get("interested_in") or "").lower().strip()

    # User wants cand_gender: cand_gender must be IN user's interested_in list
    if user_interested and cand_gender:
        user_interested_set = {g.strip() for g in user_interested.split(",")}
        if cand_gender not in user_interested_set:
            return False, "gender_mismatch"
    # Candidate wants user_gender: user_gender must be IN candidate's interested_in list
    if cand_interested and user_gender:
        cand_interested_set = {g.strip() for g in cand_interested.split(",")}
        if user_gender not in cand_interested_set:
            return False, "gender_mismatch"

    # Age preferences (two-way)
    user_age = user.get("age")
    cand_age = candidate.get("age")
    prefs_user = user.get("preferences") or {}
    prefs_cand = candidate.get("preferences") or {}

    if isinstance(prefs_user, str):
        import json
        try:
            prefs_user = json.loads(prefs_user)
        except (json.JSONDecodeError, TypeError):
            prefs_user = {}
    if isinstance(prefs_cand, str):
        import json
        try:
            prefs_cand = json.loads(prefs_cand)
        except (json.JSONDecodeError, TypeError):
            prefs_cand = {}

    if user_age and cand_age:
        # Check against user's preferred age range
        min_a = prefs_user.get("preferred_age_min")
        max_a = prefs_user.get("preferred_age_max")
        if min_a is not None and cand_age < min_a:
            return False, "age_out_of_range"
        if max_a is not None and cand_age > max_a:
            return False, "age_out_of_range"

        # Check against candidate's preferred age range
        min_b = prefs_cand.get("preferred_age_min")
        max_b = prefs_cand.get("preferred_age_max")
        if min_b is not None and user_age < min_b:
            return False, "age_out_of_range"
        if max_b is not None and user_age > max_b:
            return False, "age_out_of_range"

    return True, "pass"


def _location_score(user: dict, candidate: dict) -> tuple[float, str]:
    """Score location proximity."""
    user_city = (user.get("city") or "").lower().strip()
    cand_city = (candidate.get("city") or "").lower().strip()

    if user_city and cand_city and user_city == cand_city:
        return 1.0, "same_city"

    # Distance-based scoring (if lat/lng available)
    user_lat = user.get("lat")
    user_lng = user.get("lng")
    cand_lat = candidate.get("lat")
    cand_lng = candidate.get("lng")

    if user_lat and user_lng and cand_lat and cand_lng:
        distance = _haversine(user_lat, user_lng, cand_lat, cand_lng)
        prefs = user.get("preferences") or {}
        max_dist = prefs.get("preferred_distance_km", 50)
        if distance <= max_dist:
            # Linear decay within preferred range
            return max(0.1, 1.0 - (distance / max_dist) * 0.9), f"distance_{int(distance)}km"
        else:
            return 0.0, f"too_far_{int(distance)}km"

    return 0.5, "no_location_data"


def _dating_goal_score(user: dict, candidate: dict) -> tuple[float, str]:
    """Score dating goal compatibility."""
    user_goal = user.get("dating_goal", "")
    cand_goal = candidate.get("dating_goal", "")

    if not user_goal or not cand_goal:
        return 0.5, "unknown_goal"

    compat = _GOAL_COMPAT.get(user_goal, {}).get(cand_goal, 0.5)
    return compat, f"goal_{user_goal}_vs_{cand_goal}"


def _age_score(user: dict, candidate: dict) -> tuple[float, str]:
    """Score age preference fit."""
    user_age = user.get("age")
    cand_age = candidate.get("age")
    prefs = user.get("preferences") or {}

    if not user_age or not cand_age:
        return 0.5, "unknown_age"

    min_a = prefs.get("preferred_age_min")
    max_a = prefs.get("preferred_age_max")
    if min_a is not None and max_a is not None:
        center = (min_a + max_a) / 2
        # Gaussian-like scoring: closer to center = higher score
        spread = max(1, (max_a - min_a) / 3)
        diff = abs(cand_age - center)
        return max(0.1, math.exp(-0.5 * (diff / spread) ** 2)), "age_fit"
    return 0.8, "no_age_preference"


def _interest_similarity(user: dict, candidate: dict) -> tuple[float, str]:
    """Jaccard similarity of hobbies/interests."""
    user_hobbies = _normalize_list(user.get("hobbies"))
    cand_hobbies = _normalize_list(candidate.get("hobbies"))

    if not user_hobbies or not cand_hobbies:
        return 0.3, "insufficient_interest_data"

    user_set = set(h.lower().strip() for h in user_hobbies)
    cand_set = set(h.lower().strip() for h in cand_hobbies)

    if not user_set or not cand_set:
        return 0.3, "empty_interest_sets"

    intersection = len(user_set & cand_set)
    union = len(user_set | cand_set)
    jaccard = intersection / union if union > 0 else 0.0

    return jaccard, f"interests_{intersection}_shared"


def _personality_similarity(
    user: dict,
    candidate: dict,
    user_emb: list[float] | None = None,
    cand_emb: list[float] | None = None,
) -> tuple[float, str]:
    """Personality/communication compatibility via embedding cosine similarity."""
    # Communication style match
    user_style = (user.get("communication_style") or "").lower().strip()
    cand_style = (candidate.get("communication_style") or "").lower().strip()

    style_score = 0.0
    if user_style and cand_style:
        if user_style == cand_style:
            style_score = 1.0
        else:
            style_score = 0.3  # different styles

    if user_emb and cand_emb and len(user_emb) > 0 and len(cand_emb) > 0:
        emb_score = _cosine_similarity(user_emb, cand_emb)
        # Blend: 60% embedding, 40% communication style
        return 0.6 * emb_score + 0.4 * style_score, "embedding_match"

    return style_score if style_score > 0 else 0.5, "no_embedding"


def _dealbreaker_safety(user: dict, candidate: dict) -> tuple[float, str]:
    """Check candidate doesn't trigger user's deal breakers."""
    dealbreakers = _normalize_list(user.get("deal_breakers"))
    if not dealbreakers:
        return 1.0, "no_dealbreakers"

    # For MVP, dealbreakers are keywords checked against candidate public data
    cand_text = " ".join([
        candidate.get("bio") or "",
        candidate.get("public_summary") or "",
        " ".join(_normalize_list(candidate.get("values", []))),
    ]).lower()

    triggered = []
    for db in dealbreakers:
        if db.lower().strip() in cand_text:
            triggered.append(db)

    if triggered:
        # penalty: -0.15 per triggered dealbreaker
        penalty = min(1.0, len(triggered) * 0.15)
        return max(0.1, 1.0 - penalty), f"dealbreakers_triggered_{len(triggered)}"

    return 1.0, "all_dealbreakers_clear"


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Compute distance in km between two lat/lng points."""
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def _normalize_list(value: Any) -> list:
    """Normalize JSONB hobbies/interests to a Python list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.keys())
    return []
