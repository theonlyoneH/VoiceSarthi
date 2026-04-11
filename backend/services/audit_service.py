"""Audit Service — Immutable AI suggestion logger.
Follows ETHICS_AND_SAFETY.md Immutable Audit Architecture.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from db.models import AISuggestion, Call

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log_suggestion(
        self,
        call_sid: str,
        suggestion_text: str,
        risk_level: str,
        risk_score: int,
        confidence: float,
        reasoning_chain: dict,
        model_version: str = "v1.0.0-fusion",
        call_minute: int | None = None,
        operator_id: str | None = None
    ) -> AISuggestion:
        """Log an AI suggestion (INSERT ONLY — immutable audit)."""
        suggestion = AISuggestion(
            call_sid=call_sid,
            suggestion_text=suggestion_text,
            risk_level=risk_level,
            risk_score=risk_score,
            confidence=confidence,
            reasoning_chain=reasoning_chain,
            model_version=model_version,
            call_minute=call_minute,
            operator_id=operator_id
        )
        self.db.add(suggestion)
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def record_operator_action(
        self,
        suggestion_id: str,
        action: str,
        operator_id: str,
        modification_text: str | None = None
    ) -> bool:
        """Record operator response (accepted/modified/rejected) to a suggestion."""
        from uuid import UUID
        try:
            suggestion = self.db.query(AISuggestion).filter(
                AISuggestion.id == UUID(suggestion_id)
            ).first()
            if not suggestion:
                return False

            suggestion.operator_action = action
            suggestion.operator_action_at = datetime.now(timezone.utc)
            suggestion.operator_id = UUID(operator_id)
            if modification_text:
                suggestion.operator_modification = modification_text

            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to record operator action: {e}")
            self.db.rollback()
            return False

    def get_call_suggestions(self, call_sid: str) -> list[dict]:
        """Get all suggestions for a call (for audit replay)."""
        suggestions = (
            self.db.query(AISuggestion)
            .filter(AISuggestion.call_sid == call_sid)
            .order_by(AISuggestion.timestamp)
            .all()
        )
        return [self._serialize(s) for s in suggestions]

    def get_risk_timeline(self, call_sid: str) -> list[dict]:
        """Get risk score timeline for a call."""
        suggestions = self.get_call_suggestions(call_sid)
        return [
            {
                "timestamp": s["timestamp"],
                "risk_level": s["risk_level"],
                "risk_score": s["risk_score"],
                "operator_action": s.get("operator_action"),
                "trigger": s.get("reasoning_chain", {}).get("explanation", "")[:100]
            }
            for s in suggestions
        ]

    @staticmethod
    def _serialize(s: AISuggestion) -> dict:
        return {
            "id": str(s.id),
            "call_sid": s.call_sid,
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            "suggestion_text": s.suggestion_text,
            "risk_level": s.risk_level,
            "risk_score": s.risk_score,
            "confidence": s.confidence,
            "reasoning_chain": s.reasoning_chain,
            "operator_action": s.operator_action,
            "operator_action_at": s.operator_action_at.isoformat() if s.operator_action_at else None,
            "operator_modification": s.operator_modification,
            "model_version": s.model_version,
            "call_minute": s.call_minute,
        }
