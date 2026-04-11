# DATABASE SCHEMA — VoiceForward

All tables live in PostgreSQL. Redis is used for ephemeral session state and event bus only.

---

## Table: `calls`

Primary record per phone call session.

```sql
CREATE TABLE calls (
  call_sid          VARCHAR(64) PRIMARY KEY,        -- Exotel CallSid
  started_at        TIMESTAMPTZ NOT NULL,
  answered_at       TIMESTAMPTZ,                    -- when operator picked up
  ended_at          TIMESTAMPTZ,
  duration_seconds  INTEGER,

  operator_id       UUID REFERENCES operators(id),
  helpline_id       UUID REFERENCES helplines(id),

  -- Language
  language_primary  VARCHAR(10),                    -- ISO code: hi, en, mr, te, etc.
  languages_detected VARCHAR(10)[],                 -- all languages heard

  -- Priority
  priority_tier     VARCHAR(4) NOT NULL DEFAULT 'P2', -- P0 P1 P2 P3
  priority_score    INTEGER,                        -- 0-100 raw score
  priority_reason   VARCHAR(255),                   -- why this tier was assigned

  -- Risk
  final_risk_level  VARCHAR(10),                    -- LOW MEDIUM HIGH CRITICAL UNKNOWN
  peak_risk_level   VARCHAR(10),                    -- highest risk reached in call
  peak_risk_at      TIMESTAMPTZ,

  -- Compliance
  ai_disclosed      BOOLEAN DEFAULT FALSE,
  disclosed_at      TIMESTAMPTZ,
  opted_out         BOOLEAN DEFAULT FALSE,
  opted_out_at      TIMESTAMPTZ,
  shadow_mode       BOOLEAN DEFAULT FALSE,           -- if opted out, AI still runs but hidden

  -- Outcome
  outcome_label     VARCHAR(30),                    -- de_escalated | escalated | referred | dropped | unknown
  outcome_set_at    TIMESTAMPTZ,
  outcome_set_by    UUID REFERENCES operators(id),

  -- Privacy
  caller_phone_hash VARCHAR(64),                    -- SHA-256 of phone number; never raw
  anonymised_at     TIMESTAMPTZ,                    -- when PII wipe ran
  erasure_requested BOOLEAN DEFAULT FALSE,

  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_calls_operator ON calls(operator_id);
CREATE INDEX idx_calls_started_at ON calls(started_at);
CREATE INDEX idx_calls_priority ON calls(priority_tier, started_at);
CREATE INDEX idx_calls_risk ON calls(final_risk_level);
```

---

## Table: `ai_suggestions`

**Immutable audit log.** No UPDATE or DELETE permitted (enforced via row-level security).

```sql
CREATE TABLE ai_suggestions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_sid          VARCHAR(64) REFERENCES calls(call_sid),
  timestamp         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- What was shown
  suggestion_text   TEXT NOT NULL,
  risk_level        VARCHAR(10) NOT NULL,
  risk_score        INTEGER NOT NULL,
  confidence        FLOAT NOT NULL,

  -- Full reasoning (the glass box)
  reasoning_chain   JSONB NOT NULL,
  -- Structure:
  -- {
  --   "agents": {
  --     "emotion": {"score": 7, "confidence": 0.8, "explanation": "...", "dimensions": {...}},
  --     "ambient": {"score": 5, "confidence": 0.9, "explanation": "..."},
  --     "narrative": {"score": 8, "confidence": 0.85, "explanation": "..."},
  --     "language": {"score": 3, "confidence": 0.7, "explanation": "..."}
  --   },
  --   "conflicts": ["emotion=3 vs narrative=8"],
  --   "resolution": "Defaulted to higher risk — NarrativeAgent triggered keyword override",
  --   "stt_confidence": 0.78,
  --   "resource_triggers": ["show_shelter"]
  -- }

  -- Operator response
  operator_action       VARCHAR(20),              -- accepted | modified | rejected | no_action
  operator_action_at    TIMESTAMPTZ,
  operator_modification TEXT,                     -- if modified, what did they change to
  operator_id           UUID REFERENCES operators(id),

  -- Meta
  model_version         VARCHAR(50),              -- which version of each model was running
  call_minute           INTEGER                   -- which minute of the call this was
);

-- Prevent modification (immutable audit)
ALTER TABLE ai_suggestions ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_suggestions_insert_only ON ai_suggestions FOR INSERT WITH CHECK (true);
CREATE POLICY ai_suggestions_select ON ai_suggestions FOR SELECT USING (true);
-- No UPDATE or DELETE policy = denied

CREATE INDEX idx_suggestions_call ON ai_suggestions(call_sid);
CREATE INDEX idx_suggestions_risk ON ai_suggestions(risk_level);
CREATE INDEX idx_suggestions_action ON ai_suggestions(operator_action);
```

