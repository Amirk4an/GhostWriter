"""Тесты Yandex Speech STT-провайдера."""

from __future__ import annotations

import io
import wave
from typing import Any

from app.providers.yandex_speech_transcription_provider import YandexSpeechTranscriptionProvider


class _FakeConfigManager:
    def get_secret(self, key: str) -> str:
        assert key == "YANDEX_API_KEY"
        return "fake-yandex-key"

    def peek_secret(self, key: str) -> str | None:
        if key == "YANDEX_FOLDER_ID":
            return "folder-123"
        return None


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, **kwargs: Any) -> None:
        del kwargs

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        del exc_type, exc, tb
        return False

    def post(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        del args, kwargs
        return _FakeResponse({"result": "тест яндекс"})


def _make_wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 16)
    return buffer.getvalue()


def test_yandex_provider_returns_result(monkeypatch: Any) -> None:
    provider = YandexSpeechTranscriptionProvider(_FakeConfigManager(), "general")
    monkeypatch.setattr(
        "app.providers.yandex_speech_transcription_provider.httpx.Client",
        lambda **kwargs: _FakeClient(**kwargs),
    )
    text = provider.transcribe(_make_wav_bytes(), sample_rate=16000, language="ru-RU")
    assert text == "тест яндекс"


def test_yandex_provider_empty_audio_returns_empty() -> None:
    provider = YandexSpeechTranscriptionProvider(_FakeConfigManager(), "general")
    assert provider.transcribe(b"", sample_rate=16000, language="ru-RU") == ""
