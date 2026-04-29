"""Тесты маппинга секретов для провайдеров."""

from __future__ import annotations

from app.core.provider_credentials import (
    ALLOWED_WHISPER_BACKENDS,
    iter_needed_secret_names,
    stt_secret_key_name,
)


def test_stt_secret_mapping_for_gcp() -> None:
    assert stt_secret_key_name("gcp_speech") == "GCP_STT_API_KEY"
    assert stt_secret_key_name("GCP_SPEECH") == "GCP_STT_API_KEY"


def test_allowed_whisper_backends_contains_gcp() -> None:
    assert "gcp_speech" in ALLOWED_WHISPER_BACKENDS
    assert "vosk" in ALLOWED_WHISPER_BACKENDS


def test_stt_secret_mapping_for_yandex() -> None:
    assert stt_secret_key_name("yandex_speech") == "YANDEX_API_KEY"


def test_iter_needed_secret_names_includes_yandex_folder_id() -> None:
    names = iter_needed_secret_names(
        model_provider="openai",
        whisper_backend="yandex_speech",
        llm_enabled=False,
    )
    assert "YANDEX_API_KEY" in names
    assert "YANDEX_FOLDER_ID" in names


def test_stt_secret_mapping_for_vosk_is_not_required() -> None:
    assert stt_secret_key_name("vosk") is None
