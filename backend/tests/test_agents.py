"""Tests for MetaAgent conflict resolution logic.
Follows ARCHITECTURE.md Section 5 (MetaAgent Conflict Resolution Priority).
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# Mock EventBus before importing MetaAgent
def mock_emit(*args, **kwargs):
    pass


class TestMetaAgentConflictResolution:
    """Tests for safety-first conflict resolution logic."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch('pipeline.event_bus.EventBus.emit', new_callable=AsyncMock):
            from agents.meta_agent import MetaAgent, score_to_level, SAFETY_FIRST
            self.MetaAgent = MetaAgent
            self.score_to_level = score_to_level
            self.SAFETY_FIRST = SAFETY_FIRST

    def test_safety_first_is_always_true(self):
        """CRITICAL: SAFETY_FIRST must never be False."""
        assert self.SAFETY_FIRST == True, "SAFETY_FIRST constant must be True — never change this"

    def test_score_to_level_mapping(self):
        """Test risk score to level mapping."""
        cases = [
            (0, "LOW"), (1, "LOW"), (2, "LOW"),
            (3, "MEDIUM"), (4, "MEDIUM"),
            (5, "HIGH"), (6, "HIGH"),
            (7, "CRITICAL"), (8, "CRITICAL"), (9, "CRITICAL"), (10, "CRITICAL"),
        ]
        for score, expected in cases:
            result = self.score_to_level(score)
            assert result == expected, f"score {score} → expected {expected}, got {result}"

    @pytest.mark.asyncio
    async def test_conflict_defaults_to_max_score(self):
        """When agents disagree by >= 3, MetaAgent should use MAX score (safety-first)."""
        emitted_events = []

        async def capture_emit(event_type, payload):
            if event_type == "meta.risk_update":
                emitted_events.append(payload)

        with patch('pipeline.event_bus.EventBus.emit', side_effect=capture_emit):
            from agents.meta_agent import MetaAgent
            meta = MetaAgent()

            # Emotion says LOW (2), Narrative says HIGH (7) → conflict → should pick 7
            meta.update_assessment("test_001", {
                "agent_id": "emotion",
                "risk_score": 2,
                "confidence": 0.8,
                "explanation": "calm tone",
                "dimensions": {},
                "flags": []
            })
            meta.update_assessment("test_001", {
                "agent_id": "narrative",
                "risk_score": 7,
                "confidence": 0.85,
                "explanation": "high-stakes phrase detected",
                "dimensions": {},
                "flags": ["HIGH_STAKES_PHRASE"]
            })

            await meta.fuse_and_emit("test_001")

        assert len(emitted_events) == 1, "Should emit exactly one risk update"
        event = emitted_events[0]
        assert event["risk_score"] == 7, f"Conflict → should pick max score 7, got {event['risk_score']}"
        assert event["risk_level"] == "CRITICAL", f"Score 7 → CRITICAL, got {event['risk_level']}"
        assert len(event["conflicts"]) > 0, "Should report conflict"
        assert event["confidence"] == 0.5, "Conflict → confidence should be 0.5"

    @pytest.mark.asyncio
    async def test_ambient_override_adds_two(self):
        """Child crying or glass breaking should add +2 to final score."""
        emitted_events = []

        async def capture_emit(event_type, payload):
            if event_type == "meta.risk_update":
                emitted_events.append(payload)

        with patch('pipeline.event_bus.EventBus.emit', side_effect=capture_emit):
            from agents.meta_agent import MetaAgent
            meta = MetaAgent()

            # Baseline: MEDIUM risk (score 4)
            meta.update_assessment("test_002", {
                "agent_id": "narrative",
                "risk_score": 4,
                "confidence": 0.8,
                "explanation": "general distress",
                "dimensions": {},
                "flags": []
            })
            # Ambient: child crying → should add +2
            meta.update_assessment("test_002", {
                "agent_id": "ambient",
                "risk_score": 4,
                "confidence": 0.75,
                "explanation": "child crying detected",
                "dimensions": {},
                "flags": ["AMBIENT_OVERRIDE: child_crying"]
            })

            await meta.fuse_and_emit("test_002")

        assert len(emitted_events) == 1
        event = emitted_events[0]
        # Base 4 + ambient override +2 = 6 → HIGH
        assert event["risk_score"] == 6, f"Expected 6 (4 + ambient +2), got {event['risk_score']}"
        assert event["risk_level"] == "HIGH"

    @pytest.mark.asyncio
    async def test_low_confidence_agent_excluded(self):
        """Agents with confidence < 0.5 should be excluded from fusion."""
        emitted_events = []

        async def capture_emit(event_type, payload):
            if event_type == "meta.risk_update":
                emitted_events.append(payload)

        with patch('pipeline.event_bus.EventBus.emit', side_effect=capture_emit):
            from agents.meta_agent import MetaAgent
            meta = MetaAgent()

            # High confidence agent says LOW
            meta.update_assessment("test_003", {
                "agent_id": "narrative",
                "risk_score": 2,
                "confidence": 0.8,
                "explanation": "calm conversation",
                "dimensions": {},
                "flags": []
            })
            # Low confidence agent says CRITICAL — should be EXCLUDED
            meta.update_assessment("test_003", {
                "agent_id": "emotion",
                "risk_score": 9,
                "confidence": 0.3,  # Below MIN_AGENT_CONFIDENCE
                "explanation": "uncertain emotional read",
                "dimensions": {},
                "flags": []
            })

            await meta.fuse_and_emit("test_003")

        assert len(emitted_events) == 1
        event = emitted_events[0]
        # Only narrative (score 2) should count → LOW
        assert event["risk_score"] == 2, f"Expected 2 (excluded low-conf agent), got {event['risk_score']}"
        assert event["risk_level"] == "LOW"

    @pytest.mark.asyncio
    async def test_temporal_coherence_caps_rapid_jump(self):
        """Risk score cannot jump more than 3 in one update without multi-agent confirmation."""
        emitted_events = []

        async def capture_emit(event_type, payload):
            if event_type == "meta.risk_update":
                emitted_events.append(payload)

        with patch('pipeline.event_bus.EventBus.emit', side_effect=capture_emit):
            from agents.meta_agent import MetaAgent
            meta = MetaAgent()
            call_sid = "test_004"

            # Set history at score 2
            meta.last_risk_scores[call_sid] = [2]

            # Single agent suddenly says CRITICAL (score 9) → should be capped at 2 + 3 = 5
            meta.update_assessment(call_sid, {
                "agent_id": "narrative",
                "risk_score": 9,
                "confidence": 0.8,
                "explanation": "sudden critical phrase",
                "dimensions": {},
                "flags": ["HIGH_STAKES_PHRASE"]
            })

            await meta.fuse_and_emit(call_sid)

        assert len(emitted_events) == 1
        event = emitted_events[0]
        # Should be capped at 2 + 3 = 5 (temporal coherence)
        assert event["risk_score"] <= 5, f"Expected capped at 5, got {event['risk_score']}"


