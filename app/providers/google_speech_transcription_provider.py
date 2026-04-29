"""Транскрипция через Google Cloud Speech-to-Text (REST v1)."""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx

from app.core.interfaces import TranscriptionProvider
from app.core.provider_credentials import stt_secret_key_name

if TYPE_CHECKING:
    from app.core.config_manager import ConfigManager

GCP_SPEECH_RECOGNIZE_URL = "https://speech.googleapis.com/v1/speech:recognize"


class GoogleSpeechTranscriptionProvider(TranscriptionProvider):
    """Распознаёт WAV через Google Cloud Speech-to-Text API."""

    def __init__(self, config_manager: ConfigManager, model_name: str) -> None:
        self._config_manager = config_manager
        self._model_name = (model_name or "").strip() or "latest_long"

    @staticmethod
    def _should_fallback_to_latest_short(error: httpx.HTTPStatusError, *, model_name: str) -> bool:
        """Определяет, можно ли безопасно повторить запрос с ``latest_short``."""
        if model_name != "latest_long":
            return False
        status_code = error.response.status_code if error.response is not None else None
        if status_code != 400:
            return False
        try:
            payload = error.response.json()
        except ValueError:
            return False
        if not isinstance(payload, dict):
            return False

        err = payload.get("error")
        if not isinstance(err, dict):
            return False
        status = str(err.get("status", "") or "").upper()
        message = str(err.get("message", "") or "").lower()
        if status == "INVALID_ARGUMENT":
            return True
        return "model" in message and ("invalid" in message or "unsupported" in message)

    def _recognize(
        self,
        *,
        api_key: str,
        audio_bytes: bytes,
        sample_rate: int,
        model_name: str,
        language: str | None,
    ) -> dict[str, Any]:
        config: dict[str, Any] = {
            "encoding": "LINEAR16",
            "sampleRateHertz": sample_rate,
            "model": model_name,
            "enableAutomaticPunctuation": True,
        }
        if language:
            config["languageCode"] = language
        else:
            config["languageCode"] = "ru-RU"

        payload: dict[str, Any] = {
            "config": config,
            "audio": {"content": base64.b64encode(audio_bytes).decode("utf-8")},
        }

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                GCP_SPEECH_RECOGNIZE_URL,
                params={"key": api_key},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

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

        key_name = stt_secret_key_name("gcp_speech")
        assert key_name
        api_key = (self._config_manager.get_secret(key_name) or "").strip()
        if not api_key:
            raise RuntimeError("Не задан GCP_STT_API_KEY для облачной транскрипции Google Cloud Speech-to-Text")

        try:
            data = self._recognize(
                api_key=api_key,
                audio_bytes=audio_bytes,
                sample_rate=sample_rate,
                model_name=self._model_name,
                language=language,
            )
        except httpx.HTTPStatusError as error:
            if not self._should_fallback_to_latest_short(error, model_name=self._model_name):
                raise
            data = self._recognize(
                api_key=api_key,
                audio_bytes=audio_bytes,
                sample_rate=sample_rate,
                model_name="latest_short",
                language=language,
            )

        results = data.get("results")
        if not isinstance(results, list):
            return ""

        parts: list[str] = []
        for result in results:
            if not isinstance(result, dict):
                continue
            alternatives = result.get("alternatives")
            if not isinstance(alternatives, list) or not alternatives:
                continue
            alt0 = alternatives[0]
            if not isinstance(alt0, dict):
                continue
            transcript = str(alt0.get("transcript", "") or "").strip()
            if transcript:
                parts.append(transcript)
        return " ".join(parts).strip()
