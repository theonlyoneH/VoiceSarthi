# ARCHITECTURE — VoiceForward GlassBox Copilot

## 1. System Overview Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CALLER (PSTN)                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ phone call
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXOTEL PLATFORM                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ IVR         │  │ Priority     │  │ Real-Time Audio        │ │
│  │ Pre-Screen  │  │ Queue Router │  │ Stream (WebSocket)     │ │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬─────────────┘ │
└─────────┼───────────────┼────────────────────  ┼───────────────┘
          │               │                       │
          ▼               ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                            │
│                                                                 │
│  ┌─────────────────┐    ┌──────────────────────────────────┐   │
│  │  API Gateway    │    │      AUDIO PIPELINE              │   │
│  │  /call/incoming │    │  AudioIngest → Buffer →          │   │
│  │  /call/queue    │    │  SarvamSTT → EventBus emit       │   │
│  │  /dispatch      │    └──────────────┬───────────────────┘   │
│  │  /erase         │                   │                       │
│  └────────┬────────┘         stt.segment event                 │
│           │                             │                       │
│           │              ┌──────────────▼───────────────────┐  │
│           │              │         EVENT BUS (Redis)        │  │
│           │              │  stt.segment, audio.features,    │  │
│           │              │  agent.assessment, meta.update   │  │
│           │              └───┬───────┬────────┬────────┬────┘  │
│           │                  │       │        │        │        │
│           │           ┌──────▼┐ ┌────▼──┐ ┌──▼───┐ ┌──▼────┐  │
│           │           │Emotion│ │Ambient│ │Narrat│ │Languag│  │
│           │           │Agent  │ │Agent  │ │Agent │ │Agent  │  │
│           │           └──────┬┘ └────┬──┘ └──┬───┘ └──┬────┘  │
│           │                  │       │        │        │        │
│           │           ┌──────▼───────▼────────▼────────▼────┐  │
│           │           │           META AGENT                │  │
│           │           │  conflict resolve → explanation →   │  │
│           │           │  risk level → guidance text         │  │
│           │           └────────────────┬────────────────────┘  │
│           │                            │ meta.risk_update       │
│           │           ┌────────────────▼────────────────────┐  │
│           │           │        WS SERVER                    │  │
│           │           │  pushes HUD updates to frontend     │  │
│           │           └────────────────┬────────────────────┘  │
└───────────┼────────────────────────────┼────────────────────────┘
            │                            │ WebSocket
            │                            ▼
┌───────────▼────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js)                          │
│                                                                │
│  ┌──────────────────────┐   ┌──────────────────────────────┐  │
│  │   OPERATOR HUD       │   │   SUPERVISOR DASHBOARD       │  │
│  │  ┌────┬────────┬────┐│   │  ┌────────────────────────┐  │  │
│  │  │Left│ Centre │Right││   │  │ Live Calls Board       │  │  │
│  │  │Guid│RiskBar │Rsrc ││   │  │ Priority Queue Panel   │  │  │
│  │  │ance│GlassBox│Map  ││   │  │ Diversion Log          │  │  │
│  │  └────┴────────┴────┘│   │  │ Analytics Charts       │  │  │
│  └──────────────────────┘   │  └────────────────────────┘  │  │
│                              └──────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────┐
│  STORAGE (PostgreSQL + Redis)     │
│  calls, ai_suggestions,           │
│  resources, operators,            │
│  audit_log, diversion_log         │
└───────────────────────────────────┘
```

---

## 2. Call Lifecycle & Priority Routing

```
Incoming call (Exotel)
        │
        ▼
[IVR Pre-Screen — 10 seconds]
  "Are you safe right now? Press 1 yes, 2 no. Say your language."
        │
        ├── Caller says "no" / screaming / crying detected → P0
        ├── Caller says "no" / distress keywords → P1
        ├── Caller says "yes" / general inquiry → P2 or P3
        └── Repeat number in high-risk DB → P0 regardless of IVR
        │
        ▼
[Priority Scorer] → assigns P0/P1/P2/P3
        │
        ▼
[Queue Router]
        │
        ├── P0: broadcast alert to ALL available operators
        │         └── if no operator free in 60s → supervisor SMS/alert
        │
        ├── P1: route to most-experienced available operator
        │         └── flag on supervisor live board
        │
        ├── P2: standard queue; next available operator
        │
        └── P3: check queue depth
                  ├── depth ≤ 3: enter queue normally
                  └── depth > 3 OR all operators on P0/P1:
                            → IVR: offer callback / WhatsApp / self-help
                            → log diversion with caller choice
```

---

## 3. Service Map

| Service | Port | Language | Responsibility |
|---|---|---|---|
| `api-gateway` | 8000 | Python/FastAPI | REST API, Exotel webhooks, auth, session management |
| `ws-server` | 8001 | Python/FastAPI | WebSocket connections to operator browsers |
| `audio-pipeline` | internal | Python async | Receives Exotel audio stream, buffers, sends to Sarvam |
| `agent-runner` | internal | Python | Hosts all 5 agents as async workers |
| `meta-agent` | internal | Python | Risk fusion, explanation, guidance generation |
| `resource-service` | 8002 | Python/FastAPI | Resource DB, location-based ranking, dispatch |
| `analytics-service` | 8003 | Python | Post-call anonymisation, phrase-outcome learning |
| `audit-service` | 8004 | Python/FastAPI | Immutable log writer + replay queries |
| `priority-service` | internal | Python | IVR integration, call scoring, diversion logic |
| `frontend` | 3000 | Next.js | Operator HUD, Supervisor Dashboard, Admin |

---

## 4. Event Bus Schema (Redis Streams)

### Stream: `voiceforward:events`

All events carry `call_sid`, `timestamp`, `version`.

```
Event: stt.segment
  text: str
  language_tags: [{phrase: str, lang: str}]
  confidence: float
  uncertain: bool
  word_timestamps: [{word: str, start_ms: int, end_ms: int}]

