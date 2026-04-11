# UI SPEC — VoiceForward GlassBox Copilot

## Design Principles

1. **Ambient first** — information visible without reading, never interrupting
2. **One glance, one action** — any response takes ≤ 1 keystroke or tap
3. **Operator eyes belong to the call** — never require more than 2 seconds of screen attention
4. **Colour as signal, not decoration** — green/amber/red have exactly one meaning
5. **Uncertainty is visible** — never show confidence we don't have

---

## Colour System

```
--risk-low:       #10B981   (emerald-500)
--risk-medium:    #F59E0B   (amber-500)
--risk-high:      #EF4444   (red-500)
--risk-critical:  #7C3AED   (violet-600)
--risk-unknown:   #94A3B8   (slate-400)

--bg-primary:     #0F172A   (slate-900)  — main HUD background
--bg-secondary:   #1E293B   (slate-800)  — pane backgrounds
--bg-card:        #334155   (slate-700)  — card surfaces
--bg-overlay:     rgba(15, 23, 42, 0.95)  — map overlay

--text-primary:   #F8FAFC   (slate-50)
--text-secondary: #94A3B8   (slate-400)
--text-muted:     #64748B   (slate-500)

--accent:         #0D9488   (teal-600)   — Sarvam language indicators
--accent-light:   #CCFBF1   (teal-100)

--priority-p0:    #DC2626   (red-600)
--priority-p1:    #EA580C   (orange-600)
--priority-p2:    #2563EB   (blue-600)
--priority-p3:    #6B7280   (gray-500)

--conflict:       #F59E0B   (amber-500)  — conflict banner background
--uncertain:      #475569   (slate-600)  — dotted border for uncertain agents
```

---

## Screen 1: Operator HUD

**Route:** `/operator/[callSid]`
**Layout:** Full-screen, dark theme, three columns

```
┌─────────────────────────────────────────────────────────────────────┐
│ [VOICEFORWARD] [●LIVE 04:32] [HI/EN] [P1 HIGH]    [A/M/R] [⚡ SOS] │ ← TopBar
├────────────────┬─────────────────────────────┬──────────────────────┤
│                │  RISK TIMELINE BAR           │                      │
│  GUIDANCE      │  ████████████░░  HIGH 7.2   │  RESOURCES           │
│                ├─────────────────────────────┤                      │
│  "Acknowledge  │  GLASSBOX                   │  🏥 Nair Hospital     │
│  what they     │  ┌──────┐┌──────┐┌──────┐┌──┐  1.2km  [Connect]   │
│  said before   │  │EMOT  ││AMBI  ││NARR  ││LA│                      │
│  asking about  │  │HIGH  ││MED   ││HIGH  ││LO│  🏠 Snehi Shelter     │
│  safety plan." │  │ 0.82 ││ 0.71 ││ 0.89 ││0.│  2.4km  [Connect]   │
│                │  └──────┘└──────┘└──────┘└──┘                      │
│  [A] Accept    │                             │  🚓 Dharavi PS        │
│  [M] Modify    │  ⚠ CONFLICT: Emotion vs    │  0.8km  [Transfer]   │
│  [R] Reject    │  Narrative disagree         │                      │
│                │  → Defaulted to HIGH        │  ─────────────────── │
│  Last: Accepted│                             │  🚑 DISPATCH          │
│  2 min ago     │  NARRATIVE SUMMARY          │  [Ambulance 108]     │
│                │  "Caller mentions 'decided' │  [Police 100]        │
│                │  twice. Tone unusually calm.│                      │
│                │  History: past attempt hint"│  [📍 Open Map]       │
└────────────────┴─────────────────────────────┴──────────────────────┘
│ AI DISCLOSED ✓  |  Caller: Hinglish  |  Operator: Priya  |  Exotel  │ ← StatusBar
└─────────────────────────────────────────────────────────────────────┘
```

