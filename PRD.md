# PRD — VoiceForward GlassBox Copilot

## 1. Problem Statement

Every crisis helpline in India operates identically: a human picks up the phone and decides what to do — alone, under pressure, with no real-time support beyond their training and a printed referral sheet.

Call outcomes are shaped more by **operator fatigue**, **language mismatch**, and **time of day** than by actual caller severity. A caller in crisis at 3am reaching an exhausted volunteer in an unfamiliar language is statistically less likely to be helped than the same caller at 2pm.

This is not a resource problem. It is an **intelligence distribution problem**.

---

## 2. Goal

Build a real-time AI copilot that makes every operator perform at the level of their best possible shift — regardless of the hour, their fatigue state, or the caller's language.

**Not a chatbot. Not an IVR. Not autonomous.**

---

## 3. Users

### Primary: Frontline Operator
- Volunteer or paid counsellor at a crisis helpline
- On a live call with a distressed caller
- Cannot look away from the call for more than 1–2 seconds
- May be fatigued, especially on night shifts
- May not speak the caller's dominant language fluently
- Needs: instant risk awareness, specific guidance, one-click resources

### Secondary: Supervisor / Clinical Lead
- Monitors all active calls in real time
- Manages operator well-being and escalations
- Reviews call quality for training
- Needs: live board, audit replay, analytics dashboard

### Tertiary: Helpline Administrator / NGO Manager
- Configures system per helpline (risk thresholds, resource lists, language profiles)
- Reviews compliance reports
- Needs: admin panel, DPDPA compliance tools, usage analytics

---

## 4. Core Features

### F1 — Priority-Based Call Queue
Every incoming call is scored for **triage priority** before an operator picks up. This ensures the highest-risk callers are never waiting behind low-priority calls.

**Priority Tiers:**

| Tier | Label | Criteria | Queue Behaviour |
|---|---|---|---|
| P0 | CRITICAL | Prior suicide attempt mentioned in IVR, repeat caller flagged high-risk, caller screaming/distress sounds on line | Immediate alert to all available operators; escalate to supervisor if no operator free in 60s |
| P1 | HIGH | Distress keywords in IVR pre-screening, callback from previous high-risk call | Route to most experienced available operator; alert supervisor |
| P2 | MEDIUM | Standard crisis call, general distress | Normal queue; any available operator |
| P3 | LOW | General inquiry, follow-up, non-crisis | Can be **diverted**: offer callback slot, WhatsApp text support, or self-help IVR menu |

**Diversion Logic for P3 (Low Priority):**
- If queue depth > 3 AND all operators are on P1/P2 calls:
  - IVR plays: "All our counsellors are currently supporting urgent calls. We can: (1) Call you back within 30 minutes, (2) Send you a support message on WhatsApp, (3) Connect you to our self-help line."
  - Diversion is logged; if caller opts for callback, entry created in callback queue with timestamp
  - P3 calls are NEVER silently dropped — always offered an alternative

**How Priority Is Determined Pre-Answer:**
- IVR pre-screening: 10-second voice prompt ("Are you safe right now? Press 1 for yes, 2 for no, or say your language")
- Exotel caller ID check: is this number in the repeat-high-risk DB?
- Basic audio energy analysis on hold audio: silence vs crying vs screaming
- Operator-set flag from previous call ("mark as priority callback")

---

### F2 — Real-Time Multilingual Transcription (Sarvam AI)
- Streaming STT via Sarvam Saaras model
- Phrase-level language tagging: [HI] [EN] [MR] [TE] [BN] [GU] [KN] [PA] [UR] [TA]
- Code-switch detection mid-sentence without context loss
- Confidence score per segment; uncertain segments flagged
- Fallback to local Whisper tiny model if Sarvam unavailable

---

### F3 — Multi-Agent Analysis
Five parallel specialist agents consuming every STT segment:

| Agent | Input | Output |
|---|---|---|
| EmotionAgent | Audio prosody + text | Distress/calm/agitation/dissociation/suicidal-proxy scores (0–1 each) |
| AmbientAgent | Raw audio | Background classification (child crying, shouting, silence, traffic, etc.) |
| NarrativeAgent | Full transcript | Narrative shift alerts, disclosure detection, storyline coherence |
| LanguageAgent | STT segments | Code-switch map, dialect tags, idiom/codeword flags |
| OperatorFatigueAgent | Operator audio + shift metadata | Operator stress score, micro-break recommendation |

