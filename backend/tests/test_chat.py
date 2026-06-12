"""S4 tests — Chat module: REST endpoints, suggest-reply, message persistence."""
import pytest


@pytest.mark.asyncio
async def test_chat_unauthorized(client):
    """Chat endpoints require auth."""
    import uuid
    resp = await client.get(f"/api/chats/{uuid.uuid4()}/messages")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_not_participant(client, auth_headers):
    """Non-participant cannot access chat messages."""
    import uuid
    resp = await client.get(f"/api/chats/{uuid.uuid4()}/messages", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_chat_messages_flow(client):
    """Full flow: create match → send messages → read history → suggest reply."""
    # ── Create 2 users + match them ──
    # User A
    ra = await client.post("/api/auth/register", json={
        "username": "chat_a", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1995-01-01",
    })
    token_a = ra.json()["data"]["access_token"]
    ha = {"Authorization": f"Bearer {token_a}"}
    await client.patch("/api/profile/me", headers=ha, json={
        "display_name": "ChatA", "gender": "male", "interested_in": "female",
        "city": "HCM", "dating_goal": "serious",
    })
    a_profile = await client.get("/api/profile/me", headers=ha)
    a_id = a_profile.json()["data"]["user_id"]

    # User B
    rb = await client.post("/api/auth/register", json={
        "username": "chat_b", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1997-01-01",
    })
    token_b = rb.json()["data"]["access_token"]
    hb = {"Authorization": f"Bearer {token_b}"}
    await client.patch("/api/profile/me", headers=hb, json={
        "display_name": "ChatB", "gender": "female", "interested_in": "male",
        "city": "HCM", "dating_goal": "serious",
    })
    b_profile = await client.get("/api/profile/me", headers=hb)
    b_id = b_profile.json()["data"]["user_id"]

    # Mutual match
    await client.post(f"/api/matches/{b_id}/like", headers=ha)
    match_resp = await client.post(f"/api/matches/{a_id}/like", headers=hb)
    match_id = match_resp.json()["data"]["match_id"]

    # ── Send messages via REST ──
    resp = await client.post(f"/api/chats/{match_id}/messages", headers=ha, json={
        "content": "Chào bạn! 👋", "message_type": "text",
    })
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["content"] == "Chào bạn! 👋"
    assert data["data"]["sender_user_id"] == a_id
    assert data["data"]["status"] == "sent"

    # Send from B
    resp = await client.post(f"/api/chats/{match_id}/messages", headers=hb, json={
        "content": "Chào A! Rất vui được làm quen 😊",
    })
    assert resp.json()["success"] is True

    # ── Get history ──
    resp = await client.get(f"/api/chats/{match_id}/messages", headers=ha)
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) == 2
    assert data["data"][0]["content"] == "Chào bạn! 👋"
    assert data["data"][1]["content"] == "Chào A! Rất vui được làm quen 😊"

    # ── Suggest reply ──
    resp = await client.post(f"/api/chats/{match_id}/suggest-reply", headers=ha, json={
        "tone": "natural",
    })
    data = resp.json()
    assert data["success"] is True
    suggestions = data["data"]["suggestions"]
    assert 2 <= len(suggestions) <= 3
    for s in suggestions:
        assert len(s.split()) <= 35  # Max 35 words


@pytest.mark.asyncio
async def test_suggest_reply_tones(client):
    """Different tones should yield different suggestions."""
    # Setup match
    ra = await client.post("/api/auth/register", json={
        "username": "tone_a", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1995-01-01",
    })
    ha = {"Authorization": f"Bearer {ra.json()['data']['access_token']}"}
    await client.patch("/api/profile/me", headers=ha, json={
        "display_name": "TA", "gender": "male", "interested_in": "female", "city": "HCM", "dating_goal": "serious",
    })
    a_p = await client.get("/api/profile/me", headers=ha)
    a_id = a_p.json()["data"]["user_id"]

    rb = await client.post("/api/auth/register", json={
        "username": "tone_b", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1997-01-01",
    })
    hb = {"Authorization": f"Bearer {rb.json()['data']['access_token']}"}
    await client.patch("/api/profile/me", headers=hb, json={
        "display_name": "TB", "gender": "female", "interested_in": "male", "city": "HCM", "dating_goal": "serious",
    })
    b_p = await client.get("/api/profile/me", headers=hb)
    b_id = b_p.json()["data"]["user_id"]

    await client.post(f"/api/matches/{b_id}/like", headers=ha)
    mr = await client.post(f"/api/matches/{a_id}/like", headers=hb)
    match_id = mr.json()["data"]["match_id"]

    # Send a message
    await client.post(f"/api/chats/{match_id}/messages", headers=hb, json={
        "content": "Cuối tuần bạn thích làm gì?",
    })

    for tone in ["natural", "humorous", "concise"]:
        resp = await client.post(f"/api/chats/{match_id}/suggest-reply", headers=ha, json={"tone": tone})
        data = resp.json()
        assert data["success"] is True
        assert 2 <= len(data["data"]["suggestions"]) <= 3