### Component: TopBar
- Left: Logo (small), live indicator (pulsing red dot + duration MM:SS)
- Centre: Detected language badge (e.g. "HI / EN"), Priority badge (P1 in orange)
- Right: Risk level badge (HIGH in red), keyboard hint [A/M/R], silent SOS button

### Component: RiskTimelineBar
- Full-width horizontal bar below TopBar (in centre pane)
- Background: `--bg-card`, filled portion colour interpolates green → amber → red based on score
- Score label on right: "HIGH 7.2" in matching risk colour
- On hover: tooltip showing last 5 risk changes with timestamps and triggers
- Animated: smooth transition over 200ms, never jarring

### Component: GlassBoxPanel
- 4 agent cards in a row (Emotion, Ambient, Narrative, Language)
- Each card:
  ```
  ┌──────────────┐
  │ EMOTION      │  ← agent name (small caps)
  │   HIGH       │  ← risk level (large, coloured)
  │ ████░ 0.82   │  ← confidence bar + score
  │ "calm + ↓pace"│  ← 1-line explanation
  └──────────────┘
  ```
- Uncertain agent (confidence < 0.6): card has dashed border, slightly dimmed
- Agent in conflict: card has amber left border
- OperatorFatigue agent shown as 5th small card below the 4 main ones
- When all agents agree: subtle green glow around panel
- When conflict: amber banner between cards showing conflict description

### Component: ConflictBanner
- Appears in centre pane between GlassBox and NarrativeSummary
- Background: amber-500 at 20% opacity, amber border
- Text: "⚠ Agents disagree — [conflict description] — defaulted to higher risk"
- Disappears when conflict resolves

### Component: GuidancePane (Left Pane)
- Large readable text: 1–2 sentences, 18px minimum, line spacing 1.6
- Below text: three action buttons
  - `[A] Accept` — teal background, keyboard shortcut A
  - `[M] Modify` — slate background, keyboard shortcut M
  - `[R] Reject` — transparent with border, keyboard shortcut R
- On Accept: guidance text fades to 60% opacity; "Accepted" badge appears
- On Reject: brief "Learning from this" message (1.5s), then fades
- On Modify: textarea appears pre-filled with original suggestion; operator edits; Submit with Enter
- Below buttons: last action summary in muted text ("Last: Accepted 2 min ago")
- If fatigue detected: amber banner above guidance: "You may be fatigued. Consider a brief pause after this call."

### Component: ResourcePanel (Right Pane)
- List of 3–5 ranked resources
- Each item:
  ```
  [icon] Resource Name      [ACTION]
         City · Distance · Hours
  ```
- Icons: 🏥 hospital, 🏠 shelter, 🚓 police, 🧠 mental health, 📞 helpline
- Distance shown if location detected, otherwise hidden
- ACTION button: "Connect" (3-way Exotel bridge) or "Transfer" (direct dial transfer)
- Dispatch section at bottom (only when risk >= HIGH):
  - Red `[🚑 Dispatch Ambulance 108]` button
  - Orange `[🚓 Alert Police 100]` button
  - Both require confirmation modal before action
- `[📍 Open Map]` button toggles MapOverlay

### Component: MapOverlay
- Slides in from right, 60% width, sits on top of ResourcePanel
- Mapbox GL JS dark theme map
- Pins:
  - Blue pulsing pin: caller location (if known)
  - Colour-coded pins per resource category
  - Clicking pin: popup with resource name, phone, hours, [Dispatch] button
- Top-left: editable location text field ("Type address or landmark")
- Distance rings: 1km, 5km shown as faint circles
- Close button top-right

### Component: AIDisclosureTimer
- Appears on new call connection
- Countdown bar: 0–30 seconds
- Pre-written disclosure script shown in operator's language
- TTS play button: "🔊 Read aloud" (plays Sarvam TTS)
- After 30s: "Disclosed ✓" in status bar
- Opt-out button: if caller says no, shows "Opt-out confirmed — shadow mode active"

