# ETHICS AND SAFETY — VoiceForward

## Core Ethical Commitments

1. **Human override is absolute** — the AI never acts on a call without operator confirmation
2. **Uncertainty is honest** — when the AI is unsure, it says so explicitly, never projects false confidence
3. **Safety defaults to caution** — a false positive (over-caution) is always preferable to a false negative (missing a crisis)
4. **Privacy is architectural** — DPDPA compliance is built into data flows, not added as a policy
5. **Failure must be designed** — every failure mode has a specific, graceful response

---

## DPDPA 2023 Compliance

### Data Localisation
- All PostgreSQL instances run in India-region cloud (AWS ap-south-1 / Azure Central India) or on-prem
- Sarvam AI: India-based; confirm their data residency SLA before production deployment
- No audio, transcript, or metadata transmitted to servers outside India
- Mapbox: use self-hosted tile server OR Mapbox India-compliant tier (review ToS)

### Consent Architecture

```
Call connected
    │
    ▼ (within 30 seconds)
Operator reads AI disclosure to caller
    │
    ├── Caller accepts (implicit or explicit) → ai_disclosed=TRUE logged
    │                                         → AI proceeds normally
    │
    └── Caller says no / opts out → ai_disclosed=TRUE, opted_out=TRUE
                                  → AI switches to SHADOW MODE:
                                    - Still processes audio internally
                                    - Does NOT surface guidance to operator
                                    - Does NOT surface risk level to operator
                                    - Logs for research/improvement only
                                    - Session data subject to FULL erasure on request
```

**Shadow mode is not a degraded experience for the caller.** The operator simply works without AI assistance, exactly as they would on a legacy helpline. The caller receives the same quality of human support.

### Right to Erasure

```
POST /api/calls/{call_sid}/erase
  Auth: supervisor or admin only

Erasure steps (all within 5 seconds):
1. Delete: raw audio files from storage
2. Delete: full transcript text from calls table
3. Pseudonymise: caller_phone_hash → replace with NULL
4. Delete: all STT segments from event bus cache
5. Retain (anonymised): call metadata (duration, language, risk level, outcome)
   — retained for helpline performance analytics
   — cannot be linked back to caller
6. Log: erasure_requested=TRUE, anonymised_at=NOW() in calls table
7. Return: confirmation with list of deleted data types
```

### Minimum Data Retention

| Data Type | Retention | Reason |
|---|---|---|
| Raw audio | Session duration only | Never persisted to disk after session |
| STT transcript (full) | 30 days (operator review) OR erasure request | Call quality review |
| Caller phone hash | 90 days | Repeat caller detection for safety |
| Risk metadata (no PII) | 2 years | Longitudinal learning |
| AI suggestions + reasoning | 2 years | Audit and model improvement |
| Anonymised phrase-outcomes | 5 years | Research and training |

---

## Hallucination Prevention — 7 Layers

### Layer 1: STT Confidence Gating
```python
UNCERTAIN_THRESHOLD = 0.65

if segment.confidence < UNCERTAIN_THRESHOLD:
    segment.uncertain = True
    # Downstream agents weight this segment at 0.4x (not zero)
    # HUD shows small "⚠ audio unclear" indicator
    # Never triggers HIGH risk based on uncertain segment alone
```

### Layer 2: Agent Confidence Exclusion
```python
MINIMUM_AGENT_CONFIDENCE = 0.5

# In MetaAgent:
for agent_id, assessment in agent_outputs.items():
    if assessment.confidence < MINIMUM_AGENT_CONFIDENCE:
        excluded_agents.append(agent_id)
        explanation_parts.append(f"{agent_id} excluded — confidence {assessment.confidence:.2f}")
        continue
    valid_agents.append(assessment)
```

### Layer 3: Cross-Agent Disagreement Detection
```python
CONFLICT_THRESHOLD = 3  # risk score difference that triggers conflict

scores = [a.risk_score for a in valid_agents]
if max(scores) - min(scores) >= CONFLICT_THRESHOLD:
    conflict = True
    # Show conflict banner in HUD
    # Default to MAX score (safety-first)
    # Reduce overall confidence to 0.5
    # Explicit explanation: which agents disagree and on what
```

