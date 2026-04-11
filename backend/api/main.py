"""FastAPI Gateway — Main application entry point.
Follows ARCHITECTURE.md Section 3 and IMPLEMENTATION_GUIDE.md Phase 6.
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

# Local imports
from pipeline.event_bus import EventBus
from pipeline.stt_pipeline import SarvamSTTPipeline
from pipeline.audio_ingest import ingest_audio_stream
from agents.meta_agent import MetaAgent
from agents.narrative_agent import NarrativeAgent
from agents.emotion_agent import EmotionAgent
from agents.ambient_agent import AmbientAgent
from agents.language_agent import LanguageAgent
from agents.fatigue_agent import OperatorFatigueAgent
from api.auth import (
    create_access_token, verify_password, get_password_hash,
    get_current_operator, require_supervisor
)
from api.ws import ws_manager
from db.session import get_db
from db.models import Operator, Call, DiversionLog, DispatchLog, AISuggestion
from services.priority_service import PriorityService
from services.resource_service import ResourceService
from services.audit_service import AuditService
from services.dispatch_service import DispatchService

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(name)s %(levelname)s %(message)s"
)

# Global singletons
stt_pipeline = SarvamSTTPipeline()
meta_agent = MetaAgent()
redis_client: aioredis.Redis = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global redis_client

    # Connect Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_client = aioredis.from_url(redis_url, decode_responses=True)

    # Connect EventBus
    await EventBus.connect()

    # Start agent runner background task
    task = asyncio.create_task(run_agent_loop())

    # Start risk update pusher (meta.risk_update → WS + DB audit)
    push_task = asyncio.create_task(push_risk_updates())

    # Start STT segment pusher (stt.segment → operator WS for live transcript)
    stt_task = asyncio.create_task(push_stt_segments())

    logger.info("VoiceForward API started")
    yield

    # Shutdown
    task.cancel()
    push_task.cancel()
    stt_task.cancel()
    await EventBus.disconnect()
    await redis_client.aclose()
    logger.info("VoiceForward API shutdown complete")


app = FastAPI(
    title="VoiceForward GlassBox Copilot API",
    description="Real-time AI copilot for crisis helpline operators",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "voiceforward-api", "version": "1.0.0"}


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    operator = db.query(Operator).filter(
        Operator.email == req.email,
        Operator.active == True
    ).first()
    if not operator or not verify_password(req.password, operator.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(data={"sub": str(operator.id), "role": operator.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "operator": {
            "id": str(operator.id),
            "name": operator.name,
            "role": operator.role,
            "languages": operator.languages,
            "experience_tier": operator.experience_tier,
            "helpline_id": str(operator.helpline_id) if operator.helpline_id else None
        }
    }


@app.get("/api/auth/me")
async def me(operator: Operator = Depends(get_current_operator)):
    return {
        "id": str(operator.id),
        "name": operator.name,
        "role": operator.role,
        "languages": operator.languages,
        "helpline_id": str(operator.helpline_id) if operator.helpline_id else None
    }


# ─── Exotel Webhooks ──────────────────────────────────────────────────────────

@app.post("/call/incoming")
async def call_incoming(request: Request, db: Session = Depends(get_db)):
    """Exotel fires this when a new call arrives."""
    form = await request.form()
    call_sid = form.get("CallSid", f"demo_{datetime.now().timestamp():.0f}")
    from_number = form.get("From", "unknown")
    ivr_response = form.get("SpeechResult", None)
    dtmf_key = form.get("Digits", None)

    priority_svc = PriorityService(redis_client)
    tier, score, reason = await priority_svc.score_call(
        call_sid, from_number, ivr_response, dtmf_key
    )

    # Create call record in DB
    import hashlib
    phone_hash = hashlib.sha256(from_number.encode()).hexdigest()
    call = Call(
        call_sid=call_sid,
        started_at=datetime.now(timezone.utc),
        priority_tier=tier,
        priority_score=score,
        priority_reason=reason,
        caller_phone_hash=phone_hash,
        helpline_id="00000000-0000-0000-0000-000000000001"  # default demo helpline
    )
    db.add(call)
    db.commit()

    # Add to priority queue
    helpline_id = "00000000-0000-0000-0000-000000000001"
    await priority_svc.add_to_queue(helpline_id, call_sid, tier)

    await EventBus.emit('call.state_change', {
        'call_sid': call_sid,
        'old_state': 'none',
        'new_state': 'incoming',
        'triggered_by': 'exotel_webhook',
        'priority_tier': tier
    })

    # P3 diversion check
    if tier == "P3":
        should_divert = await priority_svc.should_divert_p3(helpline_id)
        if should_divert:
            return {
                "action": "divert",
                "options": ["callback", "whatsapp", "self_help"],
                "call_sid": call_sid
            }

    return {"action": "enqueue", "queue": tier, "call_sid": call_sid}


@app.post("/call/answered")
async def call_answered(request: Request, db: Session = Depends(get_db)):
    """Exotel webhook: operator picked up."""
    form = await request.form()
    call_sid = form.get("CallSid")
    if call_sid:
        db.query(Call).filter(Call.call_sid == call_sid).update({
            "answered_at": datetime.now(timezone.utc)
        })
        db.commit()
        await EventBus.emit('call.state_change', {
            'call_sid': call_sid, 'old_state': 'queued', 'new_state': 'answered',
            'triggered_by': 'exotel_webhook'
        })
    return {"status": "ok"}


@app.post("/call/completed")
async def call_completed(request: Request, db: Session = Depends(get_db)):
    """Exotel webhook: call ended."""
    form = await request.form()
    call_sid = form.get("CallSid")
    if call_sid:
        duration = int(form.get("Duration", 0))
        db.query(Call).filter(Call.call_sid == call_sid).update({
            "ended_at": datetime.now(timezone.utc),
            "duration_seconds": duration
        })
        db.commit()
        await EventBus.emit('call.state_change', {
            'call_sid': call_sid, 'old_state': 'active', 'new_state': 'completed',
            'triggered_by': 'exotel_webhook'
        })
    return {"status": "ok"}


# ─── Audio Stream WebSocket ───────────────────────────────────────────────────

@app.websocket("/audio-stream/{call_sid}")
async def audio_stream(ws: WebSocket, call_sid: str):
    """Exotel real-time audio stream — PCM 16-bit 8kHz mono.
    Uses AudioIngestHandler for feature extraction + STT pipeline feeding.
    """
    await ingest_audio_stream(call_sid, ws, stt_pipeline)


# ─── Operator HUD WebSocket ───────────────────────────────────────────────────

@app.websocket("/ws/operator/{call_sid}")
async def operator_ws(ws: WebSocket, call_sid: str):
    """Operator browser connects here to receive live HUD updates."""
    await ws_manager.connect_operator(call_sid, ws)

    # Send current state on connect
    state = await EventBus.get_session_state(call_sid)
    if state:
        await ws.send_json({"type": "state_sync", **state})

    try:
        while True:
            data = await ws.receive_json()
            event_type = data.get("type")

            if event_type == "operator.feedback":
                await EventBus.emit('operator.feedback', {
                    'call_sid': call_sid,
                    'suggestion_id': data.get("suggestion_id"),
                    'action': data.get("action"),
                    'operator_id': data.get("operator_id"),
                    'modification_text': data.get("modification_text")
                })
            elif event_type == "call.disclosed":
                await EventBus.emit('call.state_change', {
                    'call_sid': call_sid,
                    'old_state': 'active',
                    'new_state': 'disclosed',
                    'triggered_by': 'operator'
                })
            elif event_type == "call.opted_out":
                await EventBus.emit('call.state_change', {
                    'call_sid': call_sid,
                    'old_state': 'active',
                    'new_state': 'opted_out',
                    'triggered_by': 'operator'
                })

    except WebSocketDisconnect:
        await ws_manager.disconnect_operator(call_sid, ws)


# ─── Supervisor WebSocket ─────────────────────────────────────────────────────

@app.websocket("/ws/supervisor/{helpline_id}")
async def supervisor_ws(ws: WebSocket, helpline_id: str):
    """Supervisor browser connects here for live board updates."""
    await ws_manager.connect_supervisor(helpline_id, ws)

    # Send current board state
    if redis_client:
        try:
            board_data = await redis_client.get(f"board:{helpline_id}:metrics")
            if board_data:
                await ws.send_json({"type": "board_sync", **json.loads(board_data)})
        except Exception:
            pass

    try:
        while True:
            await ws.receive_text()  # keep-alive
    except WebSocketDisconnect:
        await ws_manager.disconnect_supervisor(helpline_id, ws)


# ─── Call Management API ──────────────────────────────────────────────────────

@app.get("/api/calls/{call_sid}")
async def get_call(call_sid: str, db: Session = Depends(get_db),
                   operator: Operator = Depends(get_current_operator)):
    call = db.query(Call).filter(Call.call_sid == call_sid).first()
    if not call:
        raise HTTPException(404, "Call not found")
    return {
        "call_sid": call.call_sid,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "priority_tier": call.priority_tier,
        "final_risk_level": call.final_risk_level,
        "peak_risk_level": call.peak_risk_level,
        "ai_disclosed": call.ai_disclosed,
        "opted_out": call.opted_out,
        "shadow_mode": call.shadow_mode,
        "outcome_label": call.outcome_label
    }


@app.patch("/api/calls/{call_sid}")
async def update_call(call_sid: str, data: dict = Body(...),
                      db: Session = Depends(get_db)):
    """Update call metadata — outcome, disclosure, debrief, etc."""
    allowed = {"outcome_label", "ai_disclosed", "opted_out", "shadow_mode",
               "debrief_notes", "ai_helpful_rating"}
    update = {k: v for k, v in data.items() if k in allowed}
    if "ai_disclosed" in update and update["ai_disclosed"]:
        update["disclosed_at"] = datetime.now(timezone.utc)
    if "opted_out" in update and update["opted_out"]:
        update["opted_out_at"] = datetime.now(timezone.utc)
        update["shadow_mode"] = True
    if "outcome_label" in update:
        update["outcome_set_at"] = datetime.now(timezone.utc)

    # Only update columns that exist in the model
    model_cols = {c.key for c in Call.__table__.columns}
    update = {k: v for k, v in update.items() if k in model_cols}

    if update:
        db.query(Call).filter(Call.call_sid == call_sid).update(update)
        db.commit()
    return {"status": "updated", "call_sid": call_sid}


# ─── Dispatch API ─────────────────────────────────────────────────────────────

class DispatchRequest(BaseModel):
    call_sid: str
    action_type: str
    resource_id: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_address: Optional[str] = None
    confirmed: bool = False


@app.post("/api/dispatch")
async def dispatch_action(
    req: DispatchRequest,
    db: Session = Depends(get_db),
    operator: Operator = Depends(get_current_operator)
):
    """Operator confirms a dispatch action from HUD."""
    if not req.confirmed:
        return {
            "status": "awaiting_confirmation",
            "message": "Dispatch requires operator confirmation",
            "action": req.action_type
        }

    dispatch_svc = DispatchService(db)
    result = await dispatch_svc.dispatch(
        call_sid=req.call_sid,
        operator_id=str(operator.id),
        action_type=req.action_type,
        resource_id=req.resource_id,
        location_lat=req.location_lat,
        location_lng=req.location_lng,
        location_address=req.location_address,
        confirmed=True
    )

    await EventBus.emit('dispatch.action', {
        'call_sid': req.call_sid,
        'action_type': req.action_type,
        'resource_id': req.resource_id,
        'operator_id': str(operator.id),
        'location': {'lat': req.location_lat, 'lng': req.location_lng, 'address': req.location_address},
        'confirmed': True
    })

    return result


# ─── DPDPA Erasure ────────────────────────────────────────────────────────────

@app.post("/api/calls/{call_sid}/erase")
async def erase_call(call_sid: str, db: Session = Depends(get_db),
                     supervisor: Operator = Depends(require_supervisor)):
    """Full PII erasure for a session — DPDPA right to erasure.
    All steps complete within 5 seconds per spec.
    """
    erased = []

    # 1. Nullify caller_phone_hash
    db.query(Call).filter(Call.call_sid == call_sid).update({
        "caller_phone_hash": None,
        "anonymised_at": datetime.now(timezone.utc),
        "erasure_requested": True
    })
    erased.append("caller_phone_hash")

    # 2. Delete Redis session keys
    await EventBus.delete_session(call_sid)
    erased.append("redis_session_data")

    db.commit()
    logger.info(f"DPDPA erasure completed for call {call_sid} by {supervisor.email}")

    return {
        "status": "erased",
        "call_sid": call_sid,
        "erased_at": datetime.now(timezone.utc).isoformat(),
        "deleted": erased,
        "retained_anonymised": ["duration", "language", "risk_level", "outcome", "ai_suggestions"]
    }


# ─── Resources API ────────────────────────────────────────────────────────────

@app.get("/api/resources")
async def get_resources(
    city: Optional[str] = None,
    state: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    risk_level: str = "MEDIUM",
    limit: int = 8,
    db: Session = Depends(get_db)
):
    """Get ranked resources for a location and risk level."""
    resource_svc = ResourceService(db)
    resources = resource_svc.get_ranked_resources(
        city=city, state=state, lat=lat, lng=lng,
        risk_level=risk_level, limit=limit
    )
    return {"resources": resources, "count": len(resources)}


# ─── Audit & Replay API ───────────────────────────────────────────────────────

@app.get("/api/calls/{call_sid}/replay")
async def get_call_replay(call_sid: str, db: Session = Depends(get_db),
                          supervisor: Operator = Depends(require_supervisor)):
    """Get full audit replay for a call."""
    audit_svc = AuditService(db)
    suggestions = audit_svc.get_call_suggestions(call_sid)
    dispatch_svc = DispatchService(db)
    dispatches = dispatch_svc.get_dispatch_history(call_sid)
    return {
        "call_sid": call_sid,
        "suggestions": suggestions,
        "dispatches": dispatches
    }


@app.get("/api/calls/{call_sid}/risk-timeline")
async def get_risk_timeline(call_sid: str, db: Session = Depends(get_db),
                            supervisor: Operator = Depends(require_supervisor)):
    """Get risk score timeline for supervisor replay view."""
    audit_svc = AuditService(db)
    return {"call_sid": call_sid, "timeline": audit_svc.get_risk_timeline(call_sid)}


# ─── Operator Feedback (guidance accepted/modified/rejected) ──────────────────

class FeedbackRequest(BaseModel):
    suggestion_id: str
    action: str  # accepted | modified | rejected
    modification_text: Optional[str] = None


@app.post("/api/feedback")
async def record_feedback(req: FeedbackRequest, db: Session = Depends(get_db),
                           operator: Operator = Depends(get_current_operator)):
    """Record operator response to an AI guidance suggestion."""
    if req.action not in ("accepted", "modified", "rejected"):
        raise HTTPException(400, "action must be accepted, modified, or rejected")

    audit_svc = AuditService(db)
    success = audit_svc.record_operator_action(
        req.suggestion_id, req.action, str(operator.id), req.modification_text
    )
    return {"status": "recorded" if success else "not_found", "action": req.action}


# ─── Supervisor — Live Board ───────────────────────────────────────────────────

@app.get("/api/supervisor/board")
async def get_board(db: Session = Depends(get_db),
                    supervisor: Operator = Depends(require_supervisor)):
    """Get live board state for supervisor dashboard."""
    helpline_id = str(supervisor.helpline_id) if supervisor.helpline_id else "00000000-0000-0000-0000-000000000001"

    # Active calls
    active_calls = db.query(Call).filter(
        Call.ended_at == None,
        Call.answered_at != None
    ).order_by(Call.started_at.desc()).limit(50).all()

    # Recent diversions
    diversions = db.query(DiversionLog).filter(
        DiversionLog.helpline_id == helpline_id
    ).order_by(DiversionLog.diverted_at.desc()).limit(20).all()

    # Queue state
    priority_svc = PriorityService(redis_client)
    queue_state = await priority_svc.get_queue_state(helpline_id)

    return {
        "active_calls": [
            {
                "call_sid": c.call_sid,
                "operator_id": str(c.operator_id) if c.operator_id else None,
                "started_at": c.started_at.isoformat(),
                "priority_tier": c.priority_tier,
                "final_risk_level": c.final_risk_level or "UNKNOWN",
                "ai_disclosed": c.ai_disclosed,
                "language_primary": c.language_primary
            }
            for c in active_calls
        ],
        "queue": queue_state,
        "diversions": [
            {
                "id": str(d.id),
                "diverted_at": d.diverted_at.isoformat(),
                "queue_depth": d.queue_depth,
                "priority_tier": d.priority_tier,
                "options_offered": d.options_offered,
                "caller_choice": d.caller_choice
            }
            for d in diversions
        ]
    }


# ─── Supervisor Analytics (PRD F9) ───────────────────────────────────────────

@app.get("/api/supervisor/analytics")
async def get_analytics(
    days: int = 7,
    db: Session = Depends(get_db),
    supervisor: Operator = Depends(require_supervisor)
):
    """Aggregate analytics for supervisor dashboard (PRD F9 — anonymised)."""
    from datetime import timedelta
    from sqlalchemy import func
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Total calls
    total_calls = db.query(func.count(Call.call_sid)).filter(
        Call.started_at >= since
    ).scalar() or 0

    # By priority
    by_priority = {}
    for tier in ["P0", "P1", "P2", "P3"]:
        by_priority[tier] = db.query(func.count(Call.call_sid)).filter(
            Call.started_at >= since,
            Call.priority_tier == tier
        ).scalar() or 0

    # By risk level (peak)
    by_risk = {}
    for level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        by_risk[level] = db.query(func.count(Call.call_sid)).filter(
            Call.started_at >= since,
            Call.peak_risk_level == level
        ).scalar() or 0

    # AI suggestion stats
    total_suggestions = db.query(func.count(AISuggestion.id)).filter(
        AISuggestion.timestamp >= since
    ).scalar() or 0
    accepted = db.query(func.count(AISuggestion.id)).filter(
        AISuggestion.timestamp >= since,
        AISuggestion.operator_action == "accepted"
    ).scalar() or 0
    modified = db.query(func.count(AISuggestion.id)).filter(
        AISuggestion.timestamp >= since,
        AISuggestion.operator_action == "modified"
    ).scalar() or 0
    rejected = db.query(func.count(AISuggestion.id)).filter(
        AISuggestion.timestamp >= since,
        AISuggestion.operator_action == "rejected"
    ).scalar() or 0

    # AI disclosure rate
    disclosed = db.query(func.count(Call.call_sid)).filter(
        Call.started_at >= since,
        Call.ai_disclosed == True
    ).scalar() or 0

    # Avg call duration (completed calls only)
    avg_duration = db.query(func.avg(Call.duration_seconds)).filter(
        Call.started_at >= since,
        Call.duration_seconds != None
    ).scalar()

    # Dispatch actions
    total_dispatches = db.query(func.count(DispatchLog.id)).filter(
        DispatchLog.dispatched_at >= since
    ).scalar() or 0

    return {
        "period_days": days,
        "total_calls": total_calls,
        "by_priority": by_priority,
        "by_risk_level": by_risk,
        "ai_disclosure_rate": round(disclosed / total_calls, 3) if total_calls else 0,
        "avg_call_duration_seconds": round(avg_duration, 1) if avg_duration else None,
        "ai_suggestions": {
            "total": total_suggestions,
            "accepted": accepted,
            "modified": modified,
            "rejected": rejected,
            "acceptance_rate": round(accepted / total_suggestions, 3) if total_suggestions else 0
        },
        "total_dispatches": total_dispatches
    }


# ─── Demo: Text injection (bypasses audio for demo) ──────────────────────────

class TextInjectRequest(BaseModel):
    call_sid: str
    text: str
    language: str = "en"
    confidence: float = 0.85
    ambient_override: Optional[str] = None  # for injecting ambient sounds


@app.post("/api/demo/inject")
async def demo_inject(req: TextInjectRequest, db: Session = Depends(get_db)):
    """Demo endpoint: inject text directly into the event bus, bypassing audio.
    Creates call record if it doesn't exist.
    """
    # Ensure call record exists
    call = db.query(Call).filter(Call.call_sid == req.call_sid).first()
    if not call:
        call = Call(
            call_sid=req.call_sid,
            started_at=datetime.now(timezone.utc),
            priority_tier="P1",
            helpline_id="00000000-0000-0000-0000-000000000001"
        )
        db.add(call)
        db.commit()

    # Inject text as STT segment
    await EventBus.emit('stt.segment', {
        'call_sid': req.call_sid,
        'text': req.text,
        'language_tags': [{'phrase': req.text, 'lang': req.language}],
        'confidence': req.confidence,
        'uncertain': req.confidence < 0.65,
        'word_timestamps': []
    })

    # Optional ambient override
    if req.ambient_override:
        await EventBus.emit('audio.features', {
            'call_sid': req.call_sid,
            'prosody_energy': 1500.0 if req.ambient_override == "child_crying" else 500.0,
            'pitch_hz': 0.0,
            'silence_ratio': 0.1,
            'chunk_ms': 2000,
            '_ambient_hint': req.ambient_override
        })

    return {"status": "injected", "call_sid": req.call_sid, "text": req.text}


@app.get("/api/demo/calls")
async def list_demo_calls(db: Session = Depends(get_db)):
    """List all active/queued calls for the operator queue view.
    Returns both demo and real calls, ordered by priority then time.
    """
    # Return all unanswered OR recently active calls (last 2 hours)
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(hours=2)
    calls = db.query(Call).filter(
        Call.started_at >= since,
        Call.ended_at == None
    ).order_by(Call.priority_tier, Call.started_at.asc()).limit(30).all()
    return {
        "calls": [
            {
                "call_sid": c.call_sid,
                "priority_tier": c.priority_tier or "P2",
                "queued_at": c.started_at.isoformat() if c.started_at else None,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "final_risk_level": c.final_risk_level or "UNKNOWN",
                "language_primary": c.language_primary or "en",
            }
            for c in calls
        ]
    }


# ─── TTS (Sarvam Bulbul) ─────────────────────────────────────────────────────

@app.post("/api/tts")
async def text_to_speech(text: str, language: str = "hi-IN"):
    """Generate TTS audio using Sarvam Bulbul API."""
    import httpx
    SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
    SARVAM_BASE_URL = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{SARVAM_BASE_URL}/text-to-speech",
                headers={"api-subscription-key": SARVAM_API_KEY},
                json={
                    "inputs": [text],
                    "target_language_code": language,
                    "speaker": "meera",
                    "model": "bulbul:v1"
                }
            )
            if response.status_code == 200:
                data = response.json()
                return {"audio_base64": data.get("audios", [""])[0], "language": language}
            else:
                return {"error": f"TTS failed: HTTP {response.status_code}", "fallback": True}
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return {"error": str(e), "fallback": True}


# ─── Agent Loop ───────────────────────────────────────────────────────────────

async def run_agent_loop():
    """Background task: consume events and run all agents inline."""
    narrative = NarrativeAgent()
    emotion = EmotionAgent()
    ambient = AmbientAgent()
    language = LanguageAgent()
    fatigue = OperatorFatigueAgent()

    agent_map = {
        "stt.segment": [narrative, language, emotion],
        "audio.features": [emotion, ambient],
        "call.state_change": [fatigue],
        "meta.risk_update": [fatigue],
    }

    async for event in EventBus.subscribe("api-agent-runner", "main"):
        event_type = event.get("type")
        call_sid = event.get("call_sid")

        if not call_sid:
            continue

        # Skip agent processing in shadow mode
        session = await EventBus.get_session_state(call_sid)
        if session.get("opted_out") and event_type != "call.state_change":
            continue  # Shadow mode: AI still runs but doesn't surface to operator

        for agent in agent_map.get(event_type, []):
            try:
                assessment = await agent.on_event(event)
                if assessment:
                    meta_agent.update_assessment(call_sid, {
                        "agent_id": assessment.agent_id,
                        "risk_score": assessment.risk_score,
                        "confidence": assessment.confidence,
                        "explanation": assessment.explanation,
                        "dimensions": assessment.dimensions,
                        "flags": assessment.flags
                    })
                    await meta_agent.fuse_and_emit(call_sid)
            except Exception as e:
                logger.error(f"Agent {agent.agent_id} error: {e}", exc_info=True)


async def push_risk_updates():
    """Background task: consume meta.risk_update, persist to DB, and push to WS connections."""
    from db.session import SessionLocal
    async for event in EventBus.subscribe("ws-pusher", "main",
                                          event_types=["meta.risk_update"]):
        call_sid = event.get("call_sid")
        if not call_sid:
            continue

        # ── Persist AI suggestion to DB (immutable audit trail) ──
        try:
            db = SessionLocal()
            audit_svc = AuditService(db)
            audit_svc.log_suggestion(
                call_sid=call_sid,
                suggestion_text=event.get("guidance_text") or "",
                risk_level=event.get("risk_level", "UNKNOWN"),
                risk_score=event.get("risk_score", 0),
                confidence=event.get("confidence", 0.0),
                reasoning_chain={
                    "explanation": event.get("explanation", ""),
                    "conflicts": event.get("conflicts", []),
                    "agents_summary": event.get("agents_summary", {}),
                    "model_version": "v1.0.0-fusion",
                },
                model_version="v1.0.0-fusion",
            )
            # Also update peak_risk_level on the call record
            new_risk = event.get("risk_level", "UNKNOWN")
            risk_order = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
            call_rec = db.query(Call).filter(Call.call_sid == call_sid).first()
            if call_rec:
                current_peak = call_rec.peak_risk_level or "UNKNOWN"
                if risk_order.get(new_risk, 0) > risk_order.get(current_peak, 0):
                    call_rec.peak_risk_level = new_risk
                    call_rec.peak_risk_at = datetime.now(timezone.utc)
                call_rec.final_risk_level = new_risk
                db.commit()
        except Exception as e:
            logger.error(f"Audit persistence error for {call_sid}: {e}")
        finally:
            try:
                db.close()
            except Exception:
                pass

        # ── Cache risk state in Redis ──
        await EventBus.set_session_state(call_sid, {
            "risk_level": event.get("risk_level"),
            "risk_score": event.get("risk_score"),
            "guidance_text": event.get("guidance_text"),
            "guidance_id": event.get("guidance_id"),
        })

        # ── Push to operator HUD and supervisor board ──
        await ws_manager.push_to_operator(call_sid, event)
        await ws_manager.push_to_supervisors(
            "00000000-0000-0000-0000-000000000001",
            {"type": "call.risk_update", "call_sid": call_sid, **event}
        )


async def push_stt_segments():
    """Background task: forward stt.segment events to operator HUD WebSocket.
    This allows the frontend to receive live transcript on the single WS connection.
    Separate consumer group 'stt-pusher' so it processes ALL stt events independently.
    """
    async for event in EventBus.subscribe("stt-pusher", "main",
                                          event_types=["stt.segment"]):
        call_sid = event.get("call_sid")
        if not call_sid:
            continue
        try:
            # Forward stt.segment directly to operator WS
            await ws_manager.push_to_operator(call_sid, event)
        except Exception as e:
            logger.error(f"STT segment push error for {call_sid}: {e}")
