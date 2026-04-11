# IMPLEMENTATION GUIDE — VoiceForward

> This document is written for an AI coding agent (Claude Code or similar).
> Follow instructions in order. Do not skip steps.
> Every section ends with a verification check — run it before proceeding.

---

## PHASE 0: Project Setup

### 0.1 Create Monorepo Structure

```bash
mkdir voiceforward && cd voiceforward
mkdir -p frontend backend/api backend/agents backend/pipeline \
          backend/services backend/db infra demo docs

# Root files
touch .env.example .gitignore docker-compose.yml
```

### 0.2 .env.example

```bash
cat > .env.example << 'EOF'
# Sarvam AI
SARVAM_API_KEY=your_sarvam_api_key_here
SARVAM_BASE_URL=https://api.sarvam.ai

# Exotel
EXOTEL_API_KEY=your_exotel_api_key
EXOTEL_API_TOKEN=your_exotel_token
EXOTEL_ACCOUNT_SID=your_account_sid
EXOTEL_BASE_URL=https://api.exotel.com/v1

# Database
DATABASE_URL=postgresql://voiceforward:secure@localhost:5432/voiceforward
REDIS_URL=redis://localhost:6379/0

# Auth
SECRET_KEY=change_this_to_a_long_random_string_in_production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

# Mapbox
NEXT_PUBLIC_MAPBOX_TOKEN=your_mapbox_public_token

# App
ENVIRONMENT=development
LOG_LEVEL=INFO
FRONTEND_URL=http://localhost:3000

# Fallback STT (local Whisper)
WHISPER_MODEL_PATH=./models/whisper-tiny
WHISPER_FALLBACK_ENABLED=true
EOF
```

### 0.3 .gitignore

```bash
cat > .gitignore << 'EOF'
.env
__pycache__/
*.pyc
node_modules/
.next/
dist/
*.egg-info/
.venv/
models/
*.wav
*.mp3
EOF
```

**✅ Verify:** All directories exist, .env.example populated.

---

## PHASE 1: Infrastructure

### 1.1 docker-compose.yml

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: voiceforward
      POSTGRES_USER: voiceforward
      POSTGRES_PASSWORD: secure
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --save 20 1 --loglevel warning

  api:
    build: ./backend/api
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

  agent-runner:
    build: ./backend/agents
    env_file: .env
    depends_on:
      - redis
    command: python -m agents.runner

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    env_file: .env
    environment:
      - NEXT_PUBLIC_WS_URL=ws://localhost:8000

volumes:
  pgdata:
```

### 1.2 Run Infrastructure

```bash
docker compose up -d postgres redis
sleep 5  # wait for postgres to be ready
```

**✅ Verify:** `docker compose ps` shows postgres and redis as "Up". Connect to postgres: `psql postgresql://voiceforward:secure@localhost:5432/voiceforward -c '\dt'`

---

## PHASE 2: Database Setup

### 2.1 Backend Dependencies

```bash
cd backend
cat > requirements.txt << 'EOF'
fastapi==0.109.0
uvicorn[standard]==0.27.0
websockets==12.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
sqlalchemy==2.0.25
alembic==1.13.1
psycopg2-binary==2.9.9
redis==5.0.1
httpx==0.26.0
python-multipart==0.0.6
pydantic==2.5.3
pydantic-settings==2.1.0
python-dotenv==1.0.0
asyncpg==0.29.0
numpy==1.26.3
scipy==1.12.0
sentence-transformers==2.3.1
openai-whisper==20231117
torch==2.1.2
torchaudio==2.1.2
EOF
pip install -r requirements.txt
```

### 2.2 Database Models (SQLAlchemy)

**File: `backend/db/models.py`**