### Keyboard Shortcuts (Global on HUD)
```
A         — Accept current guidance
M         — Modify current guidance
R         — Reject current guidance
Space     — Dismiss current notification
Ctrl+D    — Mark call as disclosed
Ctrl+M    — Toggle map overlay
Ctrl+S    — Silent SOS to supervisor
Ctrl+E    — Initiate call escalation
1/2/3     — Quick-dispatch resource 1/2/3 (with confirmation)
```

---

## Screen 2: Supervisor Dashboard

**Route:** `/supervisor`
**Layout:** Full-screen, two sections: Live Board (top) + Queue + Analytics (bottom)

```
┌─────────────────────────────────────────────────────────────────────┐
│ VoiceForward Supervisor  |  [12] Active  [4] Queued  [3] Diverted   │
├─────────────────────────────────────────────────────────────────────┤
│ LIVE CALLS                                              [Sort: Risk]│
│                                                                     │
│ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐           │
│ │ ● CRITICAL     │ │ ● HIGH         │ │ ● MEDIUM        │           │
│ │ Priya — 08:32  │ │ Rahul — 04:11  │ │ Aisha — 02:44  │           │
│ │ HI/EN  P0      │ │ HI     P1      │ │ EN     P2      │           │
│ │ "decided twice"│ │ "shelter query"│ │ General        │           │
│ │ [Shadow]       │ │ [Shadow]       │ │ [Shadow]       │           │
│ └────────────────┘ └────────────────┘ └────────────────┘           │
├─────────────────┬───────────────────────────────────────────────────┤
│ QUEUE           │ DIVERSION LOG                                     │
│ ┌─────────────┐ │ 14:32 — P3 call → offered callback, chose CB     │
│ │P0  (0) ──── │ │ 14:28 — P3 call → offered options, hung up       │
│ │P1  (1) ████ │ │ 14:15 — P3 call → chose WhatsApp support         │
│ │P2  (2) ████ │ │                                                   │
│ │P3  (1) ██── │ │                                                   │
│ └─────────────┘ │                                                   │
│ Est wait: 4 min │                                                   │
└─────────────────┴───────────────────────────────────────────────────┘
```

### Component: LiveCallCard
- Border colour = risk level
- Shows: operator name, call duration (live updating), language badge, priority badge
- Snippet: last AI narrative summary (3 words)
- [Shadow] button: opens read-only HUD view for this call in a side panel
- Cards auto-sort by risk (CRITICAL first), then by duration
- New cards fade in from right; ended calls fade out

### Component: QueuePanel
- Visual bar per priority tier showing call count
- P0: always shown in red even if empty (signals readiness)
- P3 bar has a "Divert all" toggle (converts queue to diversion mode during surge)
- Estimated wait time calculated from average call duration

### Component: DiversionLog
- Rolling list of last 20 diversions
- Timestamp, priority tier, what was offered, what caller chose
- Colour: green (chose option), grey (hung up), amber (no response)
- Filter by outcome

---

## Screen 3: Audit Replay

**Route:** `/supervisor/replay/[callSid]`

```
┌─────────────────────────────────────────────────────────────────────┐
│ REPLAY: Call #C-2847  |  14 Oct 2024 03:12  |  Priya  |  22:45 min  │
├─────────────────────────────────────────────────────────────────────┤
│ RISK TIMELINE                                                       │
│ [LOW────────MEDIUM──────────HIGH──────CRITICAL──────HIGH───MEDIUM]  │
│              │                 │                                     │
│              ↓                 ↓                                     │
│          "decided"          dispatch                                 │
│          flagged            sent                                     │
├─────────────────────────────────────────────────────────────────────┤
│ TRANSCRIPT                     │ AI SUGGESTIONS AT THIS POINT       │
│                                │                                     │
│ [03:14] [HI] Caller: "Main     │ Risk: HIGH (7.2)                   │
│ bahut thaka hoon…"             │ Agents: E:6 A:4 N:8 L:3           │
│                                │ Conflict: E vs N — resolved HIGH   │
│ [03:15] [EN] Caller: "I've     │ Suggestion: "Acknowledge feelings" │
│ decided I can't do this"       │ Operator: ACCEPTED                 │
│                                │                                     │
│ [03:16] [HI] Operator: "Main   │ ─────────────────────────────────  │
│ sun raha hoon…"                │ Risk: CRITICAL (8.5)               │
└────────────────────────────────┴────────────────────────────────────┘
```

