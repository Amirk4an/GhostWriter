"""Транскрипция через Groq OpenAI-совместимый Whisper API."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx

from app.core.interfaces import TranscriptionProvider
from app.core.provider_credentials import stt_secret_key_name

if TYPE_CHECKING:
    from app.core.config_manager import ConfigManager

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class GroqWhisperProvider(TranscriptionProvider):
    """WAV → текст через Groq."""

    def __init__(self, config_manager: ConfigManager, model_name: str) -> None:
        self._config_manager = config_manager
        self._model_name = model_name

    def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        language: str | None = None,
        *,
        on_partial: Callable[[str], None] | None = None,
    ) -> str:
        del sample_rate, on_partial  # WAV уже в нужном формате пайплайна
        if not audio_bytes:
            return ""
        key_name = stt_secret_key_name("groq")
        assert key_name  # groq backend always maps to GROQ_API_KEY
        api_key = (self._config_manager.get_secret(key_name) or "").strip()
        if not api_key:
            raise RuntimeError("Не задан GROQ_API_KEY для облачной транскрипции Groq")

        files: dict[str, Any] = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        data: dict[str, str] = {"model": self._model_name}
        if language:
            data["language"] = language

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                GROQ_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files=files,
                data=data,
            )
            response.raise_for_status()
            payload = response.json()
        text = str(payload.get("text", "") or "").strip()
        return text
