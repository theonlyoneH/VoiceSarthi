-- VoiceForward Database Schema
-- Strictly follows DATABASE_SCHEMA.md

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "earthdistance" CASCADE;

-- ─── Table: helplines ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS helplines (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                VARCHAR(200) NOT NULL,
  state               VARCHAR(50),
  city                VARCHAR(50),
  type                VARCHAR(50),
  phone_number        VARCHAR(20),
  exotel_account_sid  VARCHAR(100),

  risk_threshold_high INTEGER DEFAULT 6,
  risk_threshold_critical INTEGER DEFAULT 8,
  p3_diversion_queue_depth INTEGER DEFAULT 3,
  ai_enabled          BOOLEAN DEFAULT TRUE,
  languages_supported VARCHAR(10)[] DEFAULT '{en,hi}',
  active              BOOLEAN DEFAULT TRUE,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Table: operators ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS operators (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  helpline_id     UUID REFERENCES helplines(id),
  name            VARCHAR(100) NOT NULL,
  email           VARCHAR(255) UNIQUE,
  password_hash   VARCHAR(255),
  role            VARCHAR(20) NOT NULL DEFAULT 'operator',
  languages       VARCHAR(10)[] NOT NULL DEFAULT '{en}',
  experience_tier VARCHAR(10) DEFAULT 'junior',
  active          BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Table: calls ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS calls (
  call_sid          VARCHAR(64) PRIMARY KEY,
  started_at        TIMESTAMPTZ NOT NULL,
  answered_at       TIMESTAMPTZ,
  ended_at          TIMESTAMPTZ,
  duration_seconds  INTEGER,

  operator_id       UUID REFERENCES operators(id),
  helpline_id       UUID REFERENCES helplines(id),

  language_primary  VARCHAR(10),
  languages_detected VARCHAR(10)[],

  priority_tier     VARCHAR(4) NOT NULL DEFAULT 'P2',
  priority_score    INTEGER,
  priority_reason   VARCHAR(255),

  final_risk_level  VARCHAR(10),
  peak_risk_level   VARCHAR(10),
  peak_risk_at      TIMESTAMPTZ,

  ai_disclosed      BOOLEAN DEFAULT FALSE,
  disclosed_at      TIMESTAMPTZ,
  opted_out         BOOLEAN DEFAULT FALSE,
  opted_out_at      TIMESTAMPTZ,
  shadow_mode       BOOLEAN DEFAULT FALSE,

  outcome_label     VARCHAR(30),
  outcome_set_at    TIMESTAMPTZ,
  outcome_set_by    UUID REFERENCES operators(id),

  caller_phone_hash VARCHAR(64),
  anonymised_at     TIMESTAMPTZ,
  erasure_requested BOOLEAN DEFAULT FALSE,

  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calls_operator ON calls(operator_id);
CREATE INDEX IF NOT EXISTS idx_calls_started_at ON calls(started_at);
CREATE INDEX IF NOT EXISTS idx_calls_priority ON calls(priority_tier, started_at);
CREATE INDEX IF NOT EXISTS idx_calls_risk ON calls(final_risk_level);

-- ─── Table: ai_suggestions ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ai_suggestions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_sid          VARCHAR(64) REFERENCES calls(call_sid),
  timestamp         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  suggestion_text   TEXT NOT NULL,
  risk_level        VARCHAR(10) NOT NULL,
  risk_score        INTEGER NOT NULL,
  confidence        FLOAT NOT NULL,

  reasoning_chain   JSONB NOT NULL,

  operator_action       VARCHAR(20),
  operator_action_at    TIMESTAMPTZ,
  operator_modification TEXT,
  operator_id           UUID REFERENCES operators(id),

  model_version         VARCHAR(50),
  call_minute           INTEGER
);

-- Immutable audit: INSERT only
ALTER TABLE ai_suggestions ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_suggestions_insert_only ON ai_suggestions FOR INSERT WITH CHECK (true);
CREATE POLICY ai_suggestions_select ON ai_suggestions FOR SELECT USING (true);

CREATE INDEX IF NOT EXISTS idx_suggestions_call ON ai_suggestions(call_sid);
CREATE INDEX IF NOT EXISTS idx_suggestions_risk ON ai_suggestions(risk_level);
CREATE INDEX IF NOT EXISTS idx_suggestions_action ON ai_suggestions(operator_action);

-- ─── Table: resources ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS resources (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  helpline_id       UUID REFERENCES helplines(id),

  name              VARCHAR(200) NOT NULL,
  name_hi           VARCHAR(200),
  name_local        VARCHAR(200),
  description       TEXT,

  category          VARCHAR(30) NOT NULL,

  address           TEXT,
  city              VARCHAR(100),
  district          VARCHAR(100),
  state             VARCHAR(50),
  lat               DOUBLE PRECISION,
  lng               DOUBLE PRECISION,

  phone             VARCHAR(20),
  phone_alt         VARCHAR(20),
  whatsapp          VARCHAR(20),
  email             VARCHAR(100),
  website           VARCHAR(255),

  available_24x7    BOOLEAN DEFAULT FALSE,
  hours             VARCHAR(100),
  languages         VARCHAR(10)[],
  capacity          INTEGER,

  follow_through_rate FLOAT DEFAULT 0.5,
  referral_count    INTEGER DEFAULT 0,
  positive_outcomes INTEGER DEFAULT 0,

  dispatchable      BOOLEAN DEFAULT FALSE,
  dispatch_type     VARCHAR(20),
  dispatch_endpoint VARCHAR(255),

  active            BOOLEAN DEFAULT TRUE,
  verified_at       TIMESTAMPTZ,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resources_category ON resources(category);
CREATE INDEX IF NOT EXISTS idx_resources_state ON resources(state, city);

-- ─── Table: call_queue ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS call_queue (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_sid        VARCHAR(64) NOT NULL,
  helpline_id     UUID REFERENCES helplines(id),

  priority_tier   VARCHAR(4) NOT NULL,
  queued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  answered_at     TIMESTAMPTZ,
  abandoned_at    TIMESTAMPTZ,
  diverted_at     TIMESTAMPTZ,

  assigned_operator_id UUID REFERENCES operators(id),
  status          VARCHAR(20) DEFAULT 'waiting',

  wait_seconds    INTEGER,
  caller_id_hash  VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_queue_priority ON call_queue(priority_tier, queued_at);
CREATE INDEX IF NOT EXISTS idx_queue_status ON call_queue(status, helpline_id);

-- ─── Table: diversion_log ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS diversion_log (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_sid          VARCHAR(64),
  helpline_id       UUID REFERENCES helplines(id),
  diverted_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  queue_depth       INTEGER NOT NULL,
  priority_tier     VARCHAR(4) NOT NULL,

  options_offered   VARCHAR(20)[],
  caller_choice     VARCHAR(20),

  callback_scheduled_at TIMESTAMPTZ,
  callback_completed    BOOLEAN,
  whatsapp_sent         BOOLEAN,

  caller_id_hash    VARCHAR(64)
);

-- ─── Table: dispatch_log ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dispatch_log (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_sid        VARCHAR(64) REFERENCES calls(call_sid),
  operator_id     UUID REFERENCES operators(id),

  action_type     VARCHAR(30) NOT NULL,
  resource_id     UUID REFERENCES resources(id),

  location_lat    DOUBLE PRECISION,
  location_lng    DOUBLE PRECISION,
  location_address TEXT,

  dispatched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  confirmed_by_operator BOOLEAN NOT NULL DEFAULT FALSE,
  status          VARCHAR(20) DEFAULT 'sent',
  failure_reason  VARCHAR(255),

  exotel_conference_id VARCHAR(100)
);

-- ─── Table: phrase_outcomes ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS phrase_outcomes (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  helpline_id       UUID REFERENCES helplines(id),

  call_minute       INTEGER,
  language          VARCHAR(10),
  risk_level_at_use VARCHAR(10),
  caller_profile_hash VARCHAR(64),

  phrase_text       TEXT NOT NULL,
  phrase_category   VARCHAR(50),

  outcome_label     VARCHAR(30),
  outcome_positive  BOOLEAN,

  recorded_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_phrase_outcomes_helpline ON phrase_outcomes(helpline_id, outcome_positive);
CREATE INDEX IF NOT EXISTS idx_phrase_outcomes_category ON phrase_outcomes(phrase_category);

-- ─── Table: model_versions ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS model_versions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id        VARCHAR(30) NOT NULL,
  version_tag     VARCHAR(50) NOT NULL,
  deployed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deployed_by     UUID REFERENCES operators(id),
  evaluation_notes TEXT,
  active          BOOLEAN DEFAULT TRUE,
  superseded_at   TIMESTAMPTZ
);

-- ─── Seed: Default Helpline ────────────────────────────────────────────────────

INSERT INTO helplines (id, name, state, city, type, phone_number, languages_supported, active)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'VoiceForward Demo Helpline',
  'Maharashtra',
  'Mumbai',
  'general',
  '1800-000-0000',
  '{en,hi,mr}',
  TRUE
) ON CONFLICT DO NOTHING;

-- ─── Seed: Default Operators ──────────────────────────────────────────────────

-- Password: "demo123" bcrypt hash
INSERT INTO operators (id, helpline_id, name, email, password_hash, role, languages, experience_tier)
VALUES
  ('00000000-0000-0000-0000-000000000010',
   '00000000-0000-0000-0000-000000000001',
   'Priya Sharma', 'priya@demo.com',
   '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBxSNi8cjY2jCa',
   'operator', '{hi,en,mr}', 'senior'),
  ('00000000-0000-0000-0000-000000000011',
   '00000000-0000-0000-0000-000000000001',
   'Rahul Verma', 'rahul@demo.com',
   '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBxSNi8cjY2jCa',
   'operator', '{hi,en}', 'mid'),
  ('00000000-0000-0000-0000-000000000012',
   '00000000-0000-0000-0000-000000000001',
   'Aisha Khan', 'aisha@demo.com',
   '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBxSNi8cjY2jCa',
   'operator', '{en,ur}', 'junior'),
  ('00000000-0000-0000-0000-000000000013',
   '00000000-0000-0000-0000-000000000001',
   'Dr. Lakshmi Nair', 'supervisor@demo.com',
   '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBxSNi8cjY2jCa',
   'supervisor', '{en,hi,ta,ml}', 'senior')
ON CONFLICT DO NOTHING;

-- ─── Seed: model_versions ─────────────────────────────────────────────────────

INSERT INTO model_versions (agent_id, version_tag, evaluation_notes, active)
VALUES
  ('emotion', 'v1.0.0-prosody', 'Audio prosody + energy baseline', TRUE),
  ('ambient', 'v1.0.0-audioclf', 'Audio classification heuristics', TRUE),
  ('narrative', 'v1.0.0-keyword', 'Rule-based keyword + NLP narrative', TRUE),
  ('language', 'v1.0.0-sarvam', 'Sarvam Saaras code-switch detection', TRUE),
  ('fatigue', 'v1.0.0-shift', 'Shift-time heuristic model', TRUE),
  ('meta', 'v1.0.0-fusion', 'Safety-first fusion with conflict resolution', TRUE),
  ('stt', 'saaras:v1', 'Sarvam Saaras STT model', TRUE)
ON CONFLICT DO NOTHING;
