"""WebSocket handler for 1-1 chat — /ws/chats/{match_id}.

Events (v0.2 §4):
  Client→Server: send_message, typing_started, typing_stopped, mark_read
  Server→Client: message_created, typing_started, typing_stopped,
                  message_delivered, message_read, mutual_match_created,
                  match_unavailable, error
"""
import json
import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_ws
from db.models.user import User
from db.models.matching import Match
from db.models.chat import ChatMessage
from db.session import get_session
from modules.chat import service
from common.enums import MatchStatus

logger = logging.getLogger(__name__)

# In-memory connection registry: match_id -> set of (user_id, websocket)
_active_connections: dict[uuid.UUID, set[tuple[uuid.UUID, WebSocket]]] = {}


async def chat_websocket(
    websocket: WebSocket,
    match_id: uuid.UUID,
    user: User,
    db: AsyncSession,
):
    """Main WebSocket handler for a chat connection."""
    # Verify match participation
    match = await db.get(Match, match_id)
    if match is None or (match.user_a_id != user.id and match.user_b_id != user.id):
        await websocket.close(code=4003, reason="Not a match participant")
        return

    if match.status != MatchStatus.ACTIVE:
        await websocket.close(code=4003, reason="Match is no longer active")
        return

    await websocket.accept()

    # Register connection
    if match_id not in _active_connections:
        _active_connections[match_id] = set()
    _active_connections[match_id].add((user.id, websocket))

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            action = data.get("action", "")

            if action == "send_message":
                await _handle_send_message(websocket, user, match_id, data, db)
            elif action == "typing_started":
                await _broadcast_to_others(match_id, user.id, {
                    "event": "typing_started",
                    "data": {"match_id": str(match_id), "user_id": str(user.id)},
                })
            elif action == "typing_stopped":
                await _broadcast_to_others(match_id, user.id, {
                    "event": "typing_stopped",
                    "data": {"match_id": str(match_id), "user_id": str(user.id)},
                })
            elif action == "mark_read":
                msg_ids = [uuid.UUID(mid) for mid in data.get("message_ids", [])]
                await service.mark_read(db, user.id, match_id, msg_ids)
                # Notify sender that messages were read
                await _broadcast_to_others(match_id, user.id, {
                    "event": "message_read",
                    "data": {
                        "match_id": str(match_id),
                        "message_ids": [str(mid) for mid in msg_ids],
                        "reader_user_id": str(user.id),
                    },
                })

    except WebSocketDisconnect:
        logger.info(f"User {user.id} disconnected from match {match_id}")
    except Exception as e:
        logger.error(f"WS error in match {match_id}: {e}")
        try:
            await websocket.send_json({
                "event": "error",
                "data": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
            })
        except Exception:
            pass
    finally:
        # Unregister connection
        if match_id in _active_connections:
            _active_connections[match_id].discard((user.id, websocket))
            if not _active_connections[match_id]:
                del _active_connections[match_id]


async def _handle_send_message(
    websocket: WebSocket,
    user: User,
    match_id: uuid.UUID,
    data: dict,
    db: AsyncSession,
):
    """Handle send_message action."""
    content = data.get("content", "").strip()
    if not content:
        await _send_error(websocket, "EMPTY_MESSAGE", "Message cannot be empty")
        return

    if len(content) > 2000:
        await _send_error(websocket, "MESSAGE_TOO_LONG", "Message too long (max 2000 chars)")
        return

    try:
        msg = await service.send_message(
            db, user.id, match_id, content,
            data.get("message_type", "text"),
        )

        payload = {
            "event": "message_created",
            "data": {
                "id": str(msg.id),
                "match_id": str(match_id),
                "sender_user_id": str(user.id),
                "content": msg.content,
                "message_type": msg.message_type.value if hasattr(msg.message_type, 'value') else msg.message_type,
                "status": msg.status.value if hasattr(msg.status, 'value') else msg.status,
                "created_at": msg.created_at.isoformat(),
            },
        }

        # Send to the sender (echo)
        await websocket.send_json(payload)

        # Broadcast to the other user in this match
        await _broadcast_to_others(match_id, user.id, payload)

    except Exception as e:
        await _send_error(websocket, "SEND_FAILED", str(e))


async def _broadcast_to_others(match_id: uuid.UUID, sender_user_id: uuid.UUID, payload: dict):
    """Broadcast a JSON payload to all other connected users in a match."""
    connections = _active_connections.get(match_id, set())
    for uid, ws in connections:
        if uid != sender_user_id:
            try:
                await ws.send_json(payload)
            except Exception:
                pass  # Connection might be dead


async def _send_error(websocket: WebSocket, code: str, message: str):
    try:
        await websocket.send_json({
            "event": "error",
            "data": {"code": code, "message": message},
        })
    except Exception:
        pass


# ── Notification helpers (called from outside WS, e.g., matching service) ──

async def notify_mutual_match(match_id: uuid.UUID, match_data: dict):
    """Notify both users in a match that a mutual match was created."""
    payload = {
        "event": "mutual_match_created",
        "data": {
            "match_id": str(match_id),
            "user": match_data.get("user", {}),
        },
    }
    await _broadcast_all(match_id, payload)


async def notify_match_unavailable(match_id: uuid.UUID, reason: str):
    """Notify users that a match is no longer available (unmatched/blocked/disabled)."""
    payload = {
        "event": "match_unavailable",
        "data": {
            "match_id": str(match_id),
            "reason": reason,
        },
    }
    await _broadcast_all(match_id, payload)


async def _broadcast_all(match_id: uuid.UUID, payload: dict):
    """Broadcast to all connected users in a match."""
    connections = _active_connections.get(match_id, set())
    dead = set()
    for uid, ws in connections:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add((uid, ws))
    _active_connections.get(match_id, set()).difference_update(dead)