class TestNarrativeAgent:
    """Tests for NarrativeAgent keyword detection."""

    @pytest.mark.asyncio
    async def test_decided_twice_triggers_high(self):
        """'I've decided' appearing twice should trigger HIGH risk."""
        with patch('pipeline.event_bus.EventBus.emit', new_callable=AsyncMock):
            from agents.narrative_agent import NarrativeAgent

            agent = NarrativeAgent()
            call_sid = "narr_test_001"

            # First occurrence
            result1 = await agent.on_event({
                "type": "stt.segment",
                "call_sid": call_sid,
                "text": "I've decided to do it",
                "language_tags": [{"phrase": "I've decided", "lang": "en"}],
                "confidence": 0.85,
                "uncertain": False
            })
            assert result1 is not None
            assert result1.risk_score >= 6, "First 'decided' → at least HIGH (6)"

            # Second occurrence — should escalate
            result2 = await agent.on_event({
                "type": "stt.segment",
                "call_sid": call_sid,
                "text": "I've decided. It's final.",
                "language_tags": [{"phrase": "I've decided", "lang": "en"}],
                "confidence": 0.85,
                "uncertain": False
            })
            assert result2 is not None
            assert result2.risk_score >= 8, "Second 'decided' → CRITICAL override (>=8)"
            assert any("REPEATED_HIGH_STAKES" in f or "DECIDED_TWICE" in f
                       for f in result2.flags), "Should flag repeated high-stakes phrase"

    @pytest.mark.asyncio
    async def test_past_attempt_detection(self):
        """'tried before' and similar should trigger PAST_ATTEMPT flag."""
        with patch('pipeline.event_bus.EventBus.emit', new_callable=AsyncMock):
            from agents.narrative_agent import NarrativeAgent
            agent = NarrativeAgent()

            result = await agent.on_event({
                "type": "stt.segment",
                "call_sid": "narr_test_002",
                "text": "I tried before, last week",
                "language_tags": [{"phrase": "tried before", "lang": "en"}],
                "confidence": 0.85,
                "uncertain": False
            })
            assert result is not None
            assert "PAST_ATTEMPT_MENTIONED" in result.flags
            assert result.risk_score >= 7

    @pytest.mark.asyncio
    async def test_uncertain_stt_reduces_confidence(self):
        """Uncertain STT flag should lower agent confidence."""
        with patch('pipeline.event_bus.EventBus.emit', new_callable=AsyncMock):
            from agents.narrative_agent import NarrativeAgent
            agent = NarrativeAgent()

            result = await agent.on_event({
                "type": "stt.segment",
                "call_sid": "narr_test_003",
                "text": "I've decided to end it",
                "language_tags": [],
                "confidence": 0.4,  # Below UNCERTAIN_THRESHOLD
                "uncertain": True
            })
            assert result is not None
            assert result.confidence == 0.5, "Uncertain STT → confidence = 0.5"


