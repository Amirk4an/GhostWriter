"""Локальный провайдер транскрипции через Faster-Whisper."""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any

import numpy as np
from faster_whisper import WhisperModel
from scipy.io.wavfile import read as wav_read

from app.core.interfaces import TranscriptionProvider


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
        del local_sample_rate
        audio = self._to_float32(pcm)
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