Event: audio.features
  prosody_energy: float
  pitch_hz: float
  speaking_rate_wpm: float
  silence_ratio: float
  chunk_ms: int

Event: agent.assessment
  agent_id: str  # emotion | ambient | narrative | language | fatigue
  risk_score: int  # 0–10
  confidence: float
  dimensions: dict  # agent-specific breakdown
  explanation: str
  flags: [str]

Event: meta.risk_update
  risk_level: str  # LOW | MEDIUM | HIGH | CRITICAL | UNKNOWN
  risk_score: int
  confidence: float
  explanation: str
  guidance_text: str
  guidance_id: str  # for operator feedback logging
  conflicts: [str]
  agents_summary: dict
  resource_triggers: [str]  # e.g. ["show_shelter", "show_ambulance"]
  location_detected: {city: str, lat: float, lng: float} | null

Event: call.state_change
  old_state: str
  new_state: str
  triggered_by: str

Event: operator.feedback
  suggestion_id: str
  action: str  # accepted | modified | rejected
  operator_id: str
  modification_text: str | null

Event: dispatch.action
  action_type: str  # ambulance | police | shelter | supervisor_ping
  resource_id: str | null
  operator_id: str
  location: {lat: float, lng: float, address: str}
  confirmed: bool

Event: priority.diversion
  priority_tier: str  # P3
  diversion_type: str  # callback | whatsapp | self_help | dropped
  queue_depth_at_time: int
  caller_id_hash: str  # pseudonymised
```

---

## 5. Agent Architecture

Each agent is an async Python class that:
1. Subscribes to relevant event bus streams
2. Maintains state per `call_sid`
3. Emits `agent.assessment` events

```python
# Base pattern for all agents
class BaseAgent:
    agent_id: str
    subscriptions: list[str]  # event types to consume

    async def on_event(self, event: dict) -> AgentAssessment | None:
        raise NotImplementedError

    async def emit_assessment(self, call_sid: str, assessment: AgentAssessment):
        await EventBus.emit('agent.assessment', {
            'call_sid': call_sid,
            'agent_id': self.agent_id,
            **assessment.dict()
        })
```

### MetaAgent Conflict Resolution Priority

```
1. If ANY agent.confidence < 0.5 → exclude from fusion, note in explanation
2. If risk_scores have range > 3 → CONFLICT state
3. In CONFLICT:
   a. NarrativeAgent keywords (past attempt, "I've decided" x2) → override to HIGH
   b. Otherwise: take MAX score among confident agents
   c. Set confidence = 0.5 (explicitly uncertain)
   d. Show conflict banner in HUD
4. If EmotionAgent says "unusual calm" (calm > 0.8 AND distress > 0.6) → +2 to risk score
5. If AmbientAgent detects child crying OR glass breaking → +2 to risk score regardless of others
6. Final risk: clamp to 0–10, map to level:
   0–2: LOW, 3–4: MEDIUM, 5–6: HIGH, 7–10: CRITICAL
```

---

## 6. Sarvam AI Integration Points

| Feature | Sarvam API | Endpoint |
|---|---|---|
| Streaming STT | Saaras v1 | `POST /speech-to-text-translate` (streaming) |
| Code-switch detection | Saaras — `language=auto` | returns `language_code` per utterance |
| TTS for operator cues | Bulbul v1 | `POST /text-to-speech` |
| Translation | Translate API | `POST /translate` — caller language → operator language |
| Transliteration | Transliterate API | For displaying Devanagari terms in Roman script on HUD |

**API Base:** `https://api.sarvam.ai`
**Auth:** `api-subscription-key` header

---

## 7. Telephony Integration (Exotel)

```
Exotel Account Setup:
  ├── Provision PSTN number (1800 or state-specific)
  ├── AppBuilder flow:
  │     Incoming → IVR Pre-Screen → Priority Webhook → Queue
  ├── Real-Time Streaming enabled:
  │     Stream URL: wss://your-backend/audio-stream/{CallSid}
  │     Format: PCM 16-bit, 8kHz, mono
  └── Webhooks:
        /call/incoming    (new call)
        /call/answered    (operator picks up)
        /call/completed   (call ends)
        /dtmf/received    (IVR keypress)

Conference Bridge (for dispatch):
  - Exotel Conference Room per call_sid
  - Operator + Caller in room
  - Supervisor joins as muted participant when shadowing
  - 3-way conference for shelter/NGO connect
```

---

## 8. Frontend State Architecture

```
Zustand Stores:

callStore: {
  callSid: string
  state: CallState
  startedAt: Date
  callerLanguage: string
  priorityTier: PriorityTier
  aiDisclosed: boolean
  optedOut: boolean
  location: GeoLocation | null
}

riskStore: {
  currentLevel: RiskLevel
  currentScore: number
  confidence: number
  explanation: string
  guidanceText: string
  guidanceId: string
  activeGuidanceAction: 'pending' | 'accepted' | 'modified' | 'rejected'
  conflicts: string[]
  history: RiskSnapshot[]  // last 20 snapshots for timeline
}

agentStore: {
  emotion: AgentState
  ambient: AgentState
  narrative: AgentState
  language: AgentState
  fatigue: AgentState
}

resourceStore: {
  resources: Resource[]
  locationDetected: GeoLocation | null
  mapVisible: boolean
  dispatchPending: DispatchAction | null
}

boardStore: {  // supervisor only
  activeCalls: CallCard[]
  queue: QueueItem[]
  diversionLog: DiversionEntry[]
  shadowCallSid: string | null
}
```
