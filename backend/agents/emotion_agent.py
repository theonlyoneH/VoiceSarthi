"""EmotionAgent — Analyses audio prosody for emotional risk indicators.
Follows PRD.md F3 and ARCHITECTURE.md Section 5.
"""
from .base import BaseAgent, AgentAssessment
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Thresholds for audio prosody analysis
HIGH_ENERGY_THRESHOLD = 3000.0    # RMS energy — high = shouting/agitation
LOW_ENERGY_THRESHOLD = 200.0      # Very low = quiet/withdrawn
HIGH_SILENCE_RATIO = 0.7          # >70% silence = unresponsive (dissociation risk)
MEDIUM_SILENCE_RATIO = 0.5


class EmotionAgent(BaseAgent):
    agent_id = "emotion"
    subscriptions = ["audio.features", "stt.segment"]

    async def on_event(self, event: dict) -> Optional[AgentAssessment]:
        call_sid = event.get("call_sid")
        if not call_sid:
            return None

        state = self.get_state(call_sid)

        if event["type"] == "audio.features":
            return await self._process_audio_features(call_sid, event, state)
        elif event["type"] == "stt.segment":
            return await self._process_text_tone(call_sid, event, state)

        return None

    async def _process_audio_features(
        self, call_sid: str, event: dict, state: dict
    ) -> Optional[AgentAssessment]:
        energy = event.get("prosody_energy", 0.0)
        silence_ratio = event.get("silence_ratio", 0.0)

        state.setdefault("energy_history", [])
        state.setdefault("silence_history", [])
        state.setdefault("calm_streak", 0)
        state.setdefault("distress_score", 0)
        state.setdefault("agitation_score", 0)

        state["energy_history"].append(energy)
        state["silence_history"].append(silence_ratio)
        if len(state["energy_history"]) > 20:
            state["energy_history"].pop(0)
        if len(state["silence_history"]) > 20:
            state["silence_history"].pop(0)

        avg_energy = sum(state["energy_history"]) / len(state["energy_history"])
        avg_silence = sum(state["silence_history"]) / len(state["silence_history"])

        risk_score = 2  # baseline
        confidence = 0.7
        flags = []
        explanation_parts = []
        dimensions = {
            "energy": round(avg_energy, 2),
            "silence_ratio": round(avg_silence, 2),
        }

        # High energy = agitation/crying/shouting
        if avg_energy > HIGH_ENERGY_THRESHOLD:
            risk_score = max(risk_score, 6)
            flags.append("HIGH_AUDIO_ENERGY")
            explanation_parts.append(f"high audio energy ({avg_energy:.0f}) — possible distress")
            dimensions["agitation"] = True
        elif avg_energy < LOW_ENERGY_THRESHOLD:
            risk_score = max(risk_score, 4)
            flags.append("LOW_AUDIO_ENERGY")
            explanation_parts.append("very low audio energy — possible withdrawal")
            dimensions["withdrawn"] = True

        # High silence = unresponsive (dissociation risk)
        if avg_silence > HIGH_SILENCE_RATIO:
            risk_score = max(risk_score, 5)
            flags.append("HIGH_SILENCE_RATIO")
            explanation_parts.append(f"silence {avg_silence:.0%} — possible dissociation")
            dimensions["dissociation_risk"] = True
        elif avg_silence > MEDIUM_SILENCE_RATIO:
            risk_score = max(risk_score, 3)
            explanation_parts.append("moderate silence — caller may be processing")

        # Unusual calm check: when calm > 0.8 AND distress > 0.6 → +2
        # Proxied via: low energy after previously high energy = unsettling calm
        if len(state["energy_history"]) >= 10:
            recent_energy = sum(state["energy_history"][-5:]) / 5
            earlier_energy = sum(state["energy_history"][-10:-5]) / 5
            if earlier_energy > HIGH_ENERGY_THRESHOLD * 0.7 and recent_energy < LOW_ENERGY_THRESHOLD * 2:
                flags.append("UNUSUAL_CALM_AFTER_DISTRESS")
                risk_score = min(10, risk_score + 2)
                explanation_parts.append("unusual calm after distress pattern — risk +2")
                dimensions["unusual_calm"] = True

        state["distress_score"] = risk_score
        explanation = ", ".join(explanation_parts) if explanation_parts else "normal audio prosody"

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

    async def _process_text_tone(
        self, call_sid: str, event: dict, state: dict
    ) -> Optional[AgentAssessment]:
        """Basic text-based tone analysis as supplement to audio features."""
        text = event.get("text", "").lower()
        state.setdefault("text_distress_score", 0)

        distress_words = [
            "crying", "sobbing", "screaming", "help me", "please help",
            "i'm scared", "dar lag raha", "ro rahi", "rona aa raha"
        ]
        calm_words = ["fine", "okay", "alright", "no problem", "theek hoon"]

        flags = []
        risk_delta = 0
        explanation_parts = []

        for word in distress_words:
            if word in text:
                risk_delta += 1
                flags.append(f"DISTRESS_WORD: {word}")
                explanation_parts.append(f"distress word '{word}'")

        for word in calm_words:
            if word in text:
                risk_delta -= 1  # May modify down if calm words present

        current = state.get("distress_score", 2)
        new_score = max(0, min(10, current + risk_delta))
        state["distress_score"] = new_score

        if not flags:
            return None  # No text-based update needed

        assessment = AgentAssessment(
            agent_id=self.agent_id,
            risk_score=new_score,
            confidence=0.6,
            explanation=", ".join(explanation_parts) or "text tone analysis",
            dimensions={"text_distress_delta": risk_delta},
            flags=flags
        )
        await self.emit(call_sid, assessment)
        return assessment