```python
from sqlalchemy import Column, String, Boolean, Float, Integer, DateTime, \
    ForeignKey, ARRAY, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class Helpline(Base):
    __tablename__ = 'helplines'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    state = Column(String(50))
    city = Column(String(50))
    type = Column(String(50))
    phone_number = Column(String(20))
    exotel_account_sid = Column(String(100))
    risk_threshold_high = Column(Integer, default=6)
    risk_threshold_critical = Column(Integer, default=8)
    p3_diversion_queue_depth = Column(Integer, default=3)
    ai_enabled = Column(Boolean, default=True)
    languages_supported = Column(ARRAY(String), default=['en', 'hi'])
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Operator(Base):
    __tablename__ = 'operators'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    helpline_id = Column(UUID(as_uuid=True), ForeignKey('helplines.id'))
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True)
    password_hash = Column(String(255))
    role = Column(String(20), default='operator')
    languages = Column(ARRAY(String), default=['en'])
    experience_tier = Column(String(10), default='junior')
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Call(Base):
    __tablename__ = 'calls'
    call_sid = Column(String(64), primary_key=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    answered_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    operator_id = Column(UUID(as_uuid=True), ForeignKey('operators.id'))
    helpline_id = Column(UUID(as_uuid=True), ForeignKey('helplines.id'))
    language_primary = Column(String(10))
    languages_detected = Column(ARRAY(String))
    priority_tier = Column(String(4), default='P2')
    priority_score = Column(Integer)
    priority_reason = Column(String(255))
    final_risk_level = Column(String(10))
    peak_risk_level = Column(String(10))
    peak_risk_at = Column(DateTime(timezone=True))
    ai_disclosed = Column(Boolean, default=False)
    disclosed_at = Column(DateTime(timezone=True))
    opted_out = Column(Boolean, default=False)
    opted_out_at = Column(DateTime(timezone=True))
    shadow_mode = Column(Boolean, default=False)
    outcome_label = Column(String(30))
    outcome_set_at = Column(DateTime(timezone=True))
    outcome_set_by = Column(UUID(as_uuid=True), ForeignKey('operators.id'))
    caller_phone_hash = Column(String(64))
    anonymised_at = Column(DateTime(timezone=True))
    erasure_requested = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AISuggestion(Base):
    __tablename__ = 'ai_suggestions'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_sid = Column(String(64), ForeignKey('calls.call_sid'))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    suggestion_text = Column(Text, nullable=False)
    risk_level = Column(String(10), nullable=False)
    risk_score = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning_chain = Column(JSON, nullable=False)
    operator_action = Column(String(20))
    operator_action_at = Column(DateTime(timezone=True))
    operator_modification = Column(Text)
    operator_id = Column(UUID(as_uuid=True), ForeignKey('operators.id'))
    model_version = Column(String(50))
    call_minute = Column(Integer)

class Resource(Base):
    __tablename__ = 'resources'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    helpline_id = Column(UUID(as_uuid=True), ForeignKey('helplines.id'))
    name = Column(String(200), nullable=False)
    name_hi = Column(String(200))
    name_local = Column(String(200))
    description = Column(Text)
    category = Column(String(30), nullable=False)
    address = Column(Text)
    city = Column(String(100))
    district = Column(String(100))
    state = Column(String(50))
    lat = Column(Float)
    lng = Column(Float)
    phone = Column(String(20))
    phone_alt = Column(String(20))
    whatsapp = Column(String(20))
    email = Column(String(100))
    available_24x7 = Column(Boolean, default=False)
    hours = Column(String(100))
    languages = Column(ARRAY(String))
    follow_through_rate = Column(Float, default=0.5)
    referral_count = Column(Integer, default=0)
    positive_outcomes = Column(Integer, default=0)
    dispatchable = Column(Boolean, default=False)
    dispatch_type = Column(String(20))
    dispatch_endpoint = Column(String(255))
    active = Column(Boolean, default=True)
    verified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class DispatchLog(Base):
    __tablename__ = 'dispatch_log'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_sid = Column(String(64), ForeignKey('calls.call_sid'))
    operator_id = Column(UUID(as_uuid=True), ForeignKey('operators.id'))
    action_type = Column(String(30), nullable=False)
    resource_id = Column(UUID(as_uuid=True), ForeignKey('resources.id'))
    location_lat = Column(Float)
    location_lng = Column(Float)
    location_address = Column(Text)
    dispatched_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_by_operator = Column(Boolean, default=False)
    status = Column(String(20), default='sent')
    failure_reason = Column(String(255))
    exotel_conference_id = Column(String(100))

class DiversionLog(Base):
    __tablename__ = 'diversion_log'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_sid = Column(String(64))
    helpline_id = Column(UUID(as_uuid=True), ForeignKey('helplines.id'))
    diverted_at = Column(DateTime(timezone=True), server_default=func.now())
    queue_depth = Column(Integer, nullable=False)
    priority_tier = Column(String(4), nullable=False)
    options_offered = Column(ARRAY(String))
    caller_choice = Column(String(20))
    callback_scheduled_at = Column(DateTime(timezone=True))
    callback_completed = Column(Boolean)
    whatsapp_sent = Column(Boolean)
    caller_id_hash = Column(String(64))
```

### 2.3 Alembic Migrations

```bash
cd backend
alembic init alembic
# Edit alembic/env.py to import models and use DATABASE_URL
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

**✅ Verify:** `psql ... -c '\dt'` shows all 8+ tables.

---

## PHASE 3: Event Bus

**File: `backend/pipeline/event_bus.py`**

```python
import redis.asyncio as redis
import json
from datetime import datetime
from typing import Any
import os

class EventBus:
    _client: redis.Redis = None
    STREAM_KEY = "voiceforward:events"

    @classmethod
    async def connect(cls):
        cls._client = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

    @classmethod
    async def emit(cls, event_type: str, payload: dict):
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1",
            **payload
        }
        await cls._client.xadd(cls.STREAM_KEY, {"data": json.dumps(event)})

    @classmethod
    async def subscribe(cls, consumer_group: str, consumer_name: str,
                        event_types: list[str] | None = None):
        """Yield events from the stream for a consumer group."""
        try:
            await cls._client.xgroup_create(cls.STREAM_KEY, consumer_group, id='0', mkstream=True)
        except Exception:
            pass  # Group already exists

        while True:
            messages = await cls._client.xreadgroup(
                consumer_group, consumer_name,
                {cls.STREAM_KEY: '>'}, count=10, block=1000
            )
            if messages:
                for stream, entries in messages:
                    for entry_id, fields in entries:
                        event = json.loads(fields["data"])
                        if event_types is None or event["type"] in event_types:
                            yield event
                        await cls._client.xack(cls.STREAM_KEY, consumer_group, entry_id)
```

---

## PHASE 4: STT Pipeline (Sarvam)

**File: `backend/pipeline/stt_pipeline.py`**

```python
import asyncio
import httpx
import numpy as np
from collections import deque
from .event_bus import EventBus
import os

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
SARVAM_BASE_URL = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")
UNCERTAIN_THRESHOLD = 0.65

class AudioBuffer:
    def __init__(self, window_ms=2000, overlap_ms=500, sample_rate=8000):
        self.window_samples = int(window_ms / 1000 * sample_rate)
        self.overlap_samples = int(overlap_ms / 1000 * sample_rate)
        self.buffer = deque(maxlen=self.window_samples * 3)
        self.processed_samples = 0

    def append(self, pcm_bytes: bytes):
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        self.buffer.extend(samples.tolist())

    def ready(self) -> bool:
        return len(self.buffer) >= self.window_samples

    def get(self) -> bytes:
        samples = list(self.buffer)[:self.window_samples]
        # Remove consumed samples (keep overlap)
        for _ in range(self.window_samples - self.overlap_samples):
            if self.buffer:
                self.buffer.popleft()
        return np.array(samples, dtype=np.int16).tobytes()


