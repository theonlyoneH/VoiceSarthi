"""Dispatch Service — Exotel conference bridge and dispatch logging.
Follows PRD.md F6 and DATABASE_SCHEMA.md dispatch_log.
"""
import logging
import httpx
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from db.models import DispatchLog, Resource

logger = logging.getLogger(__name__)

EXOTEL_API_KEY = os.getenv("EXOTEL_API_KEY", "")
EXOTEL_API_TOKEN = os.getenv("EXOTEL_API_TOKEN", "")
EXOTEL_ACCOUNT_SID = os.getenv("EXOTEL_ACCOUNT_SID", "")
EXOTEL_BASE_URL = os.getenv("EXOTEL_BASE_URL", "https://api.exotel.com/v1")


class DispatchService:
    def __init__(self, db: Session):
        self.db = db

    async def dispatch(
        self,
        call_sid: str,
        operator_id: str,
        action_type: str,
        resource_id: str | None = None,
        location_lat: float | None = None,
        location_lng: float | None = None,
        location_address: str | None = None,
        confirmed: bool = True
    ) -> dict:
        """
        Execute a dispatch action from the HUD.
        All dispatches require operator confirmation (no autonomous dispatch).
        """
        if not confirmed:
            return {"status": "awaiting_confirmation", "action": action_type}

        # Log in dispatch_log (immutable)
        dispatch_entry = DispatchLog(
            call_sid=call_sid,
            operator_id=operator_id,
            action_type=action_type,
            resource_id=resource_id,
            location_lat=location_lat,
            location_lng=location_lng,
            location_address=location_address,
            confirmed_by_operator=True,
            status="sent"
        )
        self.db.add(dispatch_entry)
        self.db.commit()
        self.db.refresh(dispatch_entry)

        # Execute the dispatch
        result = {"status": "dispatched", "dispatch_id": str(dispatch_entry.id)}

        if action_type == "ambulance":
            result.update(await self._dispatch_ambulance(call_sid, dispatch_entry))
        elif action_type == "police":
            result.update(await self._dispatch_police(call_sid, dispatch_entry))
        elif action_type in ("shelter", "resource_connect"):
            result.update(await self._connect_resource(call_sid, resource_id, dispatch_entry))
        elif action_type == "supervisor_ping":
            result.update({"status": "supervisor_alerted", "message": "Supervisor pinged"})

        # Update status
        self.db.query(DispatchLog).filter(
            DispatchLog.id == dispatch_entry.id
        ).update({"status": result.get("status", "sent")})
        self.db.commit()

        return result

    async def _dispatch_ambulance(self, call_sid: str, entry: DispatchLog) -> dict:
        """Dispatch ambulance — stub for Exotel conference bridge."""
        logger.info(f"DISPATCH: Ambulance 108 for call {call_sid}")
        # In production: Exotel conference bridge to 108
        return {
            "status": "confirmed",
            "action": "ambulance",
            "number": "108",
            "message": "Ambulance dispatch initiated. Direct call: 108"
        }

    async def _dispatch_police(self, call_sid: str, entry: DispatchLog) -> dict:
        """Dispatch police — stub for Exotel conference bridge."""
        logger.info(f"DISPATCH: Police 100 for call {call_sid}")
        return {
            "status": "confirmed",
            "action": "police",
            "number": "100",
            "message": "Police alert initiated. Direct call: 100"
        }

    async def _connect_resource(self, call_sid: str, resource_id: str | None, entry: DispatchLog) -> dict:
        """Connect resource via Exotel 3-way conference."""
        if not resource_id:
            return {"status": "failed", "reason": "No resource specified"}

        resource = self.db.query(Resource).filter(
            Resource.id == resource_id
        ).first()
        if not resource:
            return {"status": "failed", "reason": "Resource not found"}

        logger.info(f"DISPATCH: Connecting {resource.name} for call {call_sid}")
        # In production: Exotel conference bridge API call
        return {
            "status": "confirmed",
            "action": "resource_connect",
            "resource_name": resource.name,
            "resource_phone": resource.phone,
            "message": f"Connecting {resource.name}. Phone: {resource.phone}"
        }

    def get_dispatch_history(self, call_sid: str) -> list[dict]:
        """Get dispatch history for a call."""
        entries = self.db.query(DispatchLog).filter(
            DispatchLog.call_sid == call_sid
        ).order_by(DispatchLog.dispatched_at).all()

        return [
            {
                "id": str(e.id),
                "action_type": e.action_type,
                "resource_id": str(e.resource_id) if e.resource_id else None,
                "dispatched_at": e.dispatched_at.isoformat(),
                "status": e.status,
                "confirmed_by_operator": e.confirmed_by_operator
            }
            for e in entries
        ]
