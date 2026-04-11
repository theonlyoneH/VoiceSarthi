"""MetaAgent — Fuses all agent outputs and emits unified risk assessment.
Follows ARCHITECTURE.md Section 5 (MetaAgent Conflict Resolution Priority).
SAFETY_FIRST is a hard constant — never set to False.
"""
from .base import AgentAssessment
from pipeline.event_bus import EventBus
import asyncio
import uuid
import logging

logger = logging.getLogger(__name__)

# ─── Safety constants — DO NOT CHANGE ─────────────────────────────────────────
SAFETY_FIRST = True           # Highest score always wins in conflicts
CONFLICT_THRESHOLD = 3        # Risk score difference triggering conflict state
MIN_AGENT_CONFIDENCE = 0.5    # Agents below this are excluded from fusion
UNUSUAL_CALM_THRESHOLD = 0.8  # calm > 0.8 AND distress > 0.6 → +2
AMBIENT_OVERRIDE_SOUNDS = {"child_crying", "glass_breaking", "shouting_nearby"}
MAX_SCORE_JUMP = 3            # Temporal coherence: max score change in one update

# ─── Risk level mapping ────────────────────────────────────────────────────────
RISK_LEVELS = [
    (0, 2, "LOW"),
    (3, 4, "MEDIUM"),
    (5, 6, "HIGH"),
    (7, 10, "CRITICAL"),
]


def score_to_level(score: int) -> str:
    for lo, hi, level in RISK_LEVELS:
        if lo <= score <= hi:
            return level
    return "UNKNOWN"


# ─── Guidance templates ────────────────────────────────────────────────────────
GUIDANCE_TEMPLATES = {
    "LOW": "Continue building rapport. Ask open questions. Validate their feelings.",
    "MEDIUM": "Acknowledge what they've shared. Gently explore: 'Can you tell me more about what's happening?'",
    "HIGH": "Name what you're hearing: 'It sounds like things feel very heavy right now.' "
            "Ask directly: 'Are you thinking about hurting yourself?'",
    "CRITICAL": "Ask directly and calmly: 'Are you safe right now? Are you thinking about ending your life?' "
                "Stay on the line. Prepare to dispatch if needed.",
    "UNKNOWN": "Follow your training. I don't have enough signal yet to guide you.",
}

# Resource triggers — what risk levels should surface
RESOURCE_TRIGGERS = {
    "LOW": [],
    "MEDIUM": ["show_helplines", "show_mental_health"],
    "HIGH": ["show_shelter", "show_mental_health", "show_helplines"],
    "CRITICAL": ["show_ambulance", "show_shelter", "show_police", "show_mental_health"],
    "UNKNOWN": [],
}


