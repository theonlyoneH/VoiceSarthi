"""WebSocket connection manager for HUD and Supervisor updates."""
import asyncio
import json
import logging
from fastapi import WebSocket
from typing import Dict, List

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for operators and supervisors."""

    def __init__(self):
        # operator HUD connections: call_sid → [ws]
        self.operator_connections: Dict[str, List[WebSocket]] = {}
        # supervisor connections: helpline_id → [ws]
        self.supervisor_connections: Dict[str, List[WebSocket]] = {}

    async def connect_operator(self, call_sid: str, ws: WebSocket):
        await ws.accept()
        self.operator_connections.setdefault(call_sid, []).append(ws)
        logger.info(f"Operator connected for call {call_sid}")

    async def disconnect_operator(self, call_sid: str, ws: WebSocket):
        connections = self.operator_connections.get(call_sid, [])
        if ws in connections:
            connections.remove(ws)
        logger.info(f"Operator disconnected from call {call_sid}")

    async def connect_supervisor(self, helpline_id: str, ws: WebSocket):
        await ws.accept()
        self.supervisor_connections.setdefault(helpline_id, []).append(ws)
        logger.info(f"Supervisor connected for helpline {helpline_id}")

    async def disconnect_supervisor(self, helpline_id: str, ws: WebSocket):
        connections = self.supervisor_connections.get(helpline_id, [])
        if ws in connections:
            connections.remove(ws)

    async def push_to_operator(self, call_sid: str, data: dict):
        """Push a JSON update to all operator HUD connections for this call."""
        connections = self.operator_connections.get(call_sid, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.operator_connections.get(call_sid, []).remove(ws)

    async def push_to_supervisors(self, helpline_id: str, data: dict):
        """Push a JSON update to all supervisor connections for this helpline."""
        connections = self.supervisor_connections.get(helpline_id, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.supervisor_connections.get(helpline_id, []).remove(ws)

    async def broadcast_risk_update(self, call_sid: str, helpline_id: str, event: dict):
        """Broadcast a risk update to both operator HUD and supervisors."""
        await self.push_to_operator(call_sid, event)
        await self.push_to_supervisors(helpline_id, {
            "type": "call.risk_update",
            "call_sid": call_sid,
            **event
        })


ws_manager = ConnectionManager()
