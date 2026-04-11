"""Priority Service — Call priority scoring (P0–P3).
Follows ARCHITECTURE.md Section 2 and PRD.md F1.
"""
import hashlib
import time
import os
from typing import Literal
import logging

logger = logging.getLogger(__name__)

PriorityTier = Literal["P0", "P1", "P2", "P3"]

DISTRESS_KEYWORDS = {
    "en": ["not safe", "hurt myself", "end it", "die", "kill", "no reason", "suicide",
           "help me", "in danger", "emergency"],
    "hi": ["safe nahi", "khud ko", "khatam", "marna", "jeevan", "khatar", "darr"],
    "mr": ["surakshit nahi", "sampavato", "manus"],
    "te": ["safe kadu", "chastanu", "praanam"],
    "ta": ["paathukappadala", "irekka"],
}


class PriorityService:
    def __init__(self, redis_client=None):
        self.redis = redis_client

    async def score_call(
        self,
        call_sid: str,
        caller_number: str,
        ivr_response: str | None = None,
        dtmf_key: str | None = None,
        audio_energy: float | None = None
    ) -> tuple[PriorityTier, int, str]:
        """
        Score and assign P0/P1/P2/P3 tier to a call.
        Returns: (tier, score, reason)
        """
        score = 0
        reason_parts = []

        # 1. IVR response: caller pressed 2 ("not safe") or spoke distress keywords
        if dtmf_key == "2":
            score += 40
            reason_parts.append("IVR: caller indicated not safe (key 2)")
        elif ivr_response:
            for lang, keywords in DISTRESS_KEYWORDS.items():
                for kw in keywords:
                    if kw in ivr_response.lower():
                        score += 35
                        reason_parts.append(f"IVR distress keyword: '{kw}'")
                        break

        # 2. Repeat high-risk caller
        caller_hash = self._hash_phone(caller_number)
        if self.redis:
            try:
                is_repeat_high_risk = await self.redis.get(f"high_risk_caller:{caller_hash}")
                if is_repeat_high_risk:
                    score += 50
                    reason_parts.append("repeat high-risk caller (flagged from previous call)")
            except Exception as e:
                logger.warning(f"Redis check failed for repeat caller: {e}")

        # 3. Audio energy on hold: screaming/crying → P0
        if audio_energy is not None:
            if audio_energy > 5000:  # Screaming threshold
                score += 30
                reason_parts.append(f"high audio energy on hold ({audio_energy:.0f}) — possible distress")
            elif audio_energy < 100:  # Complete silence (may be dissociating)
                score += 10
                reason_parts.append("complete silence on hold — possible dissociation")

        # Map score to tier
        if score >= 50:
            tier = "P0"
        elif score >= 30:
            tier = "P1"
        elif score >= 10:
            tier = "P2"
        else:
            tier = "P3"

        reason = ", ".join(reason_parts) if reason_parts else f"standard call (score={score})"
        logger.info(f"Call {call_sid}: scored {score} → {tier} — {reason}")
        return tier, score, reason

    async def should_divert_p3(self, helpline_id: str, diversion_threshold: int = 3) -> bool:
        """Check if P3 calls should be diverted based on queue depth."""
        if not self.redis:
            return False
        try:
            p0_depth = await self.redis.zcard(f"queue:{helpline_id}:p0")
            p1_depth = await self.redis.zcard(f"queue:{helpline_id}:p1")
            p2_depth = await self.redis.zcard(f"queue:{helpline_id}:p2")
            total = p0_depth + p1_depth + p2_depth
            return total > diversion_threshold
        except Exception as e:
            logger.warning(f"Redis queue check failed: {e}")
            return False

    async def add_to_queue(self, helpline_id: str, call_sid: str, tier: str):
        """Add a call to the priority queue in Redis."""
        if not self.redis:
            return
        await self.redis.zadd(
            f"queue:{helpline_id}:{tier.lower()}",
            {call_sid: time.time()}
        )
        logger.info(f"Added {call_sid} to {tier} queue for helpline {helpline_id}")

    async def get_next_for_operator(
        self, helpline_id: str, operator_tier: str = "junior"
    ) -> str | None:
        """Get highest priority call for this operator."""
        if not self.redis:
            return None

        # P0 first (any operator), then P1 (prefer senior), then P2, P3
        queues = ["p0", "p1", "p2", "p3"]

        for priority in queues:
            # P1: prefer senior operators, but don't block
            if priority == "p1" and operator_tier == "junior":
                depth = await self.redis.zcard(f"queue:{helpline_id}:p1")
                if depth > 3:  # Allow if queue is backing up
                    pass
                else:
                    continue

            result = await self.redis.zpopmin(f"queue:{helpline_id}:{priority}", 1)
            if result:
                call_sid, _ = result[0]
                return call_sid
        return None

    async def get_queue_state(self, helpline_id: str) -> dict:
        """Get the current queue state for a helpline."""
        if not self.redis:
            return {"p0": 0, "p1": 0, "p2": 0, "p3": 0}

        depths = {}
        for tier in ["p0", "p1", "p2", "p3"]:
            try:
                depths[tier] = await self.redis.zcard(f"queue:{helpline_id}:{tier}")
            except Exception:
                depths[tier] = 0
        return depths

    async def flag_high_risk_caller(self, caller_number: str, ttl_days: int = 90):
        """Flag a caller as high-risk for repeat detection. TTL = 90 days per schema."""
        if not self.redis:
            return
        caller_hash = self._hash_phone(caller_number)
        await self.redis.setex(
            f"high_risk_caller:{caller_hash}",
            ttl_days * 86400,
            "1"
        )

    @staticmethod
    def _hash_phone(phone: str) -> str:
        """SHA-256 hash of phone number — NEVER store raw PII."""
        return hashlib.sha256(phone.encode()).hexdigest()
