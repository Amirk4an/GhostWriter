"""Тесты Google Speech STT-провайдера."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.providers.google_speech_transcription_provider import GoogleSpeechTranscriptionProvider


class _FakeConfigManager:
    def get_secret(self, key: str) -> str:
        assert key == "GCP_STT_API_KEY"
        return "fake-key"


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict[str, Any], request: httpx.Request) -> None:
        self.status_code = status_code
        self._payload = payload
        self.request = request

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("http error", request=self.request, response=self)

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse], **kwargs: Any) -> None:
        del kwargs
        self._responses = responses

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        del exc_type, exc, tb
        return False

    def post(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        del args, kwargs
        return self._responses.pop(0)


def test_fallback_latest_long_to_latest_short(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GoogleSpeechTranscriptionProvider(_FakeConfigManager(), "latest_long")
    req = httpx.Request("POST", "https://speech.googleapis.com/v1/speech:recognize")
    responses = [
        _FakeResponse(
            status_code=400,
            payload={"error": {"status": "INVALID_ARGUMENT", "message": "model latest_long is not available"}},
            request=req,
        ),
        _FakeResponse(
            status_code=200,
            payload={"results": [{"alternatives": [{"transcript": "Привет мир"}]}]},
            request=req,
        ),
    ]
    monkeypatch.setattr(
        "app.providers.google_speech_transcription_provider.httpx.Client",
        lambda **kwargs: _FakeClient(responses, **kwargs),
    )

    text = provider.transcribe(b"\x00\x00" * 10, sample_rate=16000, language="ru-RU")
    assert text == "Привет мир"


def test_auth_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GoogleSpeechTranscriptionProvider(_FakeConfigManager(), "latest_long")
    req = httpx.Request("POST", "https://speech.googleapis.com/v1/speech:recognize")
    responses = [
        _FakeResponse(
            status_code=401,
            payload={"error": {"status": "UNAUTHENTICATED", "message": "bad key"}},
            request=req,
        )
    ]
    monkeypatch.setattr(
        "app.providers.google_speech_transcription_provider.httpx.Client",
        lambda **kwargs: _FakeClient(responses, **kwargs),
    )

    with pytest.raises(httpx.HTTPStatusError):
        provider.transcribe(b"\x00\x00" * 10, sample_rate=16000, language="ru-RU")
