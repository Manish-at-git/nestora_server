"""Reusable authenticated WebSocket transport for targeted portal events."""

from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.security import utc_now
from app.db.session import session_factory
from app.modules.auth.service import AuthService


MessageHandler = Callable[[WebSocket, dict[str, Any]], Awaitable[None]]


class WebSocketManager:
    """Keep connection lifecycle and message delivery in one reusable place."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, account_id: str) -> None:
        await websocket.accept()
        self._connections[account_id].add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        for account_id, connections in tuple(self._connections.items()):
            connections.discard(websocket)
            if not connections:
                self._connections.pop(account_id, None)

    async def send(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        await websocket.send_json(message)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send one event to every active connection."""
        for websocket in self._all_connections():
            try:
                await self.send(websocket, message)
            except Exception:
                self.disconnect(websocket)

    async def send_to_accounts(
        self,
        account_ids: Iterable[str],
        message: dict[str, Any],
    ) -> None:
        """Deliver one event only to authenticated accounts selected by the domain."""
        sockets = {
            websocket
            for account_id in set(account_ids)
            for websocket in self._connections.get(account_id, ())
        }
        for websocket in sockets:
            try:
                await self.send(websocket, message)
            except Exception:
                self.disconnect(websocket)

    def _all_connections(self) -> set[WebSocket]:
        return {
            websocket
            for connections in self._connections.values()
            for websocket in connections
        }


manager = WebSocketManager()
router = APIRouter(tags=["Realtime"])


async def _authenticate(websocket: WebSocket) -> str:
    """Resolve the existing HttpOnly session cookie before accepting socket messages."""
    settings = get_settings()
    raw_token = websocket.cookies.get(settings.session_cookie_name)
    async with session_factory() as session:
        auth_session = await AuthService(session, settings).get_authenticated_session(raw_token)
        return auth_session.account.id


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Authenticate a browser socket and echo a single sample message for connectivity checks."""
    try:
        account_id = await _authenticate(websocket)
    except Exception:
        await websocket.close(code=1008, reason="Authentication required")
        return

    await manager.connect(websocket, account_id)
    try:
        await manager.send(
            websocket,
            {
                "type": "socket.connected",
                "message": "Realtime connection established",
                "account_id": account_id,
            },
        )
        while True:
            payload = await websocket.receive_json()
            if payload.get("type") == "client.sample":
                await manager.send(
                    websocket,
                    {
                        "type": "server.sample",
                        "message": "Sample message received by the server",
                        "received_at": utc_now().isoformat(),
                    },
                )
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