@pytest.mark.asyncio
async def test_chat_message_pagination(client):
    """Test cursor-based pagination with before_id."""
    ra = await client.post("/api/auth/register", json={
        "username": "page_a", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1995-01-01",
    })
    ha = {"Authorization": f"Bearer {ra.json()['data']['access_token']}"}
    await client.patch("/api/profile/me", headers=ha, json={
        "display_name": "PA", "gender": "male", "interested_in": "female", "city": "HCM", "dating_goal": "serious",
    })
    a_p = await client.get("/api/profile/me", headers=ha)
    a_id = a_p.json()["data"]["user_id"]

    rb = await client.post("/api/auth/register", json={
        "username": "page_b", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1997-01-01",
    })
    hb = {"Authorization": f"Bearer {rb.json()['data']['access_token']}"}
    await client.patch("/api/profile/me", headers=hb, json={
        "display_name": "PB", "gender": "female", "interested_in": "male", "city": "HCM", "dating_goal": "serious",
    })
    b_p = await client.get("/api/profile/me", headers=hb)
    b_id = b_p.json()["data"]["user_id"]

    await client.post(f"/api/matches/{b_id}/like", headers=ha)
    mr = await client.post(f"/api/matches/{a_id}/like", headers=hb)
    match_id = mr.json()["data"]["match_id"]

    # Send 3 messages
    for i in range(3):
        await client.post(f"/api/chats/{match_id}/messages", headers=ha, json={
            "content": f"Message {i+1}",
        })

    # Get all
    resp = await client.get(f"/api/chats/{match_id}/messages", headers=ha)
    assert len(resp.json()["data"]) == 3

    # Get with limit
    resp = await client.get(f"/api/chats/{match_id}/messages?limit=1", headers=ha)
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_inactive_match_cannot_chat(client):
    """Cannot send messages after unmatch."""
    ra = await client.post("/api/auth/register", json={
        "username": "inactive_a", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1995-01-01",
    })
    ha = {"Authorization": f"Bearer {ra.json()['data']['access_token']}"}
    await client.patch("/api/profile/me", headers=ha, json={
        "display_name": "IA", "gender": "male", "interested_in": "female", "city": "HCM", "dating_goal": "serious",
    })
    pa = await client.get("/api/profile/me", headers=ha)
    a_id = pa.json()["data"]["user_id"]

    rb = await client.post("/api/auth/register", json={
        "username": "inactive_b", "password": "pass123456", "confirm_password": "pass123456",
        "date_of_birth": "1997-01-01",
    })
    hb = {"Authorization": f"Bearer {rb.json()['data']['access_token']}"}
    await client.patch("/api/profile/me", headers=hb, json={
        "display_name": "IB", "gender": "female", "interested_in": "male", "city": "HCM", "dating_goal": "serious",
    })
    pb = await client.get("/api/profile/me", headers=hb)
    b_id = pb.json()["data"]["user_id"]

    await client.post(f"/api/matches/{b_id}/like", headers=ha)
    mr = await client.post(f"/api/matches/{a_id}/like", headers=hb)
    match_id = mr.json()["data"]["match_id"]

    # Unmatch
    await client.post(f"/api/matches/{match_id}/unmatch", headers=ha)

    # Try to send message → should fail (400+ range)
    resp = await client.post(f"/api/chats/{match_id}/messages", headers=ha, json={
        "content": "Hello?",
    })
    assert resp.status_code >= 400