### Layer 4: Temporal Coherence Check
```python
MAX_SINGLE_UPDATE_JUMP = 3  # risk score cannot jump more than 3 in one update

if new_score > previous_score + MAX_SINGLE_UPDATE_JUMP:
    # Require 2+ agents to agree before accepting the jump
    if sum(a.risk_score > previous_score + 2 for a in valid_agents) < 2:
        new_score = previous_score + MAX_SINGLE_UPDATE_JUMP
        explanation_parts.append("Rapid risk increase: awaiting confirmation from multiple agents")
```

### Layer 5: High-Stakes Keyword Double-Check
```python
# These 12 phrases always trigger a secondary rule-based check
# independent of the LLM pipeline
HIGH_STAKES_PHRASES = {
    "en": ["I've decided", "said my goodbyes", "no one will miss me",
           "no point anymore", "going to end it", "tried last week",
           "last time", "won't be here", "nothing left"],
    "hi": ["faisla kar liya", "alvida bol diya", "kuch nahi bachha",
           "khatam karna chahta", "kal kiya tha"],
    # ... all 10 languages
}

# If EITHER the LLM OR the keyword checker fires: risk >= HIGH
# Only if NEITHER fires: risk can stay at LOW/MEDIUM
```

### Layer 6: Operator Rejection Learning
```python
# Every rejection logged
# After 5 rejections of similar guidance pattern:
#   - Flag for model review
#   - Temporarily suppress that guidance category
#   - Alert supervisor for manual review

async def handle_operator_rejection(call_sid, guidance_id, operator_id):
    rejection = await log_rejection(call_sid, guidance_id, operator_id)
    pattern_count = await count_similar_rejections(guidance_id, window_days=7)
    if pattern_count >= 5:
        await suppress_guidance_pattern(guidance_id)
        await alert_supervisor_pattern(guidance_id, pattern_count)
```

### Layer 7: Calibrated Uncertainty in UI
- Agent confidence < 0.6: dashed border on agent card, opacity 70%
- Agent confidence < 0.5: agent card grayed out with "Uncertain" label
- MetaAgent confidence < 0.6: guidance text shows in amber instead of white
- MetaAgent confidence < 0.5: guidance text prefixed with "⚠ Low confidence —"
- Overall UNKNOWN state: all cards show "Waiting for signals"

---

## Failure Mode Playbook

### FAILURE: STT Service Unavailable

**Detection:**
```python
STT_FAILURE_CONDITIONS = [
    "3 consecutive empty transcripts",
    "confidence < 0.3 for 5 consecutive seconds",
    "Sarvam API HTTP 5xx or timeout",
    "WebSocket to Exotel disconnected"
]
```

**Response:**
1. Freeze all agent assessments at last known valid state
2. Mark all frozen assessments with `STALE` flag
3. Show HUD banner (amber):
   > "Transcription paused — Audio quality may be low or connection issue. I may be missing context. Trust your training. I'll resume when audio improves."
4. Emit `STT_FAILURE` WebSocket event; all agent cards show "Paused" state
5. Start Sarvam API health check every 10 seconds
6. On recovery: replay last buffered 10 seconds of audio through STT
7. Log `stt_failure_event` to audit log with duration

**Fallback:** Switch to local Whisper tiny model (lower accuracy, always available on-prem)

---

### FAILURE: Emotion Model Misclassification

**Detection:**
- Operator clicks REJECT on suggestion (immediate signal)
- EmotionAgent and NarrativeAgent differ by > 4 risk points (structural signal)
- EmotionAgent confidence drops below 0.4 (self-reported signal)

**Response:**
1. Immediately exclude EmotionAgent from fusion
2. MetaAgent uses NarrativeAgent + LanguageAgent only
3. HUD shows:
   > "Emotion signal uncertain — relying on conversation content rather than tone."
4. EmotionAgent card shows amber dotted border + "Recalibrating"
5. Log rejection + context as negative training sample
6. After 3 rejections in one call: fully disable EmotionAgent for this call_sid

---

### FAILURE: Resource Dispatch Error

**Detection:** HTTP timeout or 4xx/5xx from dispatch endpoint; Exotel conference bridge failure

**Response:**
1. Show operator immediately:
   > "Automatic dispatch failed. Please call directly:"
   > "🚑 Ambulance: 108  🚓 Police: 100  🏠 [Shelter name]: [number]"
