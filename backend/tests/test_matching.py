"""S3 tests — Matching module: search, like, pass, mutual match, list, unmatch, scoring."""
import uuid

import pytest


@pytest.mark.asyncio
async def test_search_no_candidates(client, auth_headers):
    """Search candidates when no other users exist — should return empty."""
    resp = await client.post("/api/matches/search", headers=auth_headers, json={"limit": 5})
    data = resp.json()
    assert data["success"] is True
    assert data["data"] == []


@pytest.mark.asyncio
async def test_search_with_candidates(client):
    """Search candidates with 2 other users having profiles."""
    # Register user A (main)
    ra = await client.post("/api/auth/register", json={
        "username": "aaa", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1995-06-15",
    })
    token_a = ra.json()["data"]["access_token"]
    ha = {"Authorization": f"Bearer {token_a}"}

    # Set profile for A
    await client.patch("/api/profile/me", headers=ha, json={
        "display_name": "Người A", "gender": "male", "interested_in": "female",
        "city": "Hồ Chí Minh", "dating_goal": "serious",
        "hobbies": ["Cà phê", "Đọc sách", "Du lịch"],
        "preferences": {"preferred_age_min": 22, "preferred_age_max": 35, "preferred_distance_km": 100, "preferred_gender": "female"},
    })

    # Register user B (candidate 1)
    rb = await client.post("/api/auth/register", json={
        "username": "bbb", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1998-03-20",
    })
    token_b = rb.json()["data"]["access_token"]
    hb = {"Authorization": f"Bearer {token_b}"}

    await client.patch("/api/profile/me", headers=hb, json={
        "display_name": "Người B", "gender": "female", "interested_in": "male",
        "city": "Hồ Chí Minh", "dating_goal": "serious",
        "hobbies": ["Cà phê", "Yoga", "Nhiếp ảnh"],
        "preferences": {"preferred_age_min": 25, "preferred_age_max": 35, "preferred_distance_km": 50, "preferred_gender": "male"},
    })

    # Register user C (candidate 2)
    rc = await client.post("/api/auth/register", json={
        "username": "ccc", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "2000-10-05",
    })
    token_c = rc.json()["data"]["access_token"]
    hc = {"Authorization": f"Bearer {token_c}"}

    await client.patch("/api/profile/me", headers=hc, json={
        "display_name": "Người C", "gender": "female", "interested_in": "male",
        "city": "Hà Nội", "dating_goal": "casual",
        "hobbies": ["Trekking", "Bơi lội"],
        "preferences": {"preferred_age_min": 20, "preferred_age_max": 30, "preferred_distance_km": 200, "preferred_gender": "male"},
    })

    # Search from A
    resp = await client.post("/api/matches/search", headers=ha, json={"limit": 5})
    data = resp.json()
    assert data["success"] is True
    cards = data["data"]
    assert len(cards) == 2

    # First card should be B (same city, same goal → higher score)
    assert cards[0]["type"] == "candidate"
    assert cards[0]["candidate_user_id"] is not None
    assert cards[0]["score"] >= 0
    assert cards[0]["score_tier"] in ("high", "medium", "low")
    assert "reasons" in cards[0]
    assert "considerations" in cards[0]
    assert cards[0]["like_status"] == "none"


@pytest.mark.asyncio
async def test_like_candidate(client, auth_headers):
    """Like a candidate."""
    # Create + setup candidate
    rc = await client.post("/api/auth/register", json={
        "username": "like_target", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1998-05-10",
    })
    token_c = rc.json()["data"]["access_token"]
    hc = {"Authorization": f"Bearer {token_c}"}

    resp = await client.patch("/api/profile/me", headers=hc, json={
        "display_name": "Target", "gender": "female", "interested_in": "male",
        "city": "Hồ Chí Minh", "dating_goal": "serious",
    })
    # Extract user_id from response
    profile_resp = await client.get("/api/profile/me", headers=hc)
    target_id = profile_resp.json()["data"]["user_id"]

    # Like from main user
    resp = await client.post(f"/api/matches/{target_id}/like", headers=auth_headers)
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["is_mutual"] is False  # Target hasn't liked back


