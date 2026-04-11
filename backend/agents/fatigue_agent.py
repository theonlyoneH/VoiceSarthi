"""OperatorFatigueAgent — Monitors operator stress level based on shift metadata.
Follows PRD.md F3 (OperatorFatigueAgent).
Output: operator stress score + micro-break recommendation.
"""
from .base import BaseAgent, AgentAssessment
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

SHIFT_FATIGUE_HOURS = [
    (0, 2, 0),    # First 2 hours: low fatigue
    (2, 4, 2),    # 2-4 hours: mild
    (4, 6, 4),    # 4-6 hours: moderate
    (6, 8, 6),    # 6-8 hours: high
    (8, 99, 8),   # 8+ hours: very high
]

HIGH_CALL_INTENSITY_THRESHOLD = 3  # consecutive HIGH/CRITICAL calls


class OperatorFatigueAgent(BaseAgent):
    agent_id = "fatigue"
    subscriptions = ["call.state_change", "meta.risk_update"]

    # Note: This agent tracks operator state, not call state
    # keyed by operator_id rather than call_sid

    async def on_event(self, event: dict) -> Optional[AgentAssessment]:
        call_sid = event.get("call_sid")
        if not call_sid:
            return None

        state = self.get_state(call_sid)

        if event["type"] == "call.state_change":
            return await self._process_state_change(call_sid, event, state)
        elif event["type"] == "meta.risk_update":
            return await self._process_risk_update(call_sid, event, state)

        return None

    async def _process_state_change(
        self, call_sid: str, event: dict, state: dict
    ) -> Optional[AgentAssessment]:
        new_state = event.get("new_state", "")
        if new_state == "answered":
            state["call_start"] = datetime.now(timezone.utc).isoformat()
        return None

    async def _process_risk_update(
        self, call_sid: str, event: dict, state: dict
    ) -> Optional[AgentAssessment]:
        risk_level = event.get("risk_level", "UNKNOWN")

        state.setdefault("high_risk_streak", 0)
        state.setdefault("shift_start", datetime.now(timezone.utc).isoformat())
        state.setdefault("micro_break_recommended", False)

        # Track consecutive high-risk calls
        if risk_level in ("HIGH", "CRITICAL"):
            state["high_risk_streak"] += 1
        else:
            state["high_risk_streak"] = max(0, state["high_risk_streak"] - 1)

        # Calculate shift duration
        try:
            shift_start = datetime.fromisoformat(state["shift_start"])
            shift_hours = (datetime.now(timezone.utc) - shift_start).total_seconds() / 3600
        except Exception:
            shift_hours = 0.0

        # Determine fatigue score from shift duration
        fatigue_score = 0
        for (lo, hi, score) in SHIFT_FATIGUE_HOURS:
            if lo <= shift_hours < hi:
                fatigue_score = score
                break

        # Increase for high-risk streak
        if state["high_risk_streak"] >= HIGH_CALL_INTENSITY_THRESHOLD:
            fatigue_score = min(10, fatigue_score + 2)

        flags = []
        explanation_parts = [f"shift: {shift_hours:.1f}h"]

        if shift_hours >= 6:
            flags.append("LONG_SHIFT")
            explanation_parts.append("long shift detected")

        if state["high_risk_streak"] >= HIGH_CALL_INTENSITY_THRESHOLD:
            flags.append("HIGH_CALL_INTENSITY")
            explanation_parts.append(f"{state['high_risk_streak']} consecutive high-risk calls")

        if fatigue_score >= 6:
            state["micro_break_recommended"] = True
            flags.append("MICRO_BREAK_RECOMMENDED")
            explanation_parts.append("consider micro-break after this call")

        assessment = AgentAssessment(
            agent_id=self.agent_id,
            risk_score=min(fatigue_score, 10),
            confidence=0.7,
            explanation=", ".join(explanation_parts),
            dimensions={
                "shift_hours": round(shift_hours, 1),
                "high_risk_streak": state["high_risk_streak"],
                "micro_break_recommended": state["micro_break_recommended"]
            },
            flags=flags
        )
        await self.emit(call_sid, assessment)
        return assessment
