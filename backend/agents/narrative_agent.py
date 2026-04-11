"""NarrativeAgent — Detects high-risk narrative patterns in transcript text.
Follows IMPLEMENTATION_GUIDE.md Section 5.2 and ETHICS_AND_SAFETY.md Layer 5.
"""
from .base import BaseAgent, AgentAssessment
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Critical phrases across 10 Indian languages
# IMPORTANT: Clinical team should expand and validate this list
HIGH_STAKES_PHRASES: dict[str, list[str]] = {
    "en": [
        "i've decided", "i have decided", "said my goodbyes", "said goodbye",
        "no one will miss me", "no point anymore", "going to end it",
        "tried last week", "tried before", "last time", "won't be here",
        "nothing left", "final decision", "made up my mind", "can't go on",
        "no reason to live", "end my life", "end it all", "never wake up",
        "goodbye forever", "this is the last"
    ],
    "hi": [
        "faisla kar liya", "nirnay le liya", "alvida bol diya", "alvida keh diya",
        "koi nahi dhundhega", "koi nahi chahiye", "khatam karna chahta",
        "kal kiya tha", "pehle kiya tha", "ab aur nahi", "sab khatam",
        "pura ho gaya", "thak gaya hoon", "jeene ki wajah nahi",
        "jeevan khatam karna", "har gaya hoon", "main nahi rahunga",
        "main nahi rahungi"
    ],
    "mr": [
        "nirnay gheto", "sarvanna nirop dila", "sampavto",
        "nivadnuk keli", "sarvanna baay bhakar dili"
    ],
    "te": [
        "nirnayam cheskunnanu", "inti nunchi vellipotanu",
        "anni cheskunna", "poyipodam anukuntunna"
    ],
    "ta": [
        "mudivu pannineen", "ellaarukkum vidai sollideen",
        "ini enakku vaazha vendam", "kadeisi mudivu"
    ],
    "bn": [
        "siddhanто niyechi", "sobaikei bida bolchi",
        "ar thakte parchhi na", "shesh kore debo"
    ],
    "kn": [
        "nirdharisiddene", "ellarigu alvida heldidene",
        "ini baalalu aase illa", "koneya nirdhar"
    ],
    "gu": [
        "nishchay kari lidho", "badha ne alvida kahyu",
        "hun nahi rahish", "aakhri faislo"
    ],
    "pa": [
        "faisla kar liya", "sab nu alwida keh dita",
        "hun nahi rahanga", "pehla vi kita si"
    ],
    "ur": [
        "faisla kar liya", "sab ko alvida keh diya",
        "ab nahi jeena", "sab khatam karna chahta hun"
    ]
}

PAST_ATTEMPT_PHRASES: dict[str, list[str]] = {
    "en": [
        "tried before", "tried last", "attempted", "took pills",
        "cut myself", "jumped", "overdosed", "tried to end", "previous attempt"
    ],
    "hi": [
        "pehle kiya tha", "koshish ki thi", "pills li thi",
        "kaat liya tha", "uch se kuda tha", "pehle bhi kiya"
    ],
    "mr": ["aadhi kelele hote", "magachya veli"],
    "te": ["mundu cheyyadam try chesanu", "okasari try chesanu"],
    "ta": ["munnadi try panninen", "kazhivule paniruken"],
    "bn": ["age cheshta korechilam", "ager baar"],
    "kn": ["munche try madidde", "hinde ond sala"],
    "gu": ["pahela try karyun", "paheli vaar"],
    "pa": ["pehla vi try kita si", "pichhle hafte"],
    "ur": ["pehle bhi kiya tha", "pehli koshish"]
}

DISCLOSURE_PHRASES: dict[str, list[str]] = {
    "en": ["not safe", "I'm not safe", "in danger", "he'll hurt me", "she'll hurt me"],
    "hi": ["safe nahi hoon", "main safe nahi", "khatara hai", "mujhe marega", "dar lag raha"],
}