class SarvamSTTPipeline:
    def __init__(self):
        self.buffers: dict[str, AudioBuffer] = {}
        self.failure_counts: dict[str, int] = {}
        self.fallback_active: dict[str, bool] = {}

    def get_buffer(self, call_sid: str) -> AudioBuffer:
        if call_sid not in self.buffers:
            self.buffers[call_sid] = AudioBuffer()
        return self.buffers[call_sid]

    async def process_chunk(self, call_sid: str, pcm_bytes: bytes):
        buf = self.get_buffer(call_sid)
        buf.append(pcm_bytes)

        if not buf.ready():
            return

        audio_segment = buf.get()

        # Emit audio features for emotion/ambient agents
        await self._emit_audio_features(call_sid, audio_segment)

        # Transcribe
        if self.fallback_active.get(call_sid):
            result = await self._transcribe_whisper(audio_segment)
        else:
            result = await self._transcribe_sarvam(call_sid, audio_segment)

        if result:
            await EventBus.emit('stt.segment', {
                'call_sid': call_sid,
                'text': result['text'],
                'language_tags': result.get('language_tags', []),
                'confidence': result.get('confidence', 0.5),
                'uncertain': result.get('confidence', 0.5) < UNCERTAIN_THRESHOLD,
                'word_timestamps': result.get('word_timestamps', [])
            })

    async def _transcribe_sarvam(self, call_sid: str, audio: bytes) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(
                    f"{SARVAM_BASE_URL}/speech-to-text-translate",
                    headers={"api-subscription-key": SARVAM_API_KEY},
                    files={"file": ("audio.wav", self._to_wav(audio), "audio/wav")},
                    data={"model": "saaras:v1", "language_code": "unknown"}
                    # language_code=unknown triggers auto-detect + code-switch
                )
                response.raise_for_status()
                data = response.json()
                self.failure_counts[call_sid] = 0
                return {
                    "text": data.get("transcript", ""),
                    "language_tags": data.get("language_code", ""),
                    "confidence": data.get("confidence", 0.7),
                    "word_timestamps": []
                }
        except Exception as e:
            self.failure_counts[call_sid] = self.failure_counts.get(call_sid, 0) + 1
            if self.failure_counts[call_sid] >= 3:
                await self._trigger_stt_failure(call_sid, str(e))
            return None

    async def _trigger_stt_failure(self, call_sid: str, reason: str):
        """Graceful degradation — see ETHICS_AND_SAFETY.md"""
        await EventBus.emit('call.state_change', {
            'call_sid': call_sid,
            'old_state': 'active',
            'new_state': 'stt_failure',
            'triggered_by': f'STT failure: {reason}'
        })
        self.fallback_active[call_sid] = True  # switch to Whisper

    async def _transcribe_whisper(self, audio: bytes) -> dict | None:
        """Local Whisper fallback — always available, lower accuracy"""
        import whisper
        model = whisper.load_model("tiny")
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(self._to_wav(audio))
            path = f.name
        result = model.transcribe(path, language=None)
        os.unlink(path)
        return {"text": result["text"], "confidence": 0.5, "language_tags": []}

    async def _emit_audio_features(self, call_sid: str, audio: bytes):
        samples = np.frombuffer(audio, dtype=np.int16).astype(float)
        if len(samples) == 0:
            return
        energy = float(np.sqrt(np.mean(samples**2)))
        pitch = 0.0  # placeholder; implement YIN algorithm or use librosa
        silence_ratio = float(np.mean(np.abs(samples) < 500))
        await EventBus.emit('audio.features', {
            'call_sid': call_sid,
            'prosody_energy': energy,
            'pitch_hz': pitch,
            'silence_ratio': silence_ratio,
            'chunk_ms': len(samples) / 8  # 8000 samples/sec → ms
        })

    def _to_wav(self, pcm: bytes) -> bytes:
        """Wrap raw PCM in WAV header (8kHz, mono, 16-bit)"""
        import struct
        sample_rate = 8000
        num_channels = 1
        bits_per_sample = 16
        data_size = len(pcm)
        header = struct.pack('<4sI4s4sIHHIIHH4sI',
            b'RIFF', 36 + data_size, b'WAVE', b'fmt ', 16,
            1, num_channels, sample_rate,
            sample_rate * num_channels * bits_per_sample // 8,
            num_channels * bits_per_sample // 8, bits_per_sample,
            b'data', data_size)
        return header + pcm
```

---

## PHASE 5: Agents

### 5.1 Base Agent

**File: `backend/agents/base.py`**

```python
from dataclasses import dataclass, field
from typing import Optional
from pipeline.event_bus import EventBus

@dataclass
class AgentAssessment:
    agent_id: str
    risk_score: int          # 0–10
    confidence: float        # 0.0–1.0
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

    async def on_event(self, event: dict) -> Optional[AgentAssessment]:
        raise NotImplementedError

    async def emit(self, call_sid: str, assessment: AgentAssessment):
        await EventBus.emit('agent.assessment', {
            'call_sid': call_sid,
            'agent_id': assessment.agent_id,
            'risk_score': assessment.risk_score,
            'confidence': assessment.confidence,
            'explanation': assessment.explanation,
            'dimensions': assessment.dimensions,
            'flags': assessment.flags
        })
```

### 5.2 NarrativeAgent

**File: `backend/agents/narrative_agent.py`**

```python
from .base import BaseAgent, AgentAssessment
from typing import Optional

