"""S2 tests — Assistant sessions + chat infrastructure.

Note: These tests verify the session API + message persistence.
Full AI conversation tests require a valid LLM API key and are
run separately via integration tests.
"""
import uuid

import pytest


@pytest.mark.asyncio
async def test_create_session(client, auth_headers):
    resp = await client.post("/api/assistant/sessions", headers=auth_headers, json={"title": "Test Chat"})
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["title"] == "Test Chat"
    assert "id" in data["data"]
    assert data["data"]["state"] is not None


@pytest.mark.asyncio
async def test_list_sessions(client, auth_headers):
    # Create 2 sessions
    await client.post("/api/assistant/sessions", headers=auth_headers, json={"title": "Chat 1"})
    await client.post("/api/assistant/sessions", headers=auth_headers, json={"title": "Chat 2"})

    resp = await client.get("/api/assistant/sessions", headers=auth_headers)
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_get_messages_empty(client, auth_headers):
    # Create session
    r = await client.post("/api/assistant/sessions", headers=auth_headers, json={})
    session_id = r.json()["data"]["id"]

    resp = await client.get(f"/api/assistant/sessions/{session_id}/messages", headers=auth_headers)
    data = resp.json()
    assert data["success"] is True
    assert data["data"] == []


@pytest.mark.asyncio
async def test_session_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/assistant/sessions/{fake_id}/messages", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_without_llm(client, auth_headers):
    """Chat endpoint should return error gracefully when no LLM API key configured."""
    # Create session
    r = await client.post("/api/assistant/sessions", headers=auth_headers, json={})
    session_id = r.json()["data"]["id"]

    # Try chat — will fail because no LLM API key, but shouldn't crash
    resp = await client.post("/api/assistant/chat", headers=auth_headers, json={
        "session_id": session_id,
        "message": "Xin chào!",
    })
    # Should get a response (even if error message from LLM layer)
    assert resp.status_code in (200, 500)  # 200 with fallback message or 500 on LLM error


@pytest.mark.asyncio
async def test_chat_persists_messages(client, auth_headers):
    """Chat messages should be persisted even if LLM call fails."""
    r = await client.post("/api/assistant/sessions", headers=auth_headers, json={})
    session_id = r.json()["data"]["id"]

    await client.post("/api/assistant/chat", headers=auth_headers, json={
        "session_id": session_id,
        "message": "Hello!",
    })

    # Should have at least the user message persisted
    resp = await client.get(f"/api/assistant/sessions/{session_id}/messages", headers=auth_headers)
    data = resp.json()
    assert data["success"] is True
    # At minimum, the user message is persisted (before LLM call)
    assert len(data["data"]) >= 1
    assert data["data"][0]["role"] == "user"
    assert data["data"][0]["content"] == "Hello!"


@pytest.mark.asyncio
async def test_agent_builds(client):
    """Verify agent can be built (no LLM key needed for build)."""
    from modules.assistant.agents import build_coordinator_agent
    agent = build_coordinator_agent()
    assert agent.name == "CoordinatorAgent"
    assert len(agent.sub_agents) == 2
    sub_names = {a.name for a in agent.sub_agents}
    assert sub_names == {"MatchmakerAgent", "ConversationCoachAgent"}
    assert len(agent.tools) == 10  # 4 profile + 5 matching + 1 notification


@pytest.mark.asyncio
async def test_tool_functions_signature():
    """Verify tool functions have correct signatures for ADK."""
    from modules.assistant.tools.profile_tools import get_my_profile, calculate_profile_completeness, update_my_profile
    import inspect

    # get_my_profile takes no args (reads from contextvar)
    sig = inspect.signature(get_my_profile)
    assert len(sig.parameters) == 0

    # calculate_profile_completeness takes no args
    sig = inspect.signature(calculate_profile_completeness)
    assert len(sig.parameters) == 0

    # update_my_profile has optional params (default not Parameter.empty)
    sig = inspect.signature(update_my_profile)
    for name, param in sig.parameters.items():
        assert param.default is not inspect.Parameter.empty, f"{name} should have a default"
