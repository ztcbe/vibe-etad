"""Global per-user WebSocket for push notifications."""
import json
import logging
import uuid

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# user_id → set of WebSocket connections
_active_connections: dict[uuid.UUID, set[WebSocket]] = {}


async def notifications_websocket(websocket: WebSocket, user_id: uuid.UUID) -> None:
    """Handle a global notification WebSocket connection for a user."""
    await websocket.accept()
    if user_id not in _active_connections:
        _active_connections[user_id] = set()
    _active_connections[user_id].add(websocket)

    try:
        while True:
            # Keep connection alive; client can send pings or mark_read actions
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                if data.get("action") == "ping":
                    await websocket.send_json({"event": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.debug("Notification WS disconnected for user %s", user_id)
    except Exception:
        logger.exception("Notification WS error for user %s", user_id)
    finally:
        conns = _active_connections.get(user_id, set())
        conns.discard(websocket)
        if not conns:
            _active_connections.pop(user_id, None)


async def push_to_user(user_id: uuid.UUID, data: dict) -> bool:
    """Send a JSON message to all WS connections for a user. Returns True if sent."""
    connections = _active_connections.get(user_id, set())
    if not connections:
        return False
    sent = False
    dead: set[WebSocket] = set()
    for ws in connections:
        try:
            await ws.send_json(data)
            sent = True
        except Exception:
            logger.debug("Dead notification WS connection for user %s", user_id)
            dead.add(ws)
    if dead:
        connections.difference_update(dead)
        if not connections:
            _active_connections.pop(user_id, None)
    return sent


def is_user_online(user_id: uuid.UUID) -> bool:
    return bool(_active_connections.get(user_id))
