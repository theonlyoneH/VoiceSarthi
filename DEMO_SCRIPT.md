# DEMO SCRIPT — VoiceForward Hackathon Presentation

## Presentation Structure (3 minutes)

```
0:00–0:30  Hook — the problem in one sentence
0:30–1:00  System overview — what it does and what it isn't
1:00–2:30  Live demo — 3 scenarios (30 sec each)
2:30–3:00  Technical highlights + closing
```

---

## Opening Hook (say this exactly)

> "Every night in India, a crisis caller reaches an exhausted volunteer who has no tools except their training and a phone. The AI that could help them — it already exists. The problem is no one has connected it in a way operators actually trust. That's VoiceForward."

---

## Scenario 1: High-Risk Hinglish Caller at 3am
**(Duration: ~30 seconds)**

### What to show
1. Open Operator HUD — dark screen, 3-pane layout
2. Run: `python demo/simulator.py --scenario high_risk_hinglish`

### What happens (auto)
- Transcript appears with language tags: `[HI] Main bahut thaka hoon… [EN] I can't do this anymore`
- Risk bar climbs from green → amber
- Second segment: `I've decided… kuch karna chahta hoon`
- NarrativeAgent fires HIGH — GlassBox Narrative card turns red
- Third segment: `I've decided` again
- Risk bar hits RED — CRITICAL
- Guidance pane: *"Ask directly and calmly: Are you thinking about ending your life? Stay on the line."*
- Dispatch panel: red `🚑 Dispatch Ambulance` button appears

### What to say
> "Notice two things. The system detected code-switching between Hindi and English mid-sentence — Sarvam AI handles this natively. And when the phrase 'I've decided' appeared twice, the NarrativeAgent triggered a CRITICAL flag. The guidance tells the operator what to say right now — not a score, a sentence."

### Click: Accept guidance → show it greys out with 'Accepted' badge
> "One keystroke. The operator never takes their voice off the call."

---

## Scenario 2: Domestic Violence + Child in Background
**(Duration: ~30 seconds)**

### What to show
1. New demo call — run: `python demo/simulator.py --scenario domestic_violence_child`
2. AmbientAgent mock: inject `child_crying` flag

### What happens
- Transcript: `"I need somewhere safe to stay tonight… my child is with me"`
- AmbientAgent card shows: MEDIUM → HIGH — "child crying detected"
- Resource panel updates: shelter options float to top
- Map overlay appears automatically (location: Mumbai detected from speech)
- Map shows 3 shelter pins within 5km, nearest is pulsing
- Dispatch button: `🏠 Connect to Shelter` appears

### What to say
> "The ambient audio agent heard a child crying in the background. That single signal moved shelter options to the top of the resource panel and opened the map. The operator didn't type anything — the system understood the risk context from what it heard, not just what was said."

### Click: Open Map → show shelter pins
> "One click connects the operator to the shelter's intake line via a three-way Exotel conference bridge. Caller, operator, shelter — all on the same call."

---

## Scenario 3: Conflicting Signals — Calibrated Uncertainty
**(Duration: ~30 seconds)**

### What to show
1. Run: `python demo/simulator.py --scenario conflicting_signals`

### What happens
- Transcript: `"Ha ha, I'm fine, really [nervous laugh]"`
- EmotionAgent: LOW (laughter detected, high energy)
- Second segment: `"I tried something last week but it's okay"`
- NarrativeAgent: HIGH (past attempt keyword)
- **Conflict banner appears** (amber): "⚠ Agents disagree — Emotion=LOW vs Narrative=HIGH — defaulted to higher risk"
- EmotionAgent card has amber dashed border
- MetaAgent explanation: "Nervous laughter can mask distress. Past attempt disclosure overrides tone."
- Guidance: *"Stay present. Don't dismiss the laughter. Gently ask: 'Can you tell me more about what happened last week?'"*

### What to say
> "This is the moment most AI systems fail. Emotion said low risk — the caller was laughing. Narrative said high risk — they mentioned a past attempt. Instead of hiding that disagreement, VoiceForward shows it. The GlassBox. And it defaults to the higher risk with a plain-English explanation of why. Calibrated uncertainty, not fake confidence."

---

## Technical Highlight (15 seconds)

> "Under the hood: five specialist agents running in parallel, consuming a shared event bus. A MetaAgent resolves conflicts using clinical-first rules — safety always defaults up. Every suggestion is logged immutably with its full reasoning chain for supervisor audit and DPDPA compliance."

---

## Show Priority Queue (if time permits, 10 seconds)

> "One more thing. Before a call even reaches an operator, our IVR pre-screens for distress. Calls are assigned P0 through P3. Low-priority calls, P3, can be diverted — offered a callback or WhatsApp support — so our trained operators are always focused on who needs them most."

Show: Supervisor dashboard with P0 call at top, P3 "Divert" option

---

## Closing (10 seconds)

> "VoiceForward doesn't replace the operator. It makes every operator perform at their best — regardless of the hour, the language, or how many calls they've already taken tonight. Thank you."

---

## Anticipated Judge Questions

**Q: What about false positives — won't too many high-risk alerts tire operators?**
> "Great question. We track operator rejection rates per guidance type. When operators consistently reject a signal category, the system learns to weight it lower. Over time, it calibrates to each helpline's specific context. And operators have one-key reject — there's no penalty for disagreeing."

**Q: How does DPDPA compliance work in practice?**
> "No raw audio ever touches disk. Transcripts are pseudonymised at call end. A single API call erases all PII for a session. The AI suggestions table is append-only — supervisors can replay what was suggested, but nobody can modify the audit trail. Compliance is in the data architecture, not in a policy PDF."

**Q: What happens when Sarvam STT goes down?**
> "We designed that failure mode explicitly. After three consecutive failures, the UI shows a plain-English banner — 'transcription paused, trust your training' — and we switch to a local Whisper tiny model as fallback. The operator is never left with a silently broken system."

**Q: Is this only for suicide helplines?**
> "No. The system is configurable per helpline type. Risk thresholds, keyword dictionaries, resource categories, and guidance templates are all configured per organisation. Domestic violence helplines, child protection lines, disaster relief lines — the core infrastructure works for any high-stakes phone support context."

**Q: What's the latency on HUD updates?**
> "Our target is under 300ms from end of utterance to HUD update. In the demo you can see it: the risk bar moves within a second of the caller finishing a sentence. That's the Sarvam streaming API plus a Redis event bus delivering to a WebSocket connection."

---

## Demo Failure Recovery

**If Sarvam STT doesn't work:**
- Use text simulation mode: `python demo/simulator.py --scenario X --text-only`
- This injects text directly, bypassing audio — same visual result

**If WebSocket drops:**
- Reload the operator HUD page; it reconnects automatically
- State is restored from Redis on reconnect

**If map doesn't load:**
- Check NEXT_PUBLIC_MAPBOX_TOKEN in .env
- Fallback: show screenshot of map panel from slides

**If any agent crashes:**
- MetaAgent gracefully handles missing agent inputs
- HUD still shows remaining agents; 'UNKNOWN' state with "trust your training" message
- This is actually a GOOD demo of failure mode design — show it proudly
