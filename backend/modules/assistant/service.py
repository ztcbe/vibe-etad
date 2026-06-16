"""Assistant service — session management + ADK agent orchestration."""
import json
import logging
import uuid
from datetime import datetime, timezone

from google.adk import Runner
from google.genai.types import Content, Part
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.assistant import AssistantSession, AssistantMessage
from db.models.audit import AIToolLog
from modules.assistant.agents import build_coordinator_agent
from modules.assistant.session import get_session_service
from modules.assistant.tools import current_db, current_user_id, current_session_id
from modules.assistant.schemas import ChatRequest, ChatResponse, ActionPayload
from common.errors import NotFoundError
from common.enums import AssistantRole

logger = logging.getLogger(__name__)


async def create_session(db: AsyncSession, user_id: uuid.UUID, title: str | None = None) -> AssistantSession:
    session = AssistantSession(
        user_id=user_id,
        title=title or "New Chat",
        state={"onboarding_step": None, "pending_confirmation": None, "active_match_id": None},
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(db: AsyncSession, user_id: uuid.UUID) -> list[AssistantSession]:
    result = await db.execute(
        select(AssistantSession)
        .where(AssistantSession.user_id == user_id)
        .order_by(AssistantSession.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_session(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> AssistantSession:
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundError(code="SESSION_NOT_FOUND", message="Session not found")
    return session


async def get_messages(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> list[AssistantMessage]:
    # Verify ownership
    await get_session(db, session_id, user_id)
    result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session_id)
        .order_by(AssistantMessage.created_at.asc())
    )
    return list(result.scalars().all())


async def chat(db: AsyncSession, user_id: uuid.UUID, data: ChatRequest) -> ChatResponse:
    """Process a chat message through the AI assistant.

    This is the core function that:
    1. Loads/creates the assistant session
    2. Sets up contextvars for tool access
    3. Runs the ADK agent
    4. Persists messages and tool logs
    5. Returns the AI response with actions
    """
    session = await get_session(db, data.session_id, user_id)

    # Set context for tool access
    token_db = current_db.set(db)
    token_user = current_user_id.set(str(user_id))
    token_session = current_session_id.set(str(session.id))

    try:
        # Build the agent (fresh per request for tool state)
        agent = build_coordinator_agent()

        # Use shared DatabaseSessionService (persistent, survives restarts)
        session_service = get_session_service()
        adk_session = await session_service.get_session(
            app_name="zvibe",
            user_id=str(user_id),
            session_id=str(session.id),
        )
        if adk_session is None:
            adk_session = await session_service.create_session(
                app_name="zvibe",
                user_id=str(user_id),
                session_id=str(session.id),
            )

        # Save user message to DB
        user_msg = AssistantMessage(
            session_id=session.id,
            user_id=user_id,
            role=AssistantRole.USER,
            content=data.message,
            metadata=data.context or {},
        )
        db.add(user_msg)
        await db.commit()

        # Run the agent
        runner = Runner(
            agent=agent,
            app_name="zvibe",
            session_service=session_service,
        )

        ai_text = ""
        actions = []
        requires_confirmation = False
        confirmation_action = None

        tool_logs = []

        async for event in runner.run_async(
            user_id=str(user_id),
            session_id=str(session.id),
            new_message=Content(role="user", parts=[Part(text=data.message)]),
        ):
            # Collect events from the agent
            if event.content and event.content.parts:
                for part in event.content.parts:
                    # Skip thinking/reasoning parts (Qwen, DeepSeek-R1, etc.)
                    # litellm parses  response blocks into parts with thought=True
                    is_thought = getattr(part, 'thought', False)
                    if part.text and not is_thought:
                        ai_text += part.text
                    if part.function_call:
                        fc = part.function_call
                        tool_logs.append({
                            "tool_name": fc.name,
                            "tool_args": fc.args,
                            "status": "called",
                        })
                    if part.function_response:
                        for log_entry in tool_logs:
                            if log_entry.get("status") == "called":
                                log_entry["status"] = "success"
                                log_entry["result_summary"] = str(part.function_response.response)[:500]
                                break

        # Strip thinking blocks (Qwen/DeepSeek style) before presenting to user
        ai_text = _strip_thinking(ai_text)

        # Analyze AI response for actions and confirmation
        actions, requires_confirmation, confirmation_action = _parse_ai_actions(ai_text, tool_logs)

        # Check for pending confirmation in session state
        state = session.state or {}
        if state.get("pending_confirmation"):
            # User message might be a confirmation response
            if _is_confirmation(data.message):
                pending = state["pending_confirmation"]
                # Execute the pending action — handled by agent in next turn
                requires_confirmation = False

        # Save AI response to DB
        ai_msg = AssistantMessage(
            session_id=session.id,
            user_id=user_id,
            role=AssistantRole.ASSISTANT,
            content=ai_text,
            metadata={
                "actions": [a.model_dump() for a in actions],
                "requires_confirmation": requires_confirmation,
                "tool_calls": tool_logs,
            },
        )
        db.add(ai_msg)

        # Save tool logs
        for log_entry in tool_logs:
            audit = AIToolLog(
                user_id=user_id,
                session_id=session.id,
                agent_name="CoordinatorAgent",
                tool_name=log_entry["tool_name"],
                input_sanitized=log_entry.get("tool_args", {}),
                output_summary={"summary": log_entry.get("result_summary", "")},
                status=log_entry.get("status", "unknown"),
            )
            db.add(audit)

        # Update session timestamp
        session.updated_at = datetime.now(timezone.utc)

        await db.commit()

        return ChatResponse(
            message=ai_text or "Xin lỗi, mình chưa xử lý được yêu cầu này. Bạn thử lại nhé!",
            actions=actions if actions else None,
            requires_confirmation=requires_confirmation,
            confirmation_action=confirmation_action,
        )

    except Exception:
        logger.exception("Assistant chat failed for user=%s session=%s", user_id, session.id)
        await db.rollback()
        return ChatResponse(
            message="Xin lỗi, có lỗi xảy ra khi xử lý yêu cầu của bạn. Vui lòng thử lại sau.",
            actions=None,
            requires_confirmation=False,
            confirmation_action=None,
        )

    finally:
        # Reset contextvars
        current_db.reset(token_db)
        current_user_id.reset(token_user)
        current_session_id.reset(token_session)


def _parse_ai_actions(text: str, tool_logs: list[dict]) -> tuple[list[ActionPayload], bool, dict | None]:
    """Parse the AI response text and tool calls to extract UI actions.

    Returns (actions, requires_confirmation, confirmation_action).
    """
    actions = []
    requires_confirmation = False
    confirmation_action = None

    # Check if profile completeness tool was called — suggest profile card
    for log in tool_logs:
        if log["tool_name"] == "calculate_profile_completeness":
            actions.append(ActionPayload(type="quick_actions", payload={
                "actions": ["search_candidates", "view_profile", "list_matches"],
            }))

        if log["tool_name"] == "update_my_profile":
            actions.append(ActionPayload(type="profile_summary_card", payload={
                "completeness": None,  # Will be populated from tool result
            }))

    # Check for confirmation patterns in text
    lower = text.lower()
    if any(phrase in lower for phrase in ["bạn có muốn", "xác nhận", "đồng ý", "chắc chắn"]):
        requires_confirmation = True
        # Try to extract confirmation action from context
        if "thích" in lower:
            confirmation_action = {"tool_name": "like_candidate", "tool_args": {}}
        elif "unmatch" in lower or "hủy match" in lower:
            confirmation_action = {"tool_name": "unmatch_user", "tool_args": {}}

    return actions, requires_confirmation, confirmation_action


def _strip_thinking(text: str) -> str:
    """Remove thinking/reasoning blocks from model output (fallback).

    Primary filtering happens in the event loop via part.thought check.
    This handles cases where the model embeds thinking as raw XML tags
    in the text stream (some Qwen/DeepSeek deployments).

    Uses XML-style angle-bracket tags: <think>, <thinking>, <thought>.
    """
    import re

    for tag in ("think", "thinking", "thought"):
        text = re.sub(
            rf"<{tag}>.*?</{tag}>", "", text,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

def _is_confirmation(message: str) -> bool:
    """Check if the user message is a confirmation."""
    lower = message.lower()
    confirm_phrases = ["đúng vậy", "đồng ý", "ok", "được", "có", "chắc chắn", "yes", "đúng", "làm đi", "thích luôn"]
    return any(phrase in lower for phrase in confirm_phrases)


async def mark_messages_read(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> int:
    """Mark all unread assistant messages in a session as read. Returns count."""
    from sqlalchemy import update
    stmt = (
        update(AssistantMessage)
        .where(
            AssistantMessage.session_id == session_id,
            AssistantMessage.user_id == user_id,
            AssistantMessage.role == AssistantRole.ASSISTANT,
            AssistantMessage.is_read == False,
        )
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Count unread assistant messages across all sessions."""
    result = await db.execute(
        select(func.count(AssistantMessage.id)).where(
            AssistantMessage.user_id == user_id,
            AssistantMessage.role == AssistantRole.ASSISTANT,
            AssistantMessage.is_read == False,
        )
    )
    return result.scalar() or 0
