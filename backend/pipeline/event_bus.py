"""Event Bus — Redis Streams wrapper.
Follows ARCHITECTURE.md Section 4: Event Bus Schema.
"""
import redis.asyncio as redis
import json
from datetime import datetime
from typing import Any, AsyncGenerator
import os
import logging

logger = logging.getLogger(__name__)

STREAM_KEY = "voiceforward:events"
STREAM_MAXLEN = 10000  # Keep last 10k events


class EventBus:
    _client: redis.Redis = None

    @classmethod
    async def connect(cls):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        cls._client = redis.from_url(redis_url, decode_responses=True)
        logger.info(f"EventBus connected to Redis: {redis_url}")

    @classmethod
    async def disconnect(cls):
        if cls._client:
            await cls._client.aclose()

    @classmethod
    async def emit(cls, event_type: str, payload: dict) -> None:
        """Emit an event to the Redis stream."""
        if cls._client is None:
            logger.warning("EventBus not connected; skipping emit")
            return
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1",
            **payload
        }
        try:
            await cls._client.xadd(
                STREAM_KEY,
                {"data": json.dumps(event, default=str)},
                maxlen=STREAM_MAXLEN,
                approximate=True
            )
        except Exception as e:
            logger.error(f"EventBus emit error: {e}")

    @classmethod
    async def subscribe(
        cls,
        consumer_group: str,
        consumer_name: str,
        event_types: list[str] | None = None
    ) -> AsyncGenerator[dict, None]:
        """Yield events from the stream for a consumer group."""
        if cls._client is None:
            logger.error("EventBus not connected")
            return

        # Create consumer group if it doesn't exist
        try:
            await cls._client.xgroup_create(
                STREAM_KEY, consumer_group, id='0', mkstream=True
            )
        except Exception:
            pass  # Group already exists

        while True:
            try:
                messages = await cls._client.xreadgroup(
                    consumer_group, consumer_name,
                    {STREAM_KEY: '>'},
                    count=10,
                    block=1000
                )
                if messages:
                    for stream, entries in messages:
                        for entry_id, fields in entries:
                            try:
                                event = json.loads(fields["data"])
                                if event_types is None or event["type"] in event_types:
                                    yield event
                                await cls._client.xack(STREAM_KEY, consumer_group, entry_id)
                            except json.JSONDecodeError as e:
                                logger.error(f"EventBus JSON decode error: {e}")
            except Exception as e:
                logger.error(f"EventBus subscribe error: {e}")
                import asyncio
                await asyncio.sleep(1)

    @classmethod
    async def get_session_state(cls, call_sid: str) -> dict:
        """Get cached session state from Redis."""
        if cls._client is None:
            return {}
        try:
            data = await cls._client.get(f"session:{call_sid}:state")
            return json.loads(data) if data else {}
        except Exception:
            return {}

    @classmethod
    async def set_session_state(cls, call_sid: str, state: dict, ttl_seconds: int = 7200):
        """Cache session state in Redis."""
        if cls._client is None:
            return
        try:
            await cls._client.setex(
                f"session:{call_sid}:state",
                ttl_seconds,
                json.dumps(state, default=str)
            )
        except Exception as e:
            logger.error(f"EventBus set_session_state error: {e}")

    @classmethod
    async def delete_session(cls, call_sid: str):
        """Delete all Redis keys for a session (DPDPA erasure)."""
        if cls._client is None:
            return
        keys = await cls._client.keys(f"session:{call_sid}:*")
        if keys:
            await cls._client.delete(*keys)
        logger.info(f"Deleted {len(keys)} Redis keys for session {call_sid}")
