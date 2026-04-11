"""STT Pipeline — Sarvam AI Saaras integration with Whisper fallback.
Follows ARCHITECTURE.md Section 6 and IMPLEMENTATION_GUIDE.md Phase 4.
"""
import asyncio
import httpx
import numpy as np
import struct
import os
import logging
import tempfile
from collections import deque
from pipeline.event_bus import EventBus

logger = logging.getLogger(__name__)

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_BASE_URL = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")
UNCERTAIN_THRESHOLD = 0.65
STT_FAILURE_CONSECUTIVE = 3  # failures before triggering degradation


class AudioBuffer:
    """Rolling PCM audio buffer with overlap."""

    def __init__(self, window_ms: int = 2000, overlap_ms: int = 500, sample_rate: int = 8000):
        self.window_samples = int(window_ms / 1000 * sample_rate)
        self.overlap_samples = int(overlap_ms / 1000 * sample_rate)
        self.buffer: deque = deque(maxlen=self.window_samples * 3)

    def append(self, pcm_bytes: bytes):
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        self.buffer.extend(samples.tolist())

    def ready(self) -> bool:
        return len(self.buffer) >= self.window_samples

    def get(self) -> bytes:
        samples = list(self.buffer)[:self.window_samples]
        # Advance buffer keeping overlap
        for _ in range(self.window_samples - self.overlap_samples):
            if self.buffer:
                self.buffer.popleft()
        return np.array(samples, dtype=np.int16).tobytes()


class SarvamSTTPipeline:
    """Sarvam AI Saaras STT pipeline with Whisper fallback."""

    def __init__(self):
        self.buffers: dict[str, AudioBuffer] = {}
        self.failure_counts: dict[str, int] = {}
        self.fallback_active: dict[str, bool] = {}
        self._whisper_model = None  # Lazy load

    def get_buffer(self, call_sid: str) -> AudioBuffer:
        if call_sid not in self.buffers:
            self.buffers[call_sid] = AudioBuffer()
        return self.buffers[call_sid]

    async def process_chunk(self, call_sid: str, pcm_bytes: bytes):
        """Process an incoming audio chunk (PCM 16-bit 8kHz mono)."""
        buf = self.get_buffer(call_sid)
        buf.append(pcm_bytes)

        if not buf.ready():
            return

        audio_segment = buf.get()
        await self._emit_audio_features(call_sid, audio_segment)

        if self.fallback_active.get(call_sid):
            result = await self._transcribe_whisper(audio_segment)
        else:
            result = await self._transcribe_sarvam(call_sid, audio_segment)

        if result and result.get("text", "").strip():
            await EventBus.emit('stt.segment', {
                'call_sid': call_sid,
                'text': result['text'],
                'language_tags': result.get('language_tags', []),
                'confidence': result.get('confidence', 0.5),
                'uncertain': result.get('confidence', 0.5) < UNCERTAIN_THRESHOLD,
                'word_timestamps': result.get('word_timestamps', [])
            })

    async def _transcribe_sarvam(self, call_sid: str, audio: bytes) -> dict | None:
        """Call Sarvam Saaras STT API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                wav_data = self._to_wav(audio)
                response = await client.post(
                    f"{SARVAM_BASE_URL}/speech-to-text-translate",
                    headers={"api-subscription-key": SARVAM_API_KEY},
                    files={"file": ("audio.wav", wav_data, "audio/wav")},
                    data={
                        "model": "saaras:v1",
                        "language_code": "unknown"  # auto-detect + code-switch
                    }
                )
                response.raise_for_status()
                data = response.json()

                # Reset failure count on success
                self.failure_counts[call_sid] = 0

                transcript = data.get("transcript", "")
                lang_code = data.get("language_code", "en")

                return {
                    "text": transcript,
                    "language_tags": [{"phrase": transcript, "lang": lang_code}] if transcript else [],
                    "confidence": data.get("confidence", 0.75),
                    "word_timestamps": []
                }

        except httpx.TimeoutException:
            logger.warning(f"Sarvam STT timeout for {call_sid}")
            return await self._handle_failure(call_sid, "timeout")
        except httpx.HTTPStatusError as e:
            logger.error(f"Sarvam STT HTTP {e.response.status_code} for {call_sid}")
            return await self._handle_failure(call_sid, f"HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"Sarvam STT error for {call_sid}: {e}")
            return await self._handle_failure(call_sid, str(e))

    async def _handle_failure(self, call_sid: str, reason: str) -> dict | None:
        self.failure_counts[call_sid] = self.failure_counts.get(call_sid, 0) + 1
        if self.failure_counts[call_sid] >= STT_FAILURE_CONSECUTIVE:
            await self._trigger_stt_failure(call_sid, reason)
        return None

    async def _trigger_stt_failure(self, call_sid: str, reason: str):
        """Graceful degradation to Whisper fallback — per ETHICS_AND_SAFETY.md."""
        logger.warning(f"STT failure for {call_sid}: switching to Whisper fallback")
        await EventBus.emit('call.state_change', {
            'call_sid': call_sid,
            'old_state': 'active',
            'new_state': 'stt_degraded',
            'triggered_by': f'STT failure after {STT_FAILURE_CONSECUTIVE} attempts: {reason}'
        })
        self.fallback_active[call_sid] = True

    async def _transcribe_whisper(self, audio: bytes) -> dict | None:
        """Local Whisper tiny model fallback — always available, lower accuracy."""
        try:
            import whisper
            if self._whisper_model is None:
                self._whisper_model = whisper.load_model("tiny")

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(self._to_wav(audio))
                path = f.name

            result = self._whisper_model.transcribe(path, language=None)
            os.unlink(path)

            return {
                "text": result.get("text", ""),
                "confidence": 0.5,  # Whisper doesn't provide per-segment confidence
                "language_tags": []
            }
        except ImportError:
            logger.warning("Whisper not installed; STT unavailable")
            return None
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return None

    async def _emit_audio_features(self, call_sid: str, audio: bytes):
        """Emit prosody/energy features for emotion and ambient agents."""
        samples = np.frombuffer(audio, dtype=np.int16).astype(float)
        if len(samples) == 0:
            return

        energy = float(np.sqrt(np.mean(samples ** 2)))
        silence_ratio = float(np.mean(np.abs(samples) < 500))
        speaking_rate = 0.0  # Placeholder: computed from word timestamps

        await EventBus.emit('audio.features', {
            'call_sid': call_sid,
            'prosody_energy': energy,
            'pitch_hz': 0.0,  # YIN pitch detection placeholder
            'speaking_rate_wpm': speaking_rate,
            'silence_ratio': silence_ratio,
            'chunk_ms': int(len(samples) / 8)  # 8000 samples/sec
        })

    @staticmethod
    def _to_wav(pcm: bytes) -> bytes:
        """Wrap raw PCM in WAV header (8kHz, mono, 16-bit)."""
        sample_rate = 8000
        num_channels = 1
        bits_per_sample = 16
        data_size = len(pcm)
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8

        header = struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF', 36 + data_size, b'WAVE', b'fmt ', 16,
            1, num_channels, sample_rate,
            byte_rate, block_align, bits_per_sample,
            b'data', data_size
        )
        return header + pcm

    def cleanup(self, call_sid: str):
        """Release resources for a completed call."""
        self.buffers.pop(call_sid, None)
        self.failure_counts.pop(call_sid, None)
        self.fallback_active.pop(call_sid, None)
