"""Провайдер транскрипции через OpenAI Whisper API."""

from __future__ import annotations

import io
from collections.abc import Callable

from openai import OpenAI

from app.core.interfaces import TranscriptionProvider


class OpenAIWhisperProvider(TranscriptionProvider):
    """Транскрибирует аудио через API OpenAI."""

    def __init__(self, api_key: str, model_name: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model_name = model_name

    def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        language: str | None = None,
        *,
        on_partial: Callable[[str], None] | None = None,
    ) -> str:
        del sample_rate, on_partial
        if not audio_bytes:
            return ""

        buffer = io.BytesIO(audio_bytes)
        buffer.name = "audio.wav"
        kwargs: dict = {"model": self._model_name, "file": buffer}
        if language:
            kwargs["language"] = language
        response = self._client.audio.transcriptions.create(**kwargs)
        return response.text.strip()
