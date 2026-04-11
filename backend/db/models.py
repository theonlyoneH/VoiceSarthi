from sqlalchemy import Column, String, Boolean, Float, Integer, DateTime, \
    ForeignKey, ARRAY, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
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
    reasoning_chain = Column(JSONB, nullable=False)
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
    website = Column(String(255))
    available_24x7 = Column(Boolean, default=False)
    hours = Column(String(100))
    languages = Column(ARRAY(String))
    capacity = Column(Integer)
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


class CallQueue(Base):
    __tablename__ = 'call_queue'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_sid = Column(String(64), nullable=False)
    helpline_id = Column(UUID(as_uuid=True), ForeignKey('helplines.id'))
    priority_tier = Column(String(4), nullable=False)
    queued_at = Column(DateTime(timezone=True), server_default=func.now())
    answered_at = Column(DateTime(timezone=True))
    abandoned_at = Column(DateTime(timezone=True))
    diverted_at = Column(DateTime(timezone=True))
    assigned_operator_id = Column(UUID(as_uuid=True), ForeignKey('operators.id'))
    status = Column(String(20), default='waiting')
    wait_seconds = Column(Integer)
    caller_id_hash = Column(String(64))


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


class PhraseOutcome(Base):
    __tablename__ = 'phrase_outcomes'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    helpline_id = Column(UUID(as_uuid=True), ForeignKey('helplines.id'))
    call_minute = Column(Integer)
    language = Column(String(10))
    risk_level_at_use = Column(String(10))
    caller_profile_hash = Column(String(64))
    phrase_text = Column(Text, nullable=False)
    phrase_category = Column(String(50))
    outcome_label = Column(String(30))
    outcome_positive = Column(Boolean)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelVersion(Base):
    __tablename__ = 'model_versions'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(30), nullable=False)
    version_tag = Column(String(50), nullable=False)
    deployed_at = Column(DateTime(timezone=True), server_default=func.now())
    deployed_by = Column(UUID(as_uuid=True), ForeignKey('operators.id'))
    evaluation_notes = Column(Text)
    active = Column(Boolean, default=True)
    superseded_at = Column(DateTime(timezone=True))
