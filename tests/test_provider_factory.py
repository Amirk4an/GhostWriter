"""Тесты фабрики провайдеров."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config_manager import ConfigManager
from app.core.provider_factory import ProviderFactory


def test_provider_factory_creates_openai_providers(monkeypatch, tmp_path: Path) -> None:
    pytest.importorskip("openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "app_name": "Test",
                "primary_color": "#000000",
                "hotkey": "f8",
                "system_prompt": "x",
                "model_provider": "openai",
                "whisper_backend": "openai",
                "whisper_model": "whisper-1",
                "local_whisper_model": "small",
                "llm_model": "gpt-4o-mini",
                "llm_enabled": True,
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024,
                "language": "ru",
                "max_parallel_jobs": 1,
            }
        ),
        encoding="utf-8",
    )
    manager = ConfigManager(config_file)
    config = manager.config
    factory = ProviderFactory(manager)

    stt_provider = factory.create_transcription_provider(config)
    llm_provider = factory.create_llm_provider(config)

    assert stt_provider.__class__.__name__ == "OpenAIWhisperProvider"
    assert llm_provider is not None
    assert llm_provider.__class__.__name__ == "OpenAILLMProvider"