- Playback controls: play, pause, skip to risk event
- Click any transcript line: right panel shows AI suggestion at that moment
- Click any timeline event marker: scroll transcript to that point
- Export button: generates PDF audit report (for clinical review)

---

## Screen 4: Priority Queue Board (Operator Waiting Screen)

**Route:** `/operator/queue`

Shown to operator when they are available but not on a call.

```
┌─────────────────────────────────────────────────────────────────────┐
│ VoiceForward  |  Priya (Senior)  |  Available  |  Shift: 02:14 in  │
├─────────────────────────────────────────────────────────────────────┤
│ INCOMING CALLS                                                      │
│                                                                     │
│ 🔴 CRITICAL — Waiting 00:47    [TAKE CALL]                         │
│    IVR: "not safe" · Repeat caller from Oct 12 high-risk          │
│                                                                     │
│ 🟠 HIGH — Waiting 01:23        [TAKE CALL]                         │
│    Language: Hindi/English · First call                            │
│                                                                     │
│ ─────────────────────────────────────────────────────────────────  │
│ P2/P3 Queue: 3 calls waiting (next est. 6 min)                     │
│                                                                     │
│ RECENT CALLS                                                        │
│ 14:02  HIGH → de-escalated  22 min  [Replay]                       │
│ 13:38  MEDIUM → referred    18 min  [Replay]                       │
└─────────────────────────────────────────────────────────────────────┘
```

- P0/P1 calls shown with urgency styling and [TAKE CALL] button
- P0: audio alert (soft chime) when new P0 enters queue
- Operator can see waiting duration; builds urgency naturally
- No personal caller details shown pre-answer (privacy)

---

## Screen 5: Post-Call Micro-Coaching

**Route:** `/operator/debrief/[callSid]`  
Appears automatically 30 seconds after call ends.

```
┌─────────────────────────────────────────────────────────────────────┐
│ 📋 CALL SUMMARY — 22:45 minutes                                     │
├─────────────────────────────────────────────────────────────────────┤
│ Peak risk: CRITICAL (reached at 18 min)                             │
│ Outcome: Ambulance dispatched + shelter referral                    │
│ AI suggestions: 8 shown — 6 accepted, 1 modified, 1 rejected        │
│                                                                     │
│ ✅ WHAT WENT WELL                                                   │
│ Your acknowledgement at minute 3 before asking about safety         │
│ correlated with caller becoming more open (narrative shift ↑)      │
│                                                                     │
│ 💡 ONE THING FOR NEXT TIME                                          │
│ After caller mentioned "decided twice", a direct but gentle         │
│ safety check question tends to have higher de-escalation rates.    │
│                                                                     │
│ [Set outcome label:  De-escalated  ▾]      [Done — Back to Queue]  │
└─────────────────────────────────────────────────────────────────────┘
```

- Max 2 coaching points; never more
- Based on actual call data, not generic tips
- Operator sets outcome label (feeds longitudinal learning)
- Skippable after 10 seconds

---

## Responsive Behaviour

- HUD designed for 1440px+ desktop (crisis call stations)
- Supervisor dashboard: 1200px+
- No mobile layout for operator HUD (deliberate — phone calls require focus)
- Supervisor dashboard: tablet-compatible (iPad Pro in landscape)

---

## Accessibility

- All colour-coded information also has a text/icon label (never colour alone)
- Risk levels have distinct icons: ● LOW, ▲ MEDIUM, ■ HIGH, ★ CRITICAL
- All keyboard shortcuts listed in a [?] help panel
- Font minimum 16px for all actionable text
- Operator fatigue mode: increases all font sizes by 20% if shift > 6 hours