class TestPriorityService:
    """Tests for call priority scoring."""

    @pytest.mark.asyncio
    async def test_dtmf_2_gives_p0_or_p1(self):
        """Caller pressing 2 ('not safe') should give P1 or P0."""
        from services.priority_service import PriorityService
        svc = PriorityService(redis_client=None)

        tier, score, reason = await svc.score_call(
            "prio_test_001", "+91-9999999999",
            ivr_response=None, dtmf_key="2"
        )
        assert tier in ("P0", "P1"), f"DTMF 2 should give P0/P1, got {tier}"
        assert score >= 30
        assert "IVR" in reason or "distress" in reason

    @pytest.mark.asyncio
    async def test_no_signals_gives_p3(self):
        """No distress signals → P3."""
        from services.priority_service import PriorityService
        svc = PriorityService(redis_client=None)

        tier, score, reason = await svc.score_call(
            "prio_test_002", "+91-8888888888",
            ivr_response="I just want to talk",
            dtmf_key="1"
        )
        assert tier == "P3", f"No signals → P3, got {tier}"

    @pytest.mark.asyncio
    async def test_distress_keyword_gives_p1(self):
        """IVR response with distress keyword → P1."""
        from services.priority_service import PriorityService
        svc = PriorityService(redis_client=None)

        tier, score, reason = await svc.score_call(
            "prio_test_003", "+91-7777777777",
            ivr_response="I want to hurt myself",
            dtmf_key=None
        )
        assert tier in ("P0", "P1"), f"Distress keyword → P1, got {tier}"

    def test_phone_hash_is_sha256(self):
        """Phone hash should be SHA-256 and never raw phone number."""
        import hashlib
        from services.priority_service import PriorityService

        phone = "+91-9876543210"
        expected_hash = hashlib.sha256(phone.encode()).hexdigest()
        actual_hash = PriorityService._hash_phone(phone)

        assert actual_hash == expected_hash, "Phone hash must be SHA-256"
        assert len(actual_hash) == 64, "SHA-256 hash must be 64 chars"
        assert phone not in actual_hash, "Raw phone number must not be in hash"