---

### F4 — MetaAgent Orchestration
- Consumes all agent outputs
- Resolves conflicts using safety-first rules
- Generates plain-language explanation (never a black box score)
- Emits unified risk level (LOW / MEDIUM / HIGH / CRITICAL / UNKNOWN) + confidence
- Produces 1–2 sentence operator guidance suggestion

---

### F5 — Operator HUD (Three-Pane Interface)
See `UI_SPEC.md` for full details.

- **Left pane**: Immediate guidance text + Accept/Modify/Reject (keyboard: A/M/R)
- **Centre pane**: Risk timeline bar + GlassBox agent panel + narrative summary
- **Right pane**: Ranked resources + dispatch buttons + map toggle

---

### F6 — Region-Aware Map + Dispatch
- Location detected from caller speech (NER) or Exotel caller ID approximation
- Mapbox map showing nearest: hospitals, police, shelters, NGOs, mental health centres
- Direct dispatch: ambulance (108), police (100), shelter intake — all via Exotel conference bridge
- Dispatch requires one operator confirmation; all dispatches logged immutably

---

### F7 — Live Calls Board (Supervisor)
- All active calls visible as live cards
- Auto-sorted by risk level (CRITICAL top)
- Supervisor can shadow any call (read-only HUD view)
- Queue panel showing P0–P3 calls waiting, estimated wait times
- Diversion log: all P3 diversions with outcome (callback accepted, self-help chosen, dropped)

---

### F8 — Sarvam TTS for Operator Guidance
- Operator can press a key to hear guidance read aloud in their language (hands-free mode)
- Resource names and addresses read in caller's detected language to operator
- Disclosure script read aloud to operator in their language for consistent delivery

---

### F9 — Longitudinal Learning
- Phrase-outcome mapping: which operator phrases correlate with de-escalation
- Resource effectiveness tracking: follow-through rates per resource
- Escalation prediction: call features at minute 5 predicting risk at minute 20
- All learning from anonymised aggregates; no PII

---

### F10 — Audit & Replay
- Every AI suggestion logged immutably with full reasoning chain
- Supervisor replay: timeline of AI suggestions + operator responses on any past call
- DPDPA-compliant erasure: one-click wipe of all PII for a session

---

## 5. Non-Functional Requirements

| Requirement | Target |
|---|---|
| HUD update latency | < 300ms from utterance end to UI update |
| STT latency | < 500ms streaming (Sarvam Saaras) |
| System uptime | 99.5% during helpline operating hours |
| Data residency | All data stored in India (AWS ap-south-1 or equivalent) |
| Concurrent calls supported | 50 simultaneous calls per deployment |
| Audio quality tolerance | Must function on 8kHz mono (standard PSTN quality) |
| Offline resilience | Core call functions work if AI backend unreachable; HUD shows degraded mode |

---

## 6. Out of Scope (v1)

- AI speaking directly to callers
- Autonomous escalation without operator confirmation
- Predictive outreach (calling potential at-risk individuals)
- Integration with national health records
- Mobile app for operators (web-only for v1)

---

## 7. Acceptance Criteria

### AC1 — Priority Queue
- [ ] P0 calls reach available operator within 30 seconds or trigger supervisor alert
- [ ] P3 calls are offered diversion options when queue depth > 3
- [ ] No call is silently dropped; all diversions logged with outcome

### AC2 — STT
- [ ] Sarvam STT produces transcripts with language tags on test Hinglish audio
- [ ] Confidence scores present on every segment
- [ ] STT failure triggers graceful degradation within 5 seconds

### AC3 — HUD
- [ ] Risk bar updates within 300ms of new agent assessment
- [ ] GlassBox shows all agent outputs with confidence
- [ ] Conflict banner appears when agents disagree by > 2 risk points
- [ ] Accept/Modify/Reject works via keyboard shortcut without mouse

### AC4 — Map + Dispatch
- [ ] Map appears within 3 seconds of location being mentioned
- [ ] Nearest 5 resources plotted correctly for Mumbai and Delhi test addresses
- [ ] Dispatch action triggers confirmation modal before proceeding
- [ ] All dispatch actions logged in audit table

### AC5 — Compliance
- [ ] AI disclosure timer visible from call start
- [ ] Opt-out switches to shadow mode; HUD guidance hidden
- [ ] Erase endpoint deletes all PII for a session within 5 seconds
