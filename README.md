# VoiceForward — GlassBox Copilot

> Real-time AI intelligence layer for human crisis helpline operators. Not a chatbot. Never autonomous. Always human-first.

---

## What This Is

VoiceForward is a **live AI copilot** that sits beside a human crisis helpline operator during a call. It listens, analyses, and surfaces insights — but the operator always speaks, decides, and acts.

The AI does three things:
1. **Understands** the call in real time (emotion, ambient audio, narrative, language)
2. **Reasons** across multiple agents and resolves conflicts transparently
3. **Surfaces** just enough to the operator — guidance, risk level, resources, map — without cognitive overload

---

## Repo Structure

```
voiceforward/
├── frontend/                  # Next.js 14 — Operator HUD, Supervisor Dashboard
│   ├── app/
│   │   ├── operator/          # Live HUD for active call
│   │   ├── supervisor/        # Live board + analytics
│   │   └── replay/            # Audit replay view
│   ├── components/
│   │   ├── hud/               # RiskBar, GlassBox, GuidancePane, ResourcePanel
│   │   ├── map/               # MapOverlay, ResourcePin, DispatchPanel
│   │   ├── board/             # LiveCallsBoard, CallCard, QueuePanel
│   │   └── shared/            # Buttons, Badges, Toasts
│   └── lib/                   # WebSocket client, Zustand stores, API helpers
│
├── backend/
│   ├── api/                   # FastAPI — REST + WebSocket gateway
│   ├── agents/
│   │   ├── emotion_agent.py
│   │   ├── ambient_agent.py
│   │   ├── narrative_agent.py
│   │   ├── language_agent.py
│   │   ├── fatigue_agent.py
│   │   └── meta_agent.py      # Orchestrator / conflict resolver
│   ├── pipeline/
│   │   ├── audio_ingest.py    # Exotel WebSocket stream handler
│   │   ├── stt_pipeline.py    # Sarvam AI STT integration
│   │   └── event_bus.py       # Redis Streams wrapper
│   ├── services/
│   │   ├── resource_service.py
│   │   ├── dispatch_service.py
│   │   ├── analytics_service.py
│   │   └── audit_service.py
│   └── db/
│       ├── models.py
│       └── migrations/
│
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   └── postgres/init.sql
│
└── demo/
    ├── audio/                 # Pre-recorded demo call files
    └── simulator.py           # Replays audio file as if it were a live call
```

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/your-org/voiceforward
cd voiceforward
cp .env.example .env        # Fill in API keys (see IMPLEMENTATION_GUIDE.md)

# 2. Start infrastructure
docker compose up -d postgres redis

# 3. Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn api.main:app --reload --port 8000

# 4. Frontend
cd frontend
npm install
npm run dev                  # http://localhost:3000

# 5. Run demo (no real phone call needed)
python demo/simulator.py --scenario high_risk_hinglish
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Sarvam AI for STT | Only Indian-native STT with real code-switch support |
| Exotel for telephony | Best PSTN coverage + WebSocket streaming in India |
| Multi-agent with visible conflict | Trust requires transparency; operators reject black boxes |
| Priority queue for call routing | Ensures high-risk / vulnerable callers never wait behind low-priority calls |
| On-prem data storage | DPDPA 2023 compliance; no caller PII leaves India |
| Safety-first defaults | False negative in crisis = catastrophic; false positive = manageable |

---

## Compliance

- **DPDPA 2023** — data localisation, consent, right to erasure
- **MeitY AI Governance** — model versioning, audit trails, human override
- **AI Disclosure** — caller informed within 30 seconds; opt-out available

---

## Docs

| File | Contents |
|---|---|
| `PRD.md` | Product requirements, user stories, acceptance criteria |
| `ARCHITECTURE.md` | System design, data flow, service map |
| `DATABASE_SCHEMA.md` | Full schema with all tables and relationships |
| `UI_SPEC.md` | Every screen, component, and interaction |
| `IMPLEMENTATION_GUIDE.md` | Step-by-step build instructions for AI agent |
| `ETHICS_AND_SAFETY.md` | Failure modes, compliance, hallucination prevention |
| `DEMO_SCRIPT.md` | Scripted scenarios for hackathon demo |
