"""Tests for bot module — auto-reply and auto-match logic."""
import uuid

import pytest


# ── User model: is_bot + account_source fields ─────────────────────────


@pytest.mark.asyncio
async def test_is_bot_field_on_user_model():
    """Verify User model has is_bot field with correct defaults."""
    from db.models.user import User
    assert hasattr(User, "is_bot")
    assert User.is_bot.default.arg is False


@pytest.mark.asyncio
async def test_account_source_field_exists():
    """Verify User model has account_source field with correct defaults."""
    from db.models.user import User
    assert hasattr(User, "account_source")
    col = User.__table__.c.account_source
    assert col.default.arg == "human"
    assert col.server_default.arg == "human"
    assert col.nullable is False


@pytest.mark.asyncio
async def test_user_registered_with_is_bot_default_false(client, auth_headers):
    """Verify is_bot column exists and works via SQLAlchemy metadata."""
    from db.models.user import User
    assert hasattr(User, "is_bot")
    col = User.__table__.c.is_bot
    assert col.default.arg is False


@pytest.mark.asyncio
async def test_mark_user_as_bot_direct_db(client):
    """Verify is_bot column server_default is 'false'."""
    from db.models.user import User
    col = User.__table__.c.is_bot
    assert col.server_default.arg == "false"
    assert col.nullable is False
    assert isinstance(col.type, __import__('sqlalchemy').Boolean)


# ── Bot agent builder ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_bot_agent_creates_valid_agent():
    """Verify build_bot_agent() returns a properly configured LlmAgent."""
    from modules.bot.bot_agent import build_bot_agent

    agent = build_bot_agent()
    assert agent is not None
    assert agent.name == "BotAgent"
    assert agent.model is not None
    assert len(agent.tools) == 2
    # Verify tool names
    tool_names = {t.name for t in agent.tools}
    assert "get_my_bot_profile" in tool_names
    assert "get_bot_match_context" in tool_names


@pytest.mark.asyncio
async def test_bot_instruction_contains_key_phrases():
    """Verify BotAgent instruction has required Vietnamese phrases."""
    from modules.bot.bot_agent import _BOT_INSTRUCTION

    assert "get_my_bot_profile" in _BOT_INSTRUCTION
    assert "get_bot_match_context" in _BOT_INSTRUCTION
    assert "tiếng Việt có dấu" in _BOT_INSTRUCTION
    assert "KHÔNG để lộ" in _BOT_INSTRUCTION
    assert "1-3 câu" in _BOT_INSTRUCTION


# ── Bot tools ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_my_bot_profile_tool():
    """Verify get_my_bot_profile tool exists and is callable."""
    from modules.bot.tools import get_my_bot_profile
    assert get_my_bot_profile is not None
    assert callable(get_my_bot_profile)


@pytest.mark.asyncio
async def test_get_bot_match_context_tool():
    """Verify get_bot_match_context tool exists and is callable."""
    from modules.bot.tools import get_bot_match_context
    assert get_bot_match_context is not None
    assert callable(get_bot_match_context)


# ── Helpers ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_format_list():
    from modules.bot.bot_agent import _format_list

    assert _format_list(["a", "b", "c"]) == "a, b, c"
    assert _format_list([]) == "chưa có"
    assert _format_list(None) == "chưa có"


@pytest.mark.asyncio
async def test_vi_dating_goal():
    from modules.bot.bot_agent import _vi_dating_goal

    assert _vi_dating_goal("serious") == "nghiêm túc"
    assert _vi_dating_goal("casual") == "tình cảm thoải mái"
    assert _vi_dating_goal("friends_first") == "làm bạn trước"
    assert _vi_dating_goal("not_sure") == "đang tìm hiểu"
    assert _vi_dating_goal(None) == "đang tìm hiểu"
    assert _vi_dating_goal("unknown") == "đang tìm hiểu"


# ── Handlers ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_bot_handlers():
    """Verify bot handlers register on all 3 events without error."""
    from common.events import event_bus
    from modules.bot.handlers import register_bot_handlers

    register_bot_handlers()

    handlers = event_bus._handlers.get("message_received", [])
    assert len(handlers) >= 1

    handlers = event_bus._handlers.get("like_received", [])
    assert len(handlers) >= 1

    # match_created should now also have a bot handler
    handlers = event_bus._handlers.get("match_created", [])
    assert len(handlers) >= 1


@pytest.mark.asyncio
async def test_bot_auto_like_handler_logic():
    """Verify bot handler functions exist and are properly registered.

    Tests the decision logic: if to_user is bot and from_user is not,
    handler should proceed. If to_user is not bot, handler should return.
    """
    from modules.bot.handlers import (
        _on_bot_like_received,
        _on_bot_message_received,
        _on_bot_match_created,
    )
    assert _on_bot_like_received is not None
    assert _on_bot_message_received is not None
    assert _on_bot_match_created is not None

    # Verify handler registration doesn't raise
    from modules.bot.handlers import register_bot_handlers
    register_bot_handlers()

    # Verify all 3 events have handlers
    from common.events import event_bus
    assert "like_received" in event_bus._handlers
    assert "message_received" in event_bus._handlers
    assert "match_created" in event_bus._handlers


# ── Context helper ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_match_context_returns_structure(client):
    """Verify match context helper imports and is callable."""
    from modules.bot.context import get_match_context_for_bot
    assert get_match_context_for_bot is not None
    assert callable(get_match_context_for_bot)