@pytest.mark.asyncio
async def test_mutual_match(client):
    """Test mutual match: A likes B, B likes A → match created."""
    # Register A
    ra = await client.post("/api/auth/register", json={
        "username": "mutual_a", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1995-01-01",
    })
    token_a = ra.json()["data"]["access_token"]
    ha = {"Authorization": f"Bearer {token_a}"}
    await client.patch("/api/profile/me", headers=ha, json={
        "display_name": "A", "gender": "male", "interested_in": "female",
        "city": "HCM", "dating_goal": "serious",
    })
    a_profile = await client.get("/api/profile/me", headers=ha)
    a_id = a_profile.json()["data"]["user_id"]

    # Register B
    rb = await client.post("/api/auth/register", json={
        "username": "mutual_b", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1997-01-01",
    })
    token_b = rb.json()["data"]["access_token"]
    hb = {"Authorization": f"Bearer {token_b}"}
    await client.patch("/api/profile/me", headers=hb, json={
        "display_name": "B", "gender": "female", "interested_in": "male",
        "city": "HCM", "dating_goal": "serious",
    })
    b_profile = await client.get("/api/profile/me", headers=hb)
    b_id = b_profile.json()["data"]["user_id"]

    # A likes B
    resp = await client.post(f"/api/matches/{b_id}/like", headers=ha)
    assert resp.json()["data"]["is_mutual"] is False

    # B likes A → should be mutual
    resp = await client.post(f"/api/matches/{a_id}/like", headers=hb)
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["is_mutual"] is True
    assert data["data"]["match_id"] is not None


@pytest.mark.asyncio
async def test_pass_candidate(client, auth_headers):
    """Pass on a candidate."""
    rc = await client.post("/api/auth/register", json={
        "username": "pass_target", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1999-01-01",
    })
    token_c = rc.json()["data"]["access_token"]
    hc = {"Authorization": f"Bearer {token_c}"}
    await client.patch("/api/profile/me", headers=hc, json={
        "display_name": "PassMe", "gender": "female", "interested_in": "male",
        "city": "HN", "dating_goal": "serious",
    })
    profile_resp = await client.get("/api/profile/me", headers=hc)
    target_id = profile_resp.json()["data"]["user_id"]

    resp = await client.post(f"/api/matches/{target_id}/pass", headers=auth_headers)
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["status"] == "passed"


@pytest.mark.asyncio
async def test_list_matches(client):
    """List matches in 2 groups: matched + pending."""
    # Create 2 users and create a match
    ra = await client.post("/api/auth/register", json={
        "username": "list_a", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1995-01-01",
    })
    token_a = ra.json()["data"]["access_token"]
    ha = {"Authorization": f"Bearer {token_a}"}
    await client.patch("/api/profile/me", headers=ha, json={
        "display_name": "ListA", "gender": "male", "interested_in": "female",
        "city": "HCM", "dating_goal": "serious",
    })
    a_data = await client.get("/api/profile/me", headers=ha)
    a_id = a_data.json()["data"]["user_id"]

    rb = await client.post("/api/auth/register", json={
        "username": "list_b", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1997-01-01",
    })
    token_b = rb.json()["data"]["access_token"]
    hb = {"Authorization": f"Bearer {token_b}"}
    await client.patch("/api/profile/me", headers=hb, json={
        "display_name": "ListB", "gender": "female", "interested_in": "male",
        "city": "HCM", "dating_goal": "serious",
    })
    b_data = await client.get("/api/profile/me", headers=hb)
    b_id = b_data.json()["data"]["user_id"]

    # Create mutual match
    await client.post(f"/api/matches/{b_id}/like", headers=ha)
    await client.post(f"/api/matches/{a_id}/like", headers=hb)

    # Check matches for A
    resp = await client.get("/api/matches", headers=ha)
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]["matched"]) == 1
    assert data["data"]["matched"][0]["user"]["display_name"] == "ListB"
    assert "last_message" in data["data"]["matched"][0]
    assert data["data"]["matched"][0]["unread_count"] == 0


