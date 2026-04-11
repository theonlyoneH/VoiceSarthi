"""Agent Runner — Async consumer loop for all agent workers.
Follows IMPLEMENTATION_GUIDE.md Phase 6 (run_agents).
"""
import asyncio
import logging
import os
import sys

# Allow running as module: python -m agents.runner
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.event_bus import EventBus
from agents.narrative_agent import NarrativeAgent
from agents.emotion_agent import EmotionAgent
from agents.ambient_agent import AmbientAgent
from agents.language_agent import LanguageAgent
from agents.fatigue_agent import OperatorFatigueAgent
from agents.meta_agent import MetaAgent

logger = logging.getLogger(__name__)


async def run_agents():
    """Main async agent loop — consumes events from EventBus."""
    await EventBus.connect()
    logger.info("Agent runner connected to EventBus")

    narrative = NarrativeAgent()
    emotion = EmotionAgent()
    ambient = AmbientAgent()
    language = LanguageAgent()
    fatigue = OperatorFatigueAgent()
    meta = MetaAgent()

    # Map event types to agents
    agent_map: dict[str, list] = {
        "stt.segment": [narrative, language, emotion],
        "audio.features": [emotion, ambient],
        "call.state_change": [fatigue],
        "meta.risk_update": [fatigue],
    }

    async for event in EventBus.subscribe("agent-runner", "main"):
        event_type = event.get("type")
        call_sid = event.get("call_sid")

        if not call_sid:
            continue

        handlers = agent_map.get(event_type, [])
        for agent in handlers:
            try:
                assessment = await agent.on_event(event)
                if assessment:
                    meta.update_assessment(call_sid, {
                        "agent_id": assessment.agent_id,
                        "risk_score": assessment.risk_score,
                        "confidence": assessment.confidence,
                        "explanation": assessment.explanation,
                        "dimensions": assessment.dimensions,
                        "flags": assessment.flags
                    })
                    await meta.fuse_and_emit(call_sid)
            except Exception as e:
                logger.error(f"Agent {agent.agent_id} error on {event_type}: {e}", exc_info=True)

        # Clean up on call end
        if event_type == "call.state_change" and event.get("new_state") == "completed":
            meta.clear_call(call_sid)
            for agent in [narrative, emotion, ambient, language, fatigue]:
                agent.clear_state(call_sid)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    logger.info("VoiceForward Agent Runner starting...")
    asyncio.run(run_agents())
