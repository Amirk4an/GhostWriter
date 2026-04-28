"""Транскрипция через Deepgram prerecorded API."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx

from app.core.interfaces import TranscriptionProvider
from app.core.provider_credentials import stt_secret_key_name

if TYPE_CHECKING:
    from app.core.config_manager import ConfigManager


class DeepgramTranscriptionProvider(TranscriptionProvider):
    """Сырой WAV в Deepgram ``/v1/listen``."""

    def __init__(self, config_manager: ConfigManager, model_name: str) -> None:
        self._config_manager = config_manager
        self._model_name = model_name or "nova-2"

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
        key_name = stt_secret_key_name("deepgram")
        assert key_name
        token = (self._config_manager.get_secret(key_name) or "").strip()
        if not token:
            raise RuntimeError("Не задан DEEPGRAM_API_KEY для облачной транскрипции Deepgram")

        params: list[tuple[str, str]] = [("model", self._model_name)]
        if language:
            params.append(("language", language))

        query = "&".join(f"{quote(k)}={quote(v)}" for k, v in params)
        url = f"https://api.deepgram.com/v1/listen?{query}"

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Token {token}",
                    "Content-Type": "audio/wav",
                },
                content=audio_bytes,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        try:
            alt0 = data["results"]["channels"][0]["alternatives"][0]
            text = str(alt0.get("transcript", "") or "").strip()
        except (KeyError, IndexError, TypeError):
            return ""
        return text