@pytest.mark.asyncio
async def test_unmatch(client):
    """Unmatch an existing match."""
    # Create 2 users + match
    ra = await client.post("/api/auth/register", json={
        "username": "unmatch_a", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1995-01-01",
    })
    token_a = ra.json()["data"]["access_token"]
    ha = {"Authorization": f"Bearer {token_a}"}
    await client.patch("/api/profile/me", headers=ha, json={
        "display_name": "UnA", "gender": "male", "interested_in": "female",
        "city": "HCM", "dating_goal": "serious",
    })
    pa = await client.get("/api/profile/me", headers=ha)
    a_id = pa.json()["data"]["user_id"]

    rb = await client.post("/api/auth/register", json={
        "username": "unmatch_b", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1997-01-01",
    })
    token_b = rb.json()["data"]["access_token"]
    hb = {"Authorization": f"Bearer {token_b}"}
    await client.patch("/api/profile/me", headers=hb, json={
        "display_name": "UnB", "gender": "female", "interested_in": "male",
        "city": "HCM", "dating_goal": "serious",
    })
    pb = await client.get("/api/profile/me", headers=hb)
    b_id = pb.json()["data"]["user_id"]

    # Match
    await client.post(f"/api/matches/{b_id}/like", headers=ha)
    resp = await client.post(f"/api/matches/{a_id}/like", headers=hb)
    match_id = resp.json()["data"]["match_id"]

    # Unmatch
    resp = await client.post(f"/api/matches/{match_id}/unmatch", headers=ha)
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["status"] == "unmatched"

    # Verify match gone from list
    resp = await client.get("/api/matches", headers=ha)
    assert len(resp.json()["data"]["matched"]) == 0


class TestScoring:
    """Unit tests for the scoring algorithm."""

    def test_score_tier_high(self):
        from modules.matching.scoring import score_tier_for
        assert score_tier_for(85) == "high"
        assert score_tier_for(80) == "high"

    def test_score_tier_medium(self):
        from modules.matching.scoring import score_tier_for
        assert score_tier_for(65) == "medium"
        assert score_tier_for(60) == "medium"
        assert score_tier_for(79) == "medium"

    def test_score_tier_low(self):
        from modules.matching.scoring import score_tier_for
        assert score_tier_for(30) == "low"
        assert score_tier_for(0) == "low"

    def test_same_city_high_score(self):
        from modules.matching.scoring import compute_score
        user = {"city": "Hồ Chí Minh", "gender": "male", "interested_in": "female",
                "dating_goal": "serious", "age": 28, "hobbies": ["cà phê", "sách"],
                "preferences": {"preferred_age_min": 22, "preferred_age_max": 35}}
        cand = {"city": "Hồ Chí Minh", "gender": "female", "interested_in": "male",
                "dating_goal": "serious", "age": 26, "hobbies": ["cà phê", "yoga"],
                "preferences": {"preferred_age_min": 25, "preferred_age_max": 35}}
        score, reasons, tier = compute_score(user, cand)
        assert score > 60
        assert "location_nearby" in reasons or "same_dating_goal" in reasons

    def test_gender_mismatch_rejected(self):
        from modules.matching.scoring import compute_score
        user = {"city": "HN", "gender": "male", "interested_in": "female",
                "dating_goal": "serious", "age": 28}
        cand = {"city": "HN", "gender": "male", "interested_in": "male",
                "dating_goal": "serious", "age": 26}
        score, reasons, tier = compute_score(user, cand)
        assert score == 0
        assert "gender_mismatch" in reasons

    def test_age_out_of_range(self):
        from modules.matching.scoring import compute_score
        user = {"city": "HN", "gender": "male", "interested_in": "female",
                "dating_goal": "serious", "age": 28,
                "preferences": {"preferred_age_min": 25, "preferred_age_max": 30}}
        cand = {"city": "HN", "gender": "female", "interested_in": "male",
                "dating_goal": "serious", "age": 40,
                "preferences": {"preferred_age_min": 20, "preferred_age_max": 40}}
        # User's age (28) is within candidate's range (20-40).
        # Candidate's age (40) is OUTSIDE user's range (25-30). Should be rejected.
        score, reasons, tier = compute_score(user, cand)
        assert score == 0
        assert "age_out_of_range" in reasons

    def test_haversine(self):
        from modules.matching.scoring import _haversine
        # HCM -> HN ≈ 1140 km
        dist = _haversine(10.8231, 106.6297, 21.0285, 105.8542)
        assert 1000 < dist < 1300

    def test_cosine_similarity(self):
        from modules.matching.scoring import _cosine_similarity
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