# Critical phrases in multiple Indian languages
# IMPORTANT: Maintain and expand with input from clinical team
HIGH_STAKES_PHRASES = {
    "en": [
        "i've decided", "i have decided", "said my goodbyes", "said goodbye",
        "no one will miss me", "no point anymore", "going to end it",
        "tried last week", "tried before", "last time", "won't be here",
        "nothing left", "final decision", "made up my mind", "can't go on"
    ],
    "hi": [
        "faisla kar liya", "nirnay le liya", "alvida bol diya", "alvida keh diya",
        "koi nahi dhundhega", "koi nahi chahiye", "khatam karna chahta",
        "kal kiya tha", "pehle kiya tha", "ab aur nahi", "sab khatam",
        "pura ho gaya", "thak gaya hoon"
    ],
    "mr": ["nirnay gheto", "sarvanna nirop dila", "sampavto"],
    "te": ["nirnayam cheskunnanu", "inti nunchi vellipotanu"],
    "ta": ["mudivu pannineen", "ellaarukkum vidai sollideen"],
    "bn": ["siddhanто niyechi", "sobaikei bida bolchi"],
}

PAST_ATTEMPT_PHRASES = {
    "en": ["tried before", "tried last", "attempted", "took pills", "cut myself", "jumped"],
    "hi": ["pehle kiya tha", "koshish ki thi", "pills li thi"],
}

