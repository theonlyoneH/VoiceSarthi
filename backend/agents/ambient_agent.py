"""AmbientAgent — Classifies background audio for context signals.
Follows PRD.md F3 and ARCHITECTURE.md Section 5.
Key override rule: child_crying or glass_breaking → +2 risk regardless of others.
"""
from .base import BaseAgent, AgentAssessment
from typing import Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Override sounds per ARCHITECTURE.md MetaAgent Conflict Resolution rule 5
OVERRIDE_SOUNDS = {"child_crying", "glass_breaking", "shouting_nearby"}

# Energy thresholds for background classification
CHILD_CRYING_ENERGY_RANGE = (800.0, 2500.0)   # Mid-energy, irregular peaks
SHOUTING_ENERGY_THRESHOLD = 4000.0
SILENCE_ENERGY_THRESHOLD = 100.0
TRAFFIC_ENERGY_RANGE = (300.0, 1200.0)


class AmbientAgent(BaseAgent):
    agent_id = "ambient"
    subscriptions = ["audio.features"]

    async def on_event(self, event: dict) -> Optional[AgentAssessment]:
        if event["type"] != "audio.features":
            return None

        call_sid = event["call_sid"]
        state = self.get_state(call_sid)

        energy = event.get("prosody_energy", 0.0)
        silence_ratio = event.get("silence_ratio", 0.0)

        state.setdefault("ambient_history", [])
        state.setdefault("classification_votes", {})

        # Classify ambient sound based on energy patterns
        classification = self._classify_ambient(energy, silence_ratio, state)
        state["ambient_history"].append(classification)
        if len(state["ambient_history"]) > 20:
            state["ambient_history"].pop(0)

        # Vote-based classification over last 10 readings
        recent = state["ambient_history"][-10:]
        votes = {}
        for c in recent:
            votes[c] = votes.get(c, 0) + 1
        dominant = max(votes, key=votes.get)
        state["classification_votes"] = votes

        flags = []
        risk_score = 1  # baseline — ambient alone is low risk
        explanation_parts = []
        dimensions = {
            "dominant_ambient": dominant,
            "classification_votes": votes
        }

        # Override sounds add +2 per ARCHITECTURE.md rule 5
        if dominant in OVERRIDE_SOUNDS:
            flags.append(f"AMBIENT_OVERRIDE: {dominant}")
            risk_score = max(risk_score, 6)
            explanation_parts.append(f"{dominant.replace('_', ' ')} detected — override +2 pending")
            dimensions["override_active"] = True

        elif dominant == "silence":
            risk_score = max(risk_score, 2)
            explanation_parts.append("background silence — caller may be isolated")

        elif dominant == "traffic":
            risk_score = max(risk_score, 2)
            explanation_parts.append("traffic noise — caller may be outdoors")

        elif dominant == "crying":
            risk_score = max(risk_score, 4)
            explanation_parts.append("crying detected in background")
            flags.append("AMBIENT_CRYING")

        elif dominant == "shouting":
            risk_score = max(risk_score, 5)
            explanation_parts.append("shouting detected nearby")
            flags.append("AMBIENT_SHOUTING")

        confidence = 0.65 if votes.get(dominant, 0) >= 7 else 0.45
        explanation = ", ".join(explanation_parts) if explanation_parts else "ambient: normal environment"

        assessment = AgentAssessment(
            agent_id=self.agent_id,
            risk_score=min(risk_score, 10),
            confidence=confidence,
            explanation=explanation,
            dimensions=dimensions,
            flags=flags
        )
        await self.emit(call_sid, assessment)
        return assessment

    @staticmethod
    def _classify_ambient(energy: float, silence_ratio: float, state: dict) -> str:
        """Classify ambient sound based on energy and silence patterns."""
        if silence_ratio > 0.85:
            return "silence"
        elif energy > SHOUTING_ENERGY_THRESHOLD:
            return "shouting_nearby"
        elif CHILD_CRYING_ENERGY_RANGE[0] <= energy <= CHILD_CRYING_ENERGY_RANGE[1]:
            # Irregular energy variation suggests child crying
            history = state.get("ambient_history", [])
            if len(history) >= 3:
                recent = history[-3:]
                energy_counts = {"shouting_nearby": 0, "child_crying": 0}
                for item in recent:
                    energy_counts[item] = energy_counts.get(item, 0) + 1
                if energy_counts.get("shouting_nearby", 0) >= 2:
                    return "shouting_nearby"
            return "child_crying"
        elif TRAFFIC_ENERGY_RANGE[0] <= energy < CHILD_CRYING_ENERGY_RANGE[0]:
            return "traffic"
        elif energy < SILENCE_ENERGY_THRESHOLD:
            return "silence"
        else:
            return "normal"

    async def inject_classification(self, call_sid: str, classification: str):
        """For demo/testing: directly inject an ambient classification."""
        state = self.get_state(call_sid)
        state.setdefault("ambient_history", [])
        # Inject 7 votes to make it dominant
        for _ in range(7):
            state["ambient_history"].append(classification)

        flags = [f"AMBIENT_OVERRIDE: {classification}"] if classification in OVERRIDE_SOUNDS else []
        risk_score = 6 if classification in OVERRIDE_SOUNDS else 3

        assessment = AgentAssessment(
            agent_id=self.agent_id,
            risk_score=risk_score,
            confidence=0.85,
            explanation=f"{classification.replace('_', ' ')} detected (injected)",
            dimensions={"dominant_ambient": classification, "injected": True},
            flags=flags
        )
        await self.emit(call_sid, assessment)
        return assessment
