"""Транскрипция через Yandex SpeechKit STT API."""

from __future__ import annotations

import io
import wave
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus

import httpx

from app.core.interfaces import TranscriptionProvider

if TYPE_CHECKING:
    from app.core.config_manager import ConfigManager

YANDEX_STT_RECOGNIZE_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"


class YandexSpeechTranscriptionProvider(TranscriptionProvider):
    """Преобразует WAV в текст через Yandex SpeechKit."""

    def __init__(self, config_manager: ConfigManager, model_name: str) -> None:
        self._config_manager = config_manager
        self._topic = (model_name or "").strip() or "general"

    @staticmethod
    def _wav_to_pcm16(audio_bytes: bytes) -> bytes:
        """Извлекает PCM16-данные из WAV-контейнера."""
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            if wav_file.getsampwidth() != 2:
                raise RuntimeError("Yandex STT ожидает WAV с глубиной 16 бит (PCM16)")
            return wav_file.readframes(wav_file.getnframes())

    def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        language: str | None = None,
        *,
        on_partial: Callable[[str], None] | None = None,
    ) -> str:
        del on_partial
        if not audio_bytes:
            return ""

        api_key = (self._config_manager.get_secret("YANDEX_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("Не задан YANDEX_API_KEY для облачной транскрипции Yandex SpeechKit")
        folder_id = (self._config_manager.peek_secret("YANDEX_FOLDER_ID") or "").strip()
        lang = (language or "").strip() or "ru-RU"
        pcm_bytes = self._wav_to_pcm16(audio_bytes)

        params: list[tuple[str, str]] = [
            ("lang", lang),
            ("format", "lpcm"),
            ("sampleRateHertz", str(sample_rate)),
            ("topic", self._topic),
        ]
        if folder_id:
            params.append(("folderId", folder_id))
        query = "&".join(f"{quote_plus(k)}={quote_plus(v)}" for k, v in params)
        url = f"{YANDEX_STT_RECOGNIZE_URL}?{query}"

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Api-Key {api_key}",
                    "Content-Type": "application/octet-stream",
                },
                content=pcm_bytes,
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()

        text = str(payload.get("result", "") or "").strip()
        return text
