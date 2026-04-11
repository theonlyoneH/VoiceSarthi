"""Analytics Service — Anonymised phrase-outcome logging.
Follows PRD.md F9 and ETHICS_AND_SAFETY.md (minimum data retention).
"""
import logging
import hashlib
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from db.models import PhraseOutcome

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def record_phrase_outcome(
        self,
        helpline_id: str,
        phrase_text: str,
        outcome_label: str,
        outcome_positive: bool,
        language: str = "en",
        risk_level_at_use: str = "MEDIUM",
        call_minute: int | None = None,
        phrase_category: str | None = None,
        caller_age_band: str | None = None,
        caller_language: str | None = None
    ):
        """Log a phrase-outcome pair for longitudinal learning (NO PII)."""
        # Anonymised caller profile hash (no personal data)
        profile_parts = filter(None, [caller_age_band, caller_language])
        profile_str = "_".join(profile_parts)
        caller_profile_hash = hashlib.sha256(profile_str.encode()).hexdigest()[:16] if profile_str else None

        entry = PhraseOutcome(
            helpline_id=helpline_id,
            call_minute=call_minute,
            language=language,
            risk_level_at_use=risk_level_at_use,
            caller_profile_hash=caller_profile_hash,
            phrase_text=phrase_text,
            phrase_category=phrase_category,
            outcome_label=outcome_label,
            outcome_positive=outcome_positive
        )
        self.db.add(entry)
        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"Analytics log error: {e}")
            self.db.rollback()

    def get_phrase_effectiveness(self, helpline_id: str, phrase_category: str | None = None) -> dict:
        """Get phrase effectiveness statistics for a helpline."""
        query = self.db.query(PhraseOutcome).filter(
            PhraseOutcome.helpline_id == helpline_id
        )
        if phrase_category:
            query = query.filter(PhraseOutcome.phrase_category == phrase_category)

        all_phrases = query.all()
        if not all_phrases:
            return {}

        total = len(all_phrases)
        positive = sum(1 for p in all_phrases if p.outcome_positive)
        return {
            "total_phrases": total,
            "positive_outcomes": positive,
            "effectiveness_rate": round(positive / total, 3) if total > 0 else 0,
            "by_category": self._group_by_category(all_phrases)
        }

    @staticmethod
    def _group_by_category(phrases: list) -> dict:
        cats = {}
        for p in phrases:
            cat = p.phrase_category or "unknown"
            cats.setdefault(cat, {"total": 0, "positive": 0})
            cats[cat]["total"] += 1
            if p.outcome_positive:
                cats[cat]["positive"] += 1
        return {k: {**v, "rate": v["positive"] / v["total"]} for k, v in cats.items()}
