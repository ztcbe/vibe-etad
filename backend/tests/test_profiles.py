import pytest


@pytest.mark.asyncio
async def test_get_my_profile(client, auth_headers):
    resp = await client.get("/api/profile/me", headers=auth_headers)
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["display_name"] is None  # empty profile


@pytest.mark.asyncio
async def test_update_profile(client, auth_headers):
    resp = await client.patch("/api/profile/me", headers=auth_headers, json={
        "display_name": "Test User",
        "gender": "male",
        "interested_in": "female",
        "city": "Hồ Chí Minh",
        "dating_goal": "serious",
    })
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["display_name"] == "Test User"
    assert data["data"]["dating_goal"] == "serious"


@pytest.mark.asyncio
async def test_completeness(client, auth_headers):
    # Update some fields first
    await client.patch("/api/profile/me", headers=auth_headers, json={
        "display_name": "Test User",
        "gender": "male",
        "interested_in": "female",
        "city": "Hồ Chí Minh",
        "dating_goal": "serious",
        "hobbies": ["Cà phê", "Đọc sách", "Trekking"],
        "personality_traits": ["thân thiện"],
        "preferences": {"preferred_age_min": 22, "preferred_age_max": 32, "preferred_distance_km": 50, "preferred_gender": "female"},
        "public_summary": "Yêu thiên nhiên và cà phê sáng sớm.",
    })

    resp = await client.get("/api/profile/me/completeness", headers=auth_headers)
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["completeness_score"] == 100
    assert len(data["data"]["missing_fields"]) == 0
    assert "breakdown" in data["data"]


@pytest.mark.asyncio
async def test_public_profile_not_found(client, auth_headers):
    import uuid
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/profile/{fake_id}", headers=auth_headers)
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "PROFILE_NOT_AVAILABLE"
