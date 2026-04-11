"""Base Agent — shared interface for all VoiceForward agents.
Follows ARCHITECTURE.md Section 5.
"""
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentAssessment:
    agent_id: str
    risk_score: int       # 0–10
    confidence: float     # 0.0–1.0
    explanation: str
    dimensions: dict = field(default_factory=dict)
    flags: list = field(default_factory=list)


class BaseAgent:
    agent_id: str = "base"
    subscriptions: list[str] = []

    def __init__(self):
        self.state: dict[str, dict] = {}  # per call_sid state

    def get_state(self, call_sid: str) -> dict:
        if call_sid not in self.state:
            self.state[call_sid] = {}
        return self.state[call_sid]

    def clear_state(self, call_sid: str):
        self.state.pop(call_sid, None)

    async def on_event(self, event: dict) -> Optional[AgentAssessment]:
        raise NotImplementedError

    async def emit(self, call_sid: str, assessment: AgentAssessment):
        """Emit assessment to EventBus."""
        from pipeline.event_bus import EventBus
        await EventBus.emit('agent.assessment', {
            'call_sid': call_sid,
            'agent_id': assessment.agent_id,
            'risk_score': assessment.risk_score,
            'confidence': assessment.confidence,
            'explanation': assessment.explanation,
            'dimensions': assessment.dimensions,
            'flags': assessment.flags
        })