---

## Table: `operators`

```sql
CREATE TABLE operators (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  helpline_id     UUID REFERENCES helplines(id),
  name            VARCHAR(100) NOT NULL,
  email           VARCHAR(255) UNIQUE,
  password_hash   VARCHAR(255),
  role            VARCHAR(20) NOT NULL DEFAULT 'operator', -- operator | supervisor | admin
  languages       VARCHAR(10)[] NOT NULL DEFAULT '{"en"}', -- languages operator speaks
  experience_tier VARCHAR(10) DEFAULT 'junior',            -- junior | mid | senior
  -- Used for P1 routing: P1 calls prefer senior operators
  active          BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Table: `helplines`

```sql
CREATE TABLE helplines (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                VARCHAR(200) NOT NULL,
  state               VARCHAR(50),
  city                VARCHAR(50),
  type                VARCHAR(50),                   -- suicide | domestic_violence | child | general
  phone_number        VARCHAR(20),
  exotel_account_sid  VARCHAR(100),

  -- Configuration
  risk_threshold_high INTEGER DEFAULT 6,             -- score at which HIGH alert triggers
  risk_threshold_critical INTEGER DEFAULT 8,
  p3_diversion_queue_depth INTEGER DEFAULT 3,        -- when to start diverting P3
  ai_enabled          BOOLEAN DEFAULT TRUE,
  languages_supported VARCHAR(10)[] DEFAULT '{"en", "hi"}',
  active              BOOLEAN DEFAULT TRUE,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Table: `resources`

```sql
CREATE TABLE resources (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  helpline_id       UUID REFERENCES helplines(id),   -- null = shared national resource

  name              VARCHAR(200) NOT NULL,
  name_hi           VARCHAR(200),                    -- Hindi name
  name_local        VARCHAR(200),                    -- regional language name
  description       TEXT,

  category          VARCHAR(30) NOT NULL,
  -- hospital | police | shelter | ngo | mental_health | helpline | ambulance | pharmacy

  -- Location
  address           TEXT,
  city              VARCHAR(100),
  district          VARCHAR(100),
  state             VARCHAR(50),
  lat               DOUBLE PRECISION,
  lng               DOUBLE PRECISION,

  -- Contact
  phone             VARCHAR(20),
  phone_alt         VARCHAR(20),
  whatsapp          VARCHAR(20),
  email             VARCHAR(100),
  website           VARCHAR(255),

  -- Operational
  available_24x7    BOOLEAN DEFAULT FALSE,
  hours             VARCHAR(100),                    -- "9am–6pm Mon–Sat"
  languages         VARCHAR(10)[],
  capacity          INTEGER,                         -- for shelters: number of beds

  -- Effectiveness (updated by analytics service)
  follow_through_rate FLOAT DEFAULT 0.5,             -- 0.0–1.0; updated weekly
  referral_count    INTEGER DEFAULT 0,
  positive_outcomes INTEGER DEFAULT 0,

  -- Dispatch
  dispatchable      BOOLEAN DEFAULT FALSE,           -- can be dispatched directly from HUD
  dispatch_type     VARCHAR(20),                     -- api | phone | manual
  dispatch_endpoint VARCHAR(255),                    -- API URL if api dispatch

  active            BOOLEAN DEFAULT TRUE,
  verified_at       TIMESTAMPTZ,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_resources_location ON resources USING GIST (
  ll_to_earth(lat, lng)
);
CREATE INDEX idx_resources_category ON resources(category);
CREATE INDEX idx_resources_state ON resources(state, city);
```

---

## Table: `call_queue`

Live queue state (also mirrored in Redis for real-time access).

```sql
CREATE TABLE call_queue (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_sid        VARCHAR(64) NOT NULL,
  helpline_id     UUID REFERENCES helplines(id),

  priority_tier   VARCHAR(4) NOT NULL,
  queued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  answered_at     TIMESTAMPTZ,
  abandoned_at    TIMESTAMPTZ,
  diverted_at     TIMESTAMPTZ,

  assigned_operator_id UUID REFERENCES operators(id),
  status          VARCHAR(20) DEFAULT 'waiting',     -- waiting | answered | abandoned | diverted

  wait_seconds    INTEGER,                           -- computed on answer/divert
  caller_id_hash  VARCHAR(64)
);

CREATE INDEX idx_queue_priority ON call_queue(priority_tier, queued_at);
CREATE INDEX idx_queue_status ON call_queue(status, helpline_id);
```

---

## Table: `diversion_log`

Every P3 call that was offered diversion.

```sql
CREATE TABLE diversion_log (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_sid          VARCHAR(64),
  helpline_id       UUID REFERENCES helplines(id),
  diverted_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  queue_depth       INTEGER NOT NULL,               -- how deep queue was when diverted
  priority_tier     VARCHAR(4) NOT NULL,            -- always P3 for auto-diversion

  -- What was offered and chosen
  options_offered   VARCHAR(20)[],                  -- ['callback', 'whatsapp', 'self_help']
  caller_choice     VARCHAR(20),                    -- callback | whatsapp | self_help | hung_up | no_response

  -- Follow-up
  callback_scheduled_at TIMESTAMPTZ,
  callback_completed    BOOLEAN,
  whatsapp_sent         BOOLEAN,

  caller_id_hash    VARCHAR(64)
);
```

---

## Table: `dispatch_log`

Every dispatch action taken from the HUD.

```sql
CREATE TABLE dispatch_log (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_sid        VARCHAR(64) REFERENCES calls(call_sid),
  operator_id     UUID REFERENCES operators(id),

  action_type     VARCHAR(30) NOT NULL,             -- ambulance | police | shelter | supervisor_ping | resource_connect
  resource_id     UUID REFERENCES resources(id),

  location_lat    DOUBLE PRECISION,
  location_lng    DOUBLE PRECISION,
  location_address TEXT,

  dispatched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  confirmed_by_operator BOOLEAN NOT NULL DEFAULT FALSE,
  status          VARCHAR(20) DEFAULT 'sent',       -- sent | confirmed | failed | cancelled
  failure_reason  VARCHAR(255),

  exotel_conference_id VARCHAR(100)                 -- if 3-way call was bridged
);
```

---

## Table: `phrase_outcomes`

Anonymised phrase-outcome pairs for longitudinal learning.

```sql
CREATE TABLE phrase_outcomes (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  helpline_id       UUID REFERENCES helplines(id),

  -- De-identified call context
  call_minute       INTEGER,
  language          VARCHAR(10),
  risk_level_at_use VARCHAR(10),
  caller_profile_hash VARCHAR(64),                  -- anonymised: age_band + language + type

  -- The phrase (operator guidance that was accepted and used)
  phrase_text       TEXT NOT NULL,
  phrase_category   VARCHAR(50),                    -- validation | empathy | resource | safety_plan

  -- Outcome
  outcome_label     VARCHAR(30),                    -- de_escalated | escalated | referred | etc.
  outcome_positive  BOOLEAN,

  recorded_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_phrase_outcomes_helpline ON phrase_outcomes(helpline_id, outcome_positive);
CREATE INDEX idx_phrase_outcomes_category ON phrase_outcomes(phrase_category);
```

---

## Table: `model_versions`

Tracks which model versions are active; required for MeitY AI governance.

```sql
CREATE TABLE model_versions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id        VARCHAR(30) NOT NULL,             -- emotion | ambient | narrative | meta | stt
  version_tag     VARCHAR(50) NOT NULL,
  deployed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deployed_by     UUID REFERENCES operators(id),   -- admin who deployed
  evaluation_notes TEXT,
  active          BOOLEAN DEFAULT TRUE,
  superseded_at   TIMESTAMPTZ
);
```

---

## Redis Keys (Session State)

```
# Active call session state (TTL: call duration + 1hr)
session:{call_sid}:state         → JSON: {state, priority, operator_id, ...}
session:{call_sid}:risk          → JSON: {level, score, confidence, guidance_id}
session:{call_sid}:agents        → JSON: {emotion: {...}, ambient: {...}, ...}
session:{call_sid}:transcript    → LIST: last 20 STT segments (for agent context)
session:{call_sid}:location      → JSON: {city, lat, lng} or null

# Queue state (TTL: session)
queue:{helpline_id}:p0           → ZSET: call_sid → queued_timestamp
queue:{helpline_id}:p1           → ZSET
queue:{helpline_id}:p2           → ZSET
queue:{helpline_id}:p3           → ZSET

# Operator availability
operator:{operator_id}:status    → STRING: available | busy | break | offline
operator:{operator_id}:call_sid  → STRING: current call

# Live board (supervisor)
board:{helpline_id}:active       → HSET: call_sid → JSON card data
board:{helpline_id}:metrics      → JSON: {active_count, queued_count, ...}
```

---

## Migrations

Use Alembic for schema migrations:

```bash
alembic init alembic
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

Seed scripts in `infra/postgres/seed_resources.sql` — pre-populates 50+ resources for Mumbai, Delhi, Bengaluru, Chennai, Hyderabad.
