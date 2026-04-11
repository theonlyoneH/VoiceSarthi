"""Audio Ingest Pipeline — Exotel real-time audio stream processor.
Follows ARCHITECTURE.md Section 3: Audio Ingestion Layer.

Receives raw PCM 16-bit 8kHz mono from Exotel, feeds SarvamSTTPipeline,
and emits audio.features events to the EventBus.
"""
import asyncio
import logging
import struct
import math
from typing import Optional

import numpy as np

from pipeline.event_bus import EventBus

logger = logging.getLogger(__name__)

# Audio config (Exotel default)
SAMPLE_RATE = 8000       # 8kHz
CHUNK_BYTES = 1600       # 100ms of PCM16 mono (8000 * 0.1 * 2 bytes)
CHUNK_DURATION_MS = 100  # milliseconds per chunk

# Thresholds
SILENCE_THRESHOLD = 150.0   # RMS below this is considered silence
HIGH_ENERGY_THRESHOLD = 4000.0
WINDOW_SIZE = 20             # Number of chunks to smooth over (~2 seconds)


class AudioIngestHandler:
    """
    Processes raw PCM audio from Exotel WebSocket streams.

    Responsibilities:
    - Buffer raw PCM bytes
    - Calculate audio features (RMS energy, silence ratio)
    - Feed SarvamSTTPipeline for transcription
    - Emit audio.features events to EventBus

    Usage:
        handler = AudioIngestHandler(call_sid, stt_pipeline)
        async for chunk in ws.iter_bytes():
            await handler.process_chunk(chunk)
        await handler.cleanup()
    """

    def __init__(self, call_sid: str, stt_pipeline=None):
        self.call_sid = call_sid
        self.stt_pipeline = stt_pipeline
        self._buffer = bytearray()
        self._energy_window: list[float] = []
        self._silence_window: list[bool] = []
        self._chunks_processed = 0
        self._emit_interval = 10  # Emit audio.features every N chunks (~1s)

    async def process_chunk(self, data: bytes) -> None:
        """Process a raw PCM chunk from Exotel."""
        if not data:
            return

        self._buffer.extend(data)

        # Process complete chunks
        while len(self._buffer) >= CHUNK_BYTES:
            chunk = bytes(self._buffer[:CHUNK_BYTES])
            self._buffer = self._buffer[CHUNK_BYTES:]
            await self._analyze_chunk(chunk)

    async def _analyze_chunk(self, chunk: bytes) -> None:
        """Analyze a single PCM chunk for acoustic features."""
        self._chunks_processed += 1

        # Convert PCM bytes to samples
        num_samples = len(chunk) // 2
        if num_samples == 0:
            return

        samples = struct.unpack(f'{num_samples}h', chunk[:num_samples * 2])
        energy = self._compute_rms(samples)
        is_silence = energy < SILENCE_THRESHOLD

        # Update rolling windows
        self._energy_window.append(energy)
        self._silence_window.append(is_silence)
        if len(self._energy_window) > WINDOW_SIZE:
            self._energy_window.pop(0)
        if len(self._silence_window) > WINDOW_SIZE:
            self._silence_window.pop(0)

        # Feed to STT pipeline every chunk
        if self.stt_pipeline:
            try:
                await self.stt_pipeline.process_chunk(self.call_sid, chunk)
            except Exception as e:
                logger.error(f"[AudioIngest] STT pipeline error for {self.call_sid}: {e}")

        # Emit audio.features event periodically
        if self._chunks_processed % self._emit_interval == 0:
            await self._emit_features()

    async def _emit_features(self) -> None:
        """Emit aggregated audio features to EventBus."""
        if not self._energy_window:
            return

        avg_energy = sum(self._energy_window) / len(self._energy_window)
        silence_ratio = sum(1 for s in self._silence_window if s) / len(self._silence_window)

        # Detect ambient signals
        ambient_hints = []
        if avg_energy > HIGH_ENERGY_THRESHOLD:
            ambient_hints.append("high_energy")
        if silence_ratio > 0.7:
            ambient_hints.append("prolonged_silence")

        try:
            await EventBus.emit('audio.features', {
                'call_sid': self.call_sid,
                'prosody_energy': round(avg_energy, 2),
                'silence_ratio': round(silence_ratio, 3),
                'pitch_hz': 0.0,       # Pitch estimation requires FFT — stub
                'chunk_ms': CHUNK_DURATION_MS * self._emit_interval,
                'chunks_processed': self._chunks_processed,
                'ambient_hints': ambient_hints,
            })
            logger.debug(
                f"[AudioIngest] {self.call_sid} | energy={avg_energy:.0f} "
                f"silence={silence_ratio:.0%} hints={ambient_hints}"
            )
        except Exception as e:
            logger.error(f"[AudioIngest] EventBus emit error: {e}")

    async def cleanup(self) -> None:
        """Call when the audio stream ends."""
        # Flush any remaining buffer
        if len(self._buffer) > 0:
            await self._analyze_chunk(bytes(self._buffer))

        logger.info(
            f"[AudioIngest] Stream ended for {self.call_sid}. "
            f"Total chunks: {self._chunks_processed}"
        )

    @staticmethod
    def _compute_rms(samples: tuple) -> float:
        """Compute Root Mean Square energy of audio samples."""
        if not samples:
            return 0.0
        sum_sq = sum(s * s for s in samples)
        return math.sqrt(sum_sq / len(samples))


# ── Convenience: async generator for Exotel stream ──────────────────────────

async def ingest_audio_stream(call_sid: str, websocket, stt_pipeline=None) -> None:
    """
    Top-level coroutine for handling an Exotel audio WebSocket.

    Args:
        call_sid: The Exotel call SID
        websocket: FastAPI WebSocket object
        stt_pipeline: SarvamSTTPipeline instance
    """
    handler = AudioIngestHandler(call_sid, stt_pipeline)
    logger.info(f"[AudioIngest] Stream started for call {call_sid}")

    try:
        await EventBus.emit('call.state_change', {
            'call_sid': call_sid,
            'old_state': 'queued',
            'new_state': 'stream_active',
            'triggered_by': 'audio_ingest',
        })

        async for chunk in websocket.iter_bytes():
            await handler.process_chunk(chunk)

    except Exception as e:
        logger.error(f"[AudioIngest] Stream error for {call_sid}: {e}")
    finally:
        await handler.cleanup()
        logger.info(f"[AudioIngest] Stream closed for call {call_sid}")