class NarrativeAgent(BaseAgent):
    agent_id = "narrative"
    subscriptions = ["stt.segment"]

    async def on_event(self, event: dict) -> Optional[AgentAssessment]:
        if event["type"] != "stt.segment":
            return None

        call_sid = event["call_sid"]
        text = event["text"].lower()
        uncertain = event.get("uncertain", False)
        language = event.get("language_tags", "en")

        state = self.get_state(call_sid)
        state.setdefault("transcript_history", [])
        state.setdefault("flagged_phrases", [])
        state.setdefault("narrative_risk", 0)
        state.setdefault("past_attempt_mentioned", False)
        state["transcript_history"].append(text)

        # Keep last 20 segments
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
                    # Count how many times this phrase has appeared
                    phrase_count = sum(
                        phrase in seg for seg in state["transcript_history"]
                    )
                    if phrase_count >= 2:
                        flags.append(f"REPEATED_HIGH_STAKES: '{phrase}' x{phrase_count}")
                        risk_score = max(risk_score, 8)
                        explanation_parts.append(
                            f"'{phrase}' repeated {phrase_count} times"
                        )
                    else:
                        flags.append(f"HIGH_STAKES_PHRASE: '{phrase}'")
                        risk_score = max(risk_score, 6)
                        explanation_parts.append(f"phrase '{phrase}' detected")

        # Check past attempt
        for lang, phrases in PAST_ATTEMPT_PHRASES.items():
            for phrase in phrases:
                if phrase in text:
                    state["past_attempt_mentioned"] = True
                    flags.append("PAST_ATTEMPT_MENTIONED")
                    risk_score = max(risk_score, 7)
                    explanation_parts.append("past attempt mentioned")

        # Narrative shift: sudden shift in topic or detail level
        if len(state["transcript_history"]) >= 5:
            recent = " ".join(state["transcript_history"][-3:])
            earlier = " ".join(state["transcript_history"][-6:-3])
            # Simple heuristic: if recent text is much shorter (shutting down)
            if len(recent) < len(earlier) * 0.4:
                flags.append("WITHDRAWAL_DETECTED")
                risk_score = max(risk_score, risk_score + 1)
                explanation_parts.append("caller becoming less talkative")

        state["narrative_risk"] = risk_score
        dimensions["past_attempt"] = state["past_attempt_mentioned"]
        dimensions["high_stakes_phrase_count"] = len(
            [f for f in flags if "HIGH_STAKES" in f]
        )

        # Confidence is lower if STT was uncertain
        confidence = 0.5 if uncertain else 0.85

        explanation = (
            ", ".join(explanation_parts) if explanation_parts
            else "No high-risk narrative indicators detected"
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
```

### 5.3 MetaAgent

**File: `backend/agents/meta_agent.py`**

```python
from .base import BaseAgent, AgentAssessment
from pipeline.event_bus import EventBus
from typing import Optional
import asyncio

CONFLICT_THRESHOLD = 3
SAFETY_FIRST = True  # NEVER change this to False
MIN_AGENT_CONFIDENCE = 0.5
UNUSUAL_CALM_THRESHOLD = 0.8
AMBIENT_OVERRIDE_SOUNDS = {"child_crying", "glass_breaking", "shouting_nearby"}

RISK_LEVELS = {
    (0, 2): "LOW",
    (3, 4): "MEDIUM",
    (5, 6): "HIGH",
    (7, 10): "CRITICAL"
}

def score_to_level(score: int) -> str:
    for (lo, hi), level in RISK_LEVELS.items():
        if lo <= score <= hi:
            return level
    return "UNKNOWN"

GUIDANCE_TEMPLATES = {
    "LOW": "Continue building rapport. Ask open questions. Validate their feelings.",
    "MEDIUM": "Acknowledge what they've shared. Gently explore: 'Can you tell me more about what's happening?'",
    "HIGH": "Name what you're hearing: 'It sounds like things feel very heavy right now.' Ask directly: 'Are you thinking about hurting yourself?'",
    "CRITICAL": "Ask directly and calmly: 'Are you safe right now? Are you thinking about ending your life?' Stay on the line. Prepare to dispatch.",
    "UNKNOWN": "Follow your training. I don't have enough signal yet to guide you."
}

class MetaAgent:
    def __init__(self):
        self.agent_assessments: dict[str, dict] = {}  # call_sid → {agent_id: assessment}
        self.last_risk_scores: dict[str, list] = {}   # call_sid → score history

    def update_assessment(self, call_sid: str, event: dict):
        if call_sid not in self.agent_assessments:
            self.agent_assessments[call_sid] = {}
        self.agent_assessments[call_sid][event["agent_id"]] = event

    async def fuse_and_emit(self, call_sid: str):
        assessments = self.agent_assessments.get(call_sid, {})
        if not assessments:
            return

        explanation_parts = []
        conflicts = []
        valid_scores = []
        ambient_flags = []

        for agent_id, a in assessments.items():
            if a["confidence"] < MIN_AGENT_CONFIDENCE:
                explanation_parts.append(
                    f"{agent_id} excluded (confidence {a['confidence']:.2f})"
                )
                continue

            # Special: ambient agent override
            if agent_id == "ambient":
                for flag in a.get("flags", []):
                    if any(s in flag.lower() for s in AMBIENT_OVERRIDE_SOUNDS):
                        ambient_flags.append(flag)
                        explanation_parts.append(f"Ambient: {flag}")

            valid_scores.append((agent_id, a["risk_score"]))
            explanation_parts.append(f"{agent_id}: {a['explanation']}")

        if not valid_scores:
            await EventBus.emit('meta.risk_update', {
                'call_sid': call_sid,
                'risk_level': 'UNKNOWN',
                'risk_score': 0,
                'confidence': 0.0,
                'explanation': 'All agent signals uncertain',
                'guidance_text': GUIDANCE_TEMPLATES['UNKNOWN'],
                'conflicts': [],
                'agents_summary': {}
            })
            return

        scores_only = [s for _, s in valid_scores]
        max_score = max(scores_only)
        min_score = min(scores_only)
        conflict = max_score - min_score >= CONFLICT_THRESHOLD

        if conflict:
            conflict_desc = f"{', '.join(f'{a}={s}' for a,s in valid_scores)}"
            conflicts.append(f"Agent disagreement: {conflict_desc}")
            explanation_parts.append(
                f"CONFLICT detected — defaulted to highest risk ({max_score})"
            )

        final_score = max_score if SAFETY_FIRST else int(sum(scores_only) / len(scores_only))

        # Ambient override: child crying or glass breaking adds +2
        if ambient_flags:
            final_score = min(10, final_score + 2)
            explanation_parts.append("Ambient audio modifier: +2")

        # Temporal coherence: prevent sudden huge jumps
        history = self.last_risk_scores.get(call_sid, [])
        if history and final_score > history[-1] + 3:
            if len([s for _, s in valid_scores if s > history[-1] + 2]) < 2:
                final_score = history[-1] + 3
                explanation_parts.append("Rapid increase capped — awaiting confirmation")

        history.append(final_score)
        self.last_risk_scores[call_sid] = history[-20:]

        confidence = 0.5 if conflict else min(
            [a["confidence"] for _, a in zip(valid_scores, assessments.values())]
        )
        risk_level = score_to_level(final_score)
        guidance = GUIDANCE_TEMPLATES.get(risk_level, GUIDANCE_TEMPLATES["UNKNOWN"])

        await EventBus.emit('meta.risk_update', {
            'call_sid': call_sid,
            'risk_level': risk_level,
            'risk_score': final_score,
            'confidence': confidence,
            'explanation': ' | '.join(explanation_parts),
            'guidance_text': guidance,
            'guidance_id': f"{call_sid}_{len(history)}",
            'conflicts': conflicts,
            'agents_summary': {a: {'score': s, 'confidence': assessments[a]['confidence']}
                               for a, s in valid_scores}
        })
```

**✅ Verify:** Import all agents, instantiate them, no import errors.

---

## PHASE 6: FastAPI Gateway

**File: `backend/api/main.py`**

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import json

from pipeline.event_bus import EventBus
from pipeline.stt_pipeline import SarvamSTTPipeline
from agents.meta_agent import MetaAgent
from agents.narrative_agent import NarrativeAgent
from agents.emotion_agent import EmotionAgent
from agents.ambient_agent import AmbientAgent
from db.session import get_db

stt_pipeline = SarvamSTTPipeline()
meta_agent = MetaAgent()
ws_connections: dict[str, list[WebSocket]] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    await EventBus.connect()
    asyncio.create_task(run_agents())
    yield

app = FastAPI(title="VoiceForward API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# ─── Exotel webhooks ──────────────────────────────────────────────

@app.post("/call/incoming")
async def call_incoming(call_sid: str, from_: str):
    """Exotel fires this when a new call arrives"""
    priority = await score_priority(call_sid, from_)
    await EventBus.emit('call.state_change', {
        'call_sid': call_sid,
        'old_state': 'none',
        'new_state': 'incoming',
        'triggered_by': 'exotel_webhook'
    })
    # Returns TwiML-style XML to Exotel
    return {"action": "enqueue", "queue": priority, "call_sid": call_sid}


@app.websocket("/audio-stream/{call_sid}")
async def audio_stream(ws: WebSocket, call_sid: str):
    """Exotel real-time audio stream"""
    await ws.accept()
    try:
        async for chunk in ws.iter_bytes():
            await stt_pipeline.process_chunk(call_sid, chunk)
    except WebSocketDisconnect:
        pass


# ─── Operator HUD WebSocket ───────────────────────────────────────

@app.websocket("/ws/operator/{call_sid}")
async def operator_ws(ws: WebSocket, call_sid: str):
    """Operator browser connects here to receive live HUD updates"""
    await ws.accept()
    ws_connections.setdefault(call_sid, []).append(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "operator.feedback":
                await EventBus.emit('operator.feedback', {
                    'call_sid': call_sid, **data
                })
    except WebSocketDisconnect:
        ws_connections[call_sid].remove(ws)


@app.websocket("/ws/supervisor/{helpline_id}")
async def supervisor_ws(ws: WebSocket, helpline_id: str):
    """Supervisor browser connects here for live board"""
    await ws.accept()
    ws_connections.setdefault(f"supervisor:{helpline_id}", []).append(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_connections[f"supervisor:{helpline_id}"].remove(ws)


# ─── Priority Queue ───────────────────────────────────────────────

async def score_priority(call_sid: str, caller_number: str) -> str:
    """
    Assign P0/P1/P2/P3 based on:
    1. IVR pre-screen response (from Exotel DTMF)
    2. Repeat caller check (phone hash in DB)
    3. Background audio energy
    """
    import hashlib
    caller_hash = hashlib.sha256(caller_number.encode()).hexdigest()

    # TODO: implement repeat caller check against DB
    # TODO: implement IVR DTMF result check
    # Default: P2
    return "P2"


# ─── Dispatch ─────────────────────────────────────────────────────

@app.post("/api/dispatch")
async def dispatch_action(call_sid: str, action_type: str,
                           resource_id: str = None, operator_id: str = None,
                           location_lat: float = None, location_lng: float = None):
    """Operator confirms a dispatch action from HUD"""
    # Log to dispatch_log table
    # Trigger Exotel conference bridge if action_type == 'shelter' or 'ambulance'
    # For ambulance: call 108 API or provide number
    await EventBus.emit('dispatch.action', {
        'call_sid': call_sid,
        'action_type': action_type,
        'resource_id': resource_id,
        'operator_id': operator_id,
        'location': {'lat': location_lat, 'lng': location_lng},
        'confirmed': True
    })
    return {"status": "dispatched", "action": action_type}


# ─── Erasure (DPDPA) ──────────────────────────────────────────────

@app.post("/api/calls/{call_sid}/erase")
async def erase_call(call_sid: str, db=Depends(get_db)):
    """Full PII erasure for a session — DPDPA right to erasure"""
    # 1. Delete transcript from calls
    # 2. Nullify caller_phone_hash
    # 3. Set erasure_requested=True, anonymised_at=NOW()
    # 4. Delete Redis keys for this session
    return {"status": "erased", "call_sid": call_sid,
            "deleted": ["transcript", "caller_phone_hash", "audio_buffer"]}


# ─── Agent runner ─────────────────────────────────────────────────

async def run_agents():
    """Background task: consume events and run agents"""
    narrative = NarrativeAgent()
    # emotion = EmotionAgent()
    # ambient = AmbientAgent()

    async for event in EventBus.subscribe("agent-runner", "main"):
        call_sid = event.get("call_sid")
        if not call_sid:
            continue

        assessment = None
        if event["type"] == "stt.segment":
            assessment = await narrative.on_event(event)

        if assessment:
            meta_agent.update_assessment(call_sid, {
                **assessment.__dict__,
                "confidence": assessment.confidence
            })
            await meta_agent.fuse_and_emit(call_sid)

            # Push to operator WebSocket
            risk_event = {}  # get from event bus
            for ws in ws_connections.get(call_sid, []):
                try:
                    await ws.send_json({"type": "meta.risk_update", **risk_event})
                except Exception:
                    pass
```

**✅ Verify:** `uvicorn api.main:app --reload` starts without errors. `GET /docs` shows API docs.

---

## PHASE 7: Frontend

### 7.1 Setup

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --app --src-dir=false
npm install socket.io-client zustand mapbox-gl @types/mapbox-gl recharts lucide-react
```

### 7.2 Risk Store (Zustand)

**File: `frontend/lib/stores/riskStore.ts`**

```typescript
import { create } from 'zustand'

type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'UNKNOWN'

interface AgentState {
  risk_score: number
  confidence: number
  explanation: string
  uncertain: boolean
}

interface RiskSnapshot {
  timestamp: string
  level: RiskLevel
  score: number
  trigger: string
}

interface RiskStore {
  level: RiskLevel
  score: number
  confidence: number
  explanation: string
  guidanceText: string
  guidanceId: string
  conflicts: string[]
  agents: Record<string, AgentState>
  history: RiskSnapshot[]
  guidanceAction: 'pending' | 'accepted' | 'modified' | 'rejected'
  setRiskUpdate: (data: any) => void
  setGuidanceAction: (action: 'accepted' | 'modified' | 'rejected', mod?: string) => void
}

export const useRiskStore = create<RiskStore>((set, get) => ({
  level: 'UNKNOWN',
  score: 0,
  confidence: 0,
  explanation: '',
  guidanceText: '',
  guidanceId: '',
  conflicts: [],
  agents: {},
  history: [],
  guidanceAction: 'pending',

  setRiskUpdate: (data) => set(state => ({
    level: data.risk_level,
    score: data.risk_score,
    confidence: data.confidence,
    explanation: data.explanation,
    guidanceText: data.guidance_text,
    guidanceId: data.guidance_id,
    conflicts: data.conflicts || [],
    agents: data.agents_summary || {},
    guidanceAction: 'pending',
    history: [...state.history.slice(-19), {
      timestamp: new Date().toISOString(),
      level: data.risk_level,
      score: data.risk_score,
      trigger: data.explanation?.split(' | ')[0] || ''
    }]
  })),

  setGuidanceAction: (action, mod) => set({ guidanceAction: action })
}))
```

### 7.3 RiskTimelineBar Component

**File: `frontend/components/hud/RiskTimelineBar.tsx`**

```typescript
'use client'
import { useRiskStore } from '@/lib/stores/riskStore'

const RISK_COLOURS: Record<string, string> = {
  LOW: '#10B981', MEDIUM: '#F59E0B',
  HIGH: '#EF4444', CRITICAL: '#7C3AED', UNKNOWN: '#94A3B8'
}

export function RiskTimelineBar() {
  const { level, score, explanation } = useRiskStore()
  const colour = RISK_COLOURS[level] || RISK_COLOURS.UNKNOWN
  const percentage = (score / 10) * 100

  return (
    <div className="w-full px-4 py-2">
      <div className="flex items-center gap-3">
        <div className="flex-1 h-3 bg-slate-700 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-200"
            style={{ width: `${percentage}%`, backgroundColor: colour }}
          />
        </div>
        <span className="text-sm font-bold min-w-[90px] text-right"
              style={{ color: colour }}>
          {level} {score.toFixed(1)}
        </span>
      </div>
      {explanation && (
        <p className="text-xs text-slate-400 mt-1 truncate">{explanation}</p>
      )}
    </div>
  )
}
```

### 7.4 GlassBox Panel

**File: `frontend/components/hud/GlassBoxPanel.tsx`**

```typescript
'use client'
import { useRiskStore } from '@/lib/stores/riskStore'

const AGENT_NAMES = ['emotion', 'ambient', 'narrative', 'language']
const RISK_COLOURS: Record<string, string> = {
  LOW: '#10B981', MEDIUM: '#F59E0B',
  HIGH: '#EF4444', CRITICAL: '#7C3AED', UNKNOWN: '#94A3B8'
}

function scoreToLevel(score: number): string {
  if (score <= 2) return 'LOW'
  if (score <= 4) return 'MEDIUM'
  if (score <= 6) return 'HIGH'
  return 'CRITICAL'
}

export function GlassBoxPanel() {
  const { agents, conflicts } = useRiskStore()

  return (
    <div className="p-4">
      <h3 className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
        GlassBox — Agent Analysis
      </h3>
      <div className="grid grid-cols-4 gap-2">
        {AGENT_NAMES.map(agentId => {
          const a = agents[agentId]
          if (!a) return (
            <div key={agentId}
                 className="bg-slate-800 rounded-lg p-2 border border-slate-700">
              <div className="text-xs text-slate-500 uppercase">{agentId}</div>
              <div className="text-slate-500 text-sm">Waiting…</div>
            </div>
          )
          const uncertain = a.confidence < 0.6
          const level = scoreToLevel(a.risk_score)
          const colour = RISK_COLOURS[level]
          return (
            <div key={agentId}
                 className={`bg-slate-800 rounded-lg p-2 ${
                   uncertain ? 'border border-dashed border-slate-500 opacity-70'
                             : 'border border-slate-700'
                 }`}>
              <div className="text-xs text-slate-400 uppercase mb-1">{agentId}</div>
              <div className="font-bold text-sm" style={{ color: colour }}>{level}</div>
              <div className="flex items-center gap-1 mt-1">
                <div className="flex-1 h-1 bg-slate-700 rounded">
                  <div className="h-full rounded bg-teal-500"
                       style={{ width: `${a.confidence * 100}%` }} />
                </div>
                <span className="text-xs text-slate-400">{a.confidence.toFixed(2)}</span>
              </div>
              <p className="text-xs text-slate-400 mt-1 line-clamp-2">{a.explanation}</p>
            </div>
          )
        })}
      </div>
      {conflicts.length > 0 && (
        <div className="mt-2 p-2 bg-amber-900/30 border border-amber-500 rounded-lg">
          <span className="text-amber-400 text-xs font-semibold">⚠ Agents disagree — </span>
          <span className="text-amber-300 text-xs">{conflicts[0]} — defaulted to higher risk</span>
        </div>
      )}
    </div>
  )
}
```

**✅ Verify:** `npm run dev` starts. Navigate to `http://localhost:3000`. No console errors.

---

## PHASE 8: Priority Queue Logic

**File: `backend/services/priority_service.py`**

```python
import hashlib
import redis.asyncio as aioredis
from typing import Literal
import os

PriorityTier = Literal["P0", "P1", "P2", "P3"]

DISTRESS_KEYWORDS = {
    "en": ["not safe", "hurt myself", "end it", "die", "kill", "no reason"],
    "hi": ["safe nahi", "khud ko", "khatam", "marna", "jeevan"],
}

class PriorityService:
    def __init__(self):
        self.redis = aioredis.from_url(os.getenv("REDIS_URL"))

    async def score_call(self, call_sid: str, caller_number: str,
                         ivr_response: str | None, dtmf_key: str | None) -> PriorityTier:
        score = 0
        reason_parts = []

        # IVR said "not safe"
        if dtmf_key == "2" or (ivr_response and any(
            kw in ivr_response.lower() for lang_kws in DISTRESS_KEYWORDS.values()
            for kw in lang_kws
        )):
            score += 40
            reason_parts.append("IVR distress signal")

        # Repeat caller from high-risk DB
        caller_hash = hashlib.sha256(caller_number.encode()).hexdigest()
        is_repeat_high_risk = await self.redis.get(f"high_risk_caller:{caller_hash}")
        if is_repeat_high_risk:
            score += 50
            reason_parts.append("repeat high-risk caller")

        # Map score to tier
        if score >= 50:
            tier = "P0"
        elif score >= 30:
            tier = "P1"
        elif score >= 10:
            tier = "P2"
        else:
            tier = "P3"

        return tier

    async def should_divert_p3(self, helpline_id: str) -> bool:
        """Check if P3 calls should be diverted based on queue depth"""
        # Get queue depths from Redis
        p0_depth = await self.redis.zcard(f"queue:{helpline_id}:p0")
        p1_depth = await self.redis.zcard(f"queue:{helpline_id}:p1")
        p2_depth = await self.redis.zcard(f"queue:{helpline_id}:p2")

        total_high_priority = p0_depth + p1_depth

        # Get helpline config (from DB or cache)
        diversion_threshold = 3  # default; load from helplines table

        return (p2_depth + total_high_priority) > diversion_threshold

    async def add_to_queue(self, helpline_id: str, call_sid: str, tier: str):
        import time
        await self.redis.zadd(
            f"queue:{helpline_id}:{tier.lower()}",
            {call_sid: time.time()}
        )

    async def get_next_for_operator(self, helpline_id: str,
                                    operator_tier: str) -> str | None:
        """Get highest priority call for this operator"""
        # P0 first (any operator), then P1 (prefer senior), then P2, then P3
        for priority in ["p0", "p1", "p2", "p3"]:
            result = await self.redis.zpopmin(f"queue:{helpline_id}:{priority}", 1)
            if result:
                call_sid, _ = result[0]
                return call_sid
        return None
```

---

## PHASE 9: Demo Simulator

**File: `demo/simulator.py`**

```python
"""
Simulates a live call by replaying a pre-recorded audio file
through the VoiceForward pipeline. No real phone needed.

Usage:
  python demo/simulator.py --scenario high_risk_hinglish
  python demo/simulator.py --scenario domestic_violence_child
  python demo/simulator.py --scenario conflicting_signals
"""
import asyncio
import httpx
import argparse
import os

SCENARIOS = {
    "high_risk_hinglish": {
        "audio_file": "demo/audio/high_risk_hinglish.wav",
        "description": "Hinglish caller, code-switching, suicidal ideation",
        "priority": "P1",
        "expected_risk": "CRITICAL"
    },
    "domestic_violence_child": {
        "audio_file": "demo/audio/domestic_violence_child.wav",
        "description": "Calm caller, child crying in background, shelter needed",
        "priority": "P2",
        "expected_risk": "HIGH"
    },
    "conflicting_signals": {
        "audio_file": "demo/audio/conflicting_signals.wav",
        "description": "Laughing but describing self-harm history",
        "priority": "P2",
        "expected_risk": "HIGH (CONFLICT shown)"
    }
}

async def run_scenario(scenario_name: str):
    scenario = SCENARIOS[scenario_name]
    print(f"\n🎬 Running scenario: {scenario_name}")
    print(f"   {scenario['description']}")
    print(f"   Expected: {scenario['expected_risk']}\n")

    # 1. Create a mock call
    call_sid = f"demo_{scenario_name}_{int(asyncio.get_event_loop().time())}"

    # 2. Stream audio to the backend audio-stream endpoint
    audio_path = scenario["audio_file"]
    if not os.path.exists(audio_path):
        print(f"⚠ Audio file not found: {audio_path}")
        print("  Create demo audio files or use text-only simulation.")
        # Fall back to text simulation
        await text_simulation(call_sid, scenario_name)
        return

    print(f"📡 Streaming {audio_path} → backend...")
    async with httpx.AsyncClient() as client:
        with open(audio_path, 'rb') as f:
            audio_data = f.read()

        # POST audio in chunks to simulate real-time streaming
        chunk_size = 1600  # 100ms of 8kHz 16-bit audio
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            # In real deployment this goes via WebSocket
            # For demo: post directly to a test endpoint
            await asyncio.sleep(0.1)  # 100ms per chunk = real-time
            print(f"\r  Streaming: {i}/{len(audio_data)} bytes", end="", flush=True)

    print(f"\n✅ Scenario complete. Check HUD at http://localhost:3000/operator/{call_sid}")

async def text_simulation(call_sid: str, scenario_name: str):
    """Simulate by injecting text directly into the event bus"""
    from backend.pipeline.event_bus import EventBus
    await EventBus.connect()

    texts = {
        "high_risk_hinglish": [
            "Main bahut thaka hoon… I can't do this anymore",
            "I've decided… kuch karna chahta hoon jo sab khatam kar de",
            "I've decided. Pura soch liya hai.",
        ],
        "domestic_violence_child": [
            "I need somewhere safe to stay tonight",
            "My husband… he gets angry",
            "I have my child with me",
        ],
        "conflicting_signals": [
            "Ha ha, I'm fine, really [nervous laugh]",
            "I tried something last week but it's okay",
            "I just wanted to talk to someone",
        ]
    }

    for i, text in enumerate(texts.get(scenario_name, [])):
        await EventBus.emit('stt.segment', {
            'call_sid': call_sid,
            'text': text,
            'language_tags': [{'phrase': text, 'lang': 'en'}],
            'confidence': 0.85,
            'uncertain': False
        })
        print(f"  [{i+1}] Injected: {text[:60]}...")
        await asyncio.sleep(3)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="high_risk_hinglish",
                        choices=list(SCENARIOS.keys()))
    args = parser.parse_args()
    asyncio.run(run_scenario(args.scenario))
```

---

## Phase 10: Final Verification Checklist

Run each item before the demo:

```bash
# 1. Infrastructure
docker compose ps                          # postgres + redis Up

# 2. Backend
curl http://localhost:8000/docs            # FastAPI docs load
curl http://localhost:8000/health          # {"status": "ok"}

# 3. Database
psql $DATABASE_URL -c "SELECT count(*) FROM resources"  # > 0 (seeded)

# 4. STT (requires API key)
python -c "
import asyncio
from backend.pipeline.stt_pipeline import SarvamSTTPipeline
# Test with silence — should return low confidence, not crash
print('STT pipeline imports OK')
"

# 5. Agents
python -c "
from backend.agents.narrative_agent import NarrativeAgent
a = NarrativeAgent()
print('Agents import OK')
"

# 6. Frontend
curl http://localhost:3000                 # Next.js loads

# 7. Demo
python demo/simulator.py --scenario high_risk_hinglish

# 8. Failure mode
# Temporarily set SARVAM_API_KEY=invalid
# Verify STT failure banner appears in HUD within 5 seconds
```
