"""Локальный провайдер транскрипции через Faster-Whisper."""

from __future__ import annotations

import io
import json
import os
from collections.abc import Callable
from typing import Any

import numpy as np
from faster_whisper import WhisperModel
from scipy.io.wavfile import read as wav_read

from app.core.interfaces import TranscriptionProvider


def _agent_debug_log(hypothesis_id: str, location: str, message: str, data: dict[str, object]) -> None:
    """Пишет NDJSON-лог отладки без секретов."""
    try:
        _log_path = "/Users/krasikov/projects/ghostwriter/.cursor/debug-edce00.log"
        os.makedirs(os.path.dirname(_log_path), exist_ok=True)
        payload: dict[str, object] = {
            "sessionId": "edce00",
            "runId": os.environ.get("GHOST_DEBUG_RUN_ID", "run1"),
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(__import__("time").time() * 1000),
        }
        with open(_log_path, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


class FasterWhisperProvider(TranscriptionProvider):
    """Транскрибирует аудио локальной моделью Faster-Whisper."""

    def __init__(self, model_name: str, device: str = "cpu", compute_type: str = "int8") -> None:
        self._model = WhisperModel(model_name, device=device, compute_type=compute_type)

    def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        language: str | None = None,
        *,
        on_partial: Callable[[str], None] | None = None,
    ) -> str:
        del sample_rate
        if not audio_bytes:
            return ""

        local_sample_rate, pcm = wav_read(io.BytesIO(audio_bytes))
        audio = self._to_float32(pcm)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        # region agent log
        _agent_debug_log(
            "H19",
            "faster_whisper_provider.py:transcribe:input",
            "stt input stats",
            {
                "audio_len": int(audio.shape[0]) if hasattr(audio, "shape") else 0,
                "wav_sample_rate": int(local_sample_rate),
                "peak": peak,
                "rms": rms,
                "language": language or "",
            },
        )
        # endregion
        segments, _info = self._model.transcribe(
            audio=audio,
            language=language,
            vad_filter=True,
        )
        parts: list[str] = []
        for segment in segments:
            chunk = segment.text.strip()
            if chunk:
                parts.append(chunk)
                if on_partial:
                    on_partial(" ".join(parts).strip())
        return " ".join(parts).strip()

    def _to_float32(self, pcm: Any) -> np.ndarray:
        audio = np.asarray(pcm)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if audio.dtype == np.int16:
            return (audio / 32768.0).astype(np.float32)
        return audio.astype(np.float32)
