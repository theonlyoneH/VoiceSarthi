"""LanguageAgent — Detects code-switching, dialects, idioms, and codewords.
Follows PRD.md F3 and ARCHITECTURE.md Section 5.
"""
from .base import BaseAgent, AgentAssessment
from typing import Optional
import re
import logging

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {'hi', 'en', 'mr', 'te', 'bn', 'gu', 'kn', 'pa', 'ur', 'ta'}

# Language-specific script patterns
HINDI_DEVANAGARI = re.compile(r'[\u0900-\u097F]')
BENGALI = re.compile(r'[\u0980-\u09FF]')
TELUGU = re.compile(r'[\u0C00-\u0C7F]')
TAMIL = re.compile(r'[\u0B80-\u0BFF]')
KANNADA = re.compile(r'[\u0C80-\u0CFF]')
GUJARATI = re.compile(r'[\u0A80-\u0AFF]')
PUNJABI_GURMUKHI = re.compile(r'[\u0A00-\u0A7F]')
URDU_ARABIC = re.compile(r'[\u0600-\u06FF]')

# Codewords / idioms that may indicate suicide risk across cultures
CULTURAL_CODEWORDS = {
    "en": [
        "going on a long journey", "the only way out", "end the pain",
        "be free", "peace at last", "meet my maker", "check out"
    ],
    "hi": [
        "lambe safar par jaana", "ek hi raasta", "dard khatam karo",
        "amaan mil jaayegi", "mukti mil jaayegi"
    ],
    "mr": ["moksha milel", "sutt miltil", "vegla hoil"],
    "te": ["mukthi pothundi", "vishranti dorukutundi"],
    "ta": ["mukthi kidaikkum", "shanthi kidaikkum"],
}


class LanguageAgent(BaseAgent):
    agent_id = "language"
    subscriptions = ["stt.segment"]

    async def on_event(self, event: dict) -> Optional[AgentAssessment]:
        if event["type"] != "stt.segment":
            return None

        call_sid = event["call_sid"]
        text = event.get("text", "")
        language_tags = event.get("language_tags", [])

        if not text:
            return None

        state = self.get_state(call_sid)
        state.setdefault("languages_detected", set())
        state.setdefault("code_switch_count", 0)
        state.setdefault("previous_lang", None)
        state.setdefault("codeword_flags", [])

        flags = []
        risk_score = 1  # baseline — language itself is not a risk signal
        explanation_parts = []
        dimensions = {}

        # Detect script-based languages
        detected_langs = self._detect_scripts(text)
        for lang in detected_langs:
            if lang not in state["languages_detected"]:
                state["languages_detected"].add(lang)
                explanation_parts.append(f"new language detected: {lang.upper()}")

        # Sarvam-provided language tags
        if isinstance(language_tags, list) and language_tags:
            for tag in language_tags:
                if isinstance(tag, dict):
                    lang = tag.get("lang", "")
                    if lang and lang in SUPPORTED_LANGUAGES:
                        if lang not in state["languages_detected"]:
                            state["languages_detected"].add(lang)

        # Code-switch detection
        text_lower = text.lower()
        current_lang = None
        if language_tags and isinstance(language_tags, list) and isinstance(language_tags[0], dict):
            current_lang = language_tags[0].get("lang")

        if current_lang and state["previous_lang"] and current_lang != state["previous_lang"]:
            state["code_switch_count"] += 1
            flags.append(f"CODE_SWITCH: {state['previous_lang'].upper()} → {current_lang.upper()}")
            explanation_parts.append(f"code-switch {state['previous_lang'].upper()} → {current_lang.upper()}")

        state["previous_lang"] = current_lang

        # Cultural codeword detection
        for lang, codewords in CULTURAL_CODEWORDS.items():
            for codeword in codewords:
                if codeword in text_lower:
                    flags.append(f"CULTURAL_CODEWORD: '{codeword}' ({lang})")
                    risk_score = max(risk_score, 5)
                    explanation_parts.append(f"cultural codeword '{codeword}' in {lang.upper()}")
                    state["codeword_flags"].append(codeword)

        dimensions["languages_detected"] = list(state["languages_detected"])
        dimensions["code_switch_count"] = state["code_switch_count"]
        dimensions["code_switch_map"] = [f.replace("CODE_SWITCH: ", "") for f in flags if "CODE_SWITCH" in f]

        confidence = 0.75
        explanation = ", ".join(explanation_parts) if explanation_parts else (
            f"languages: {', '.join(state['languages_detected']).upper() if state['languages_detected'] else 'unknown'}"
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

    @staticmethod
    def _detect_scripts(text: str) -> list[str]:
        detected = []
        if re.search(r'[a-zA-Z]', text):
            detected.append("en")
        if HINDI_DEVANAGARI.search(text):
            detected.append("hi")
        if BENGALI.search(text):
            detected.append("bn")
        if TELUGU.search(text):
            detected.append("te")
        if TAMIL.search(text):
            detected.append("ta")
        if KANNADA.search(text):
            detected.append("kn")
        if GUJARATI.search(text):
            detected.append("gu")
        if PUNJABI_GURMUKHI.search(text):
            detected.append("pa")
        if URDU_ARABIC.search(text):
            detected.append("ur")
        return detected