2. Numbers displayed in large font in RIGHT pane
3. Log `dispatch_error` with error details
4. Supervisor alerted via WebSocket push
5. Retry dispatch once after 5 seconds; if second failure, mark as manual_required
6. Dispatch log entry: `status=failed, failure_reason=...`

---

### FAILURE: Network Degradation / WebSocket Disconnect

**Detection:** WebSocket reconnection attempts > 3; ping latency > 2000ms

**Response:**
1. HUD shows offline banner: "Connection interrupted — [timestamp of last update]"
2. Last known risk state displayed with "⚠ Last updated X seconds ago"
3. Resource list stays visible from local cache (static fallback)
4. Keyboard shortcuts remain functional for logging acceptance/rejection (queued for sync)
5. On reconnect: request full state sync; apply delta to HUD

---

### FAILURE: All Agents Return UNKNOWN

**Scenario:** STT is working but all agents produce confidence < 0.5

**Response:**
1. HUD guidance pane shows: "Signals unclear — your clinical judgment is primary right now"
2. Resource panel still shown (static, unranked)
3. Risk bar shows grey "UNKNOWN" state with pulsing animation
4. Supervisor notified if UNKNOWN persists > 2 minutes

---

## Immutable Audit Architecture

### What Is Logged (Cannot Be Modified)

Every `ai_suggestions` row captures:
- Full `reasoning_chain` JSON (all agent outputs, confidence, conflicts)
- Exact `suggestion_text` shown to operator
- `operator_action` and `operator_modification`
- `model_version` for every agent at time of suggestion
- `stt_confidence` at time of suggestion

### Tamper Prevention

```sql
-- Row-level security: insert only
ALTER TABLE ai_suggestions ENABLE ROW LEVEL SECURITY;
-- No UPDATE policy defined → UPDATE denied
-- No DELETE policy defined → DELETE denied

-- Application-level: audit_service uses a dedicated DB user
-- with INSERT-only privileges on ai_suggestions
CREATE ROLE audit_writer;
GRANT INSERT ON ai_suggestions TO audit_writer;
GRANT SELECT ON ai_suggestions TO audit_reader;
-- audit_writer has NO UPDATE or DELETE
```

### Supervisor Replay Access

```
GET /api/calls/{call_sid}/replay
  Returns: full sorted list of ai_suggestions for this call
  Auth: supervisor or admin

GET /api/calls/{call_sid}/transcript
  Returns: anonymised transcript with language tags
  Auth: supervisor or admin

GET /api/calls/{call_sid}/risk-timeline
  Returns: risk score + event markers over call duration
  Auth: supervisor or admin
```

---

## AI Governance (MeitY Alignment)

| Requirement | Implementation |
|---|---|
| Model versioning | `model_versions` table; every suggestion logs model version |
| Evaluation before deployment | Evaluated on test call set; accuracy + false-negative rate documented |
| Rollback capability | Previous model version retained; can be reactivated via admin panel |
| Human override | Operator accept/modify/reject logged; high rejection rate triggers review |
| Incident response | If call ends in adverse outcome: supervisor can replay and submit incident report |
| Explainability | Every suggestion has full reasoning chain; no black-box outputs ever shown |
| Regular audits | Analytics service generates monthly model performance report |

---

## Privacy by Architecture — Data Flows

```
Audio captured (Exotel WebSocket)
    │
    ▼ [NEVER written to disk]
Audio buffer (in-memory, max 30s rolling)
    │
    ▼
Sarvam STT → transcript text (written to Redis, TTL = call duration)
    │
    ▼
Agents process transcript → assessments (written to Redis, TTL = call duration + 1hr)
    │
    ▼
MetaAgent → ai_suggestion (written to PostgreSQL — IMMUTABLE AUDIT)
    │
    ▼
Call ends → Anonymisation pipeline:
    ├── Raw audio: already not persisted (in-memory only)
    ├── Full transcript: anonymised (caller_id replaced with hash, stored 30 days)
    ├── Phone number: hashed (SHA-256), stored 90 days for repeat detection
    ├── Phrase-outcomes: extracted with NO caller link, stored in phrase_outcomes table
    └── ai_suggestions: retained as-is (no PII in reasoning chains)
```