class MetaAgent:
    """Orchestrator — resolves conflicts and emits unified risk updates."""

    def __init__(self):
        self.agent_assessments: dict[str, dict] = {}  # call_sid → {agent_id: assessment}
        self.last_risk_scores: dict[str, list] = {}   # call_sid → risk score history
        self.guidance_counter: dict[str, int] = {}

    def update_assessment(self, call_sid: str, event: dict):
        """Update assessment from an agent."""
        if call_sid not in self.agent_assessments:
            self.agent_assessments[call_sid] = {}
        agent_id = event.get("agent_id", "unknown")
        self.agent_assessments[call_sid][agent_id] = event

    async def fuse_and_emit(self, call_sid: str):
        """Fuse all agent outputs and emit a meta.risk_update event."""
        assessments = self.agent_assessments.get(call_sid, {})
        if not assessments:
            return

        explanation_parts = []
        conflicts = []
        valid_scores = []
        ambient_flags = []
        excluded_agents = []
        agents_summary = {}

        # ── Phase 1: Filter by confidence ─────────────────────────────────────
        for agent_id, a in assessments.items():
            conf = a.get("confidence", 0.0)
            if conf < MIN_AGENT_CONFIDENCE:
                excluded_agents.append(agent_id)
                explanation_parts.append(
                    f"{agent_id} excluded (conf={conf:.2f})"
                )
                continue

            # Special: harvest ambient override flags
            if agent_id == "ambient":
                for flag in a.get("flags", []):
                    for sound in AMBIENT_OVERRIDE_SOUNDS:
                        if sound in flag.lower():
                            ambient_flags.append(flag)

            valid_scores.append((agent_id, a["risk_score"]))
            agents_summary[agent_id] = {
                "score": a["risk_score"],
                "confidence": conf,
                "explanation": a.get("explanation", ""),
                "flags": a.get("flags", [])
            }
            explanation_parts.append(f"{agent_id}: {a.get('explanation', '')[:80]}")

        if not valid_scores:
            await EventBus.emit('meta.risk_update', {
                'call_sid': call_sid,
                'risk_level': 'UNKNOWN',
                'risk_score': 0,
                'confidence': 0.0,
                'explanation': 'All agent signals uncertain',
                'guidance_text': GUIDANCE_TEMPLATES['UNKNOWN'],
                'guidance_id': self._next_guidance_id(call_sid),
                'conflicts': [],
                'agents_summary': {},
                'resource_triggers': [],
                'location_detected': None
            })
            return

        scores_only = [s for _, s in valid_scores]
        max_score = max(scores_only)
        min_score = min(scores_only)
        conflict = (max_score - min_score) >= CONFLICT_THRESHOLD

        # ── Phase 2: Conflict detection and resolution ─────────────────────────
        if conflict:
            conflict_desc = ", ".join(f"{a}={s}" for a, s in valid_scores)
            conflicts.append(f"Agent disagreement: {conflict_desc}")
            explanation_parts.append(f"CONFLICT detected — defaulted to highest risk ({max_score})")

            # Narrative keyword override rule (ARCHITECTURE.md rule 3a)
            narrative = assessments.get("narrative", {})
            narrative_flags = narrative.get("flags", [])
            if any(f in ["DECIDED_TWICE_OVERRIDE", "PAST_ATTEMPT_MENTIONED"] for f in narrative_flags):
                explanation_parts.append("NarrativeAgent keyword override applied")

        # SAFETY_FIRST: always take max in conflict
        final_score = max_score

        # ── Phase 3: Apply overrides ───────────────────────────────────────────

        # Ambient override: child crying or glass breaking → +2
        if ambient_flags:
            final_score = min(10, final_score + 2)
            explanation_parts.append("Ambient audio modifier: +2")

        # Unusual calm override: +2 per ARCHITECTURE.md rule 4
        emotion = assessments.get("emotion", {})
        emotion_dims = emotion.get("dimensions", {})
        if emotion_dims.get("unusual_calm"):
            final_score = min(10, final_score + 2)
            explanation_parts.append("Unusual calm detected: +2")

        # ── Phase 4: Temporal coherence check ─────────────────────────────────
        history = self.last_risk_scores.get(call_sid, [])
        if history and final_score > history[-1] + MAX_SCORE_JUMP:
            # Require 2+ agents to confirm rapid increase
            agreeing = sum(s > history[-1] + 2 for _, s in valid_scores)
            if agreeing < 2:
                final_score = history[-1] + MAX_SCORE_JUMP
                explanation_parts.append("Rapid increase capped — awaiting multi-agent confirmation")

        final_score = max(0, min(10, final_score))
        history.append(final_score)
        self.last_risk_scores[call_sid] = history[-20:]

        # ── Phase 5: Emit ──────────────────────────────────────────────────────
        confidence = 0.5 if conflict else (
            sum(a.get("confidence", 0.5) for _, a in zip(valid_scores, assessments.values()))
            / max(len(valid_scores), 1)
        )

        risk_level = score_to_level(final_score)
        guidance = GUIDANCE_TEMPLATES.get(risk_level, GUIDANCE_TEMPLATES["UNKNOWN"])

        await EventBus.emit('meta.risk_update', {
            'call_sid': call_sid,
            'risk_level': risk_level,
            'risk_score': final_score,
            'confidence': round(confidence, 3),
            'explanation': ' | '.join(explanation_parts),
            'guidance_text': guidance,
            'guidance_id': self._next_guidance_id(call_sid),
            'conflicts': conflicts,
            'agents_summary': agents_summary,
            'resource_triggers': RESOURCE_TRIGGERS.get(risk_level, []),
            'location_detected': None  # updated by location service
        })

    def _next_guidance_id(self, call_sid: str) -> str:
        count = self.guidance_counter.get(call_sid, 0) + 1
        self.guidance_counter[call_sid] = count
        return f"{call_sid}_{count}"

    def clear_call(self, call_sid: str):
        """Release resources for a completed call."""
        self.agent_assessments.pop(call_sid, None)
        self.last_risk_scores.pop(call_sid, None)
        self.guidance_counter.pop(call_sid, None)