class NarrativeAgent(BaseAgent):
    agent_id = "narrative"
    subscriptions = ["stt.segment"]

    async def on_event(self, event: dict) -> Optional[AgentAssessment]:
        if event["type"] != "stt.segment":
            return None

        call_sid = event["call_sid"]
        text = event["text"].lower().strip()
        uncertain = event.get("uncertain", False)

        if not text:
            return None

        state = self.get_state(call_sid)
        state.setdefault("transcript_history", [])
        state.setdefault("flagged_phrases", [])
        state.setdefault("narrative_risk", 0)
        state.setdefault("past_attempt_mentioned", False)
        state.setdefault("decided_count", 0)

        state["transcript_history"].append(text)
        if len(state["transcript_history"]) > 20:
            state["transcript_history"].pop(0)

        flags = []
        risk_score = state["narrative_risk"]
        dimensions = {}
        explanation_parts = []

        # Check high-stakes phrases (all languages)
        for lang, phrases in HIGH_STAKES_PHRASES.items():
            for phrase in phrases:
                if phrase in text:
                    phrase_count = sum(phrase in seg for seg in state["transcript_history"])
                    if phrase_count >= 2:
                        flags.append(f"REPEATED_HIGH_STAKES: '{phrase}' x{phrase_count}")
                        risk_score = max(risk_score, 8)
                        explanation_parts.append(f"'{phrase}' repeated {phrase_count}x")
                        state["decided_count"] += 1
                    else:
                        flags.append(f"HIGH_STAKES_PHRASE: '{phrase}'")
                        risk_score = max(risk_score, 6)
                        explanation_parts.append(f"phrase '{phrase}' detected")
                    state["flagged_phrases"].append(phrase)

        # "decided" repeated twice → clinical override to HIGH per MetaAgent rules
        if any("decided" in p or "faisla" in p or "nirnay" in p
               for p in state["flagged_phrases"]):
            if state["decided_count"] >= 2:
                risk_score = max(risk_score, 8)
                flags.append("DECIDED_TWICE_OVERRIDE")
                explanation_parts.append("'decided' keyword appeared 2+ times — clinical override")

        # Check past attempt phrases
        for lang, phrases in PAST_ATTEMPT_PHRASES.items():
            for phrase in phrases:
                if phrase in text:
                    state["past_attempt_mentioned"] = True
                    flags.append("PAST_ATTEMPT_MENTIONED")
                    risk_score = max(risk_score, 7)
                    explanation_parts.append("past attempt mentioned")

        # Disclosure phrases (immediate safety concern)
        for lang, phrases in DISCLOSURE_PHRASES.items():
            for phrase in phrases:
                if phrase in text:
                    flags.append(f"SAFETY_DISCLOSURE: '{phrase}'")
                    risk_score = max(risk_score, 6)
                    explanation_parts.append(f"safety disclosure: '{phrase}'")

        # Narrative shift: caller becoming less talkative (withdrawal detection)
        if len(state["transcript_history"]) >= 6:
            recent = " ".join(state["transcript_history"][-3:])
            earlier = " ".join(state["transcript_history"][-6:-3])
            if earlier and len(recent) < len(earlier) * 0.35:
                flags.append("WITHDRAWAL_DETECTED")
                risk_score = min(10, risk_score + 1)
                explanation_parts.append("caller becoming less talkative (withdrawal)")

        state["narrative_risk"] = risk_score
        dimensions["past_attempt"] = state["past_attempt_mentioned"]
        dimensions["high_stakes_phrase_count"] = len([f for f in flags if "HIGH_STAKES" in f])
        dimensions["decided_count"] = state["decided_count"]

        # Confidence is lower if STT was uncertain
        confidence = 0.5 if uncertain else 0.85

        explanation = (
            ", ".join(explanation_parts) if explanation_parts
            else "No high-risk narrative indicators"
        )

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
