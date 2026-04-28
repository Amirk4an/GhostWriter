"""Фабрика провайдеров: ветки по конфигу."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config_manager import ConfigManager
from app.core.provider_factory import ProviderFactory
from app.providers.deepgram_transcription_provider import DeepgramTranscriptionProvider
from app.providers.groq_whisper_provider import GroqWhisperProvider
from app.providers.litellm_llm_provider import LiteLLMLLMProvider
from app.providers.openai_llm_provider import OpenAILLMProvider
from app.providers.openai_whisper_provider import OpenAIWhisperProvider


def _write_config(tmp_path: Path, extra: dict | None = None) -> Path:
    base = {
        "app_name": "T",
        "primary_color": "#000",
        "hotkey": "f8",
        "system_prompt": "s",
        "model_provider": "openai",
        "whisper_backend": "local",
        "whisper_model": "whisper-1",
        "local_whisper_model": "tiny",
        "llm_model": "gpt-4o-mini",
        "llm_enabled": True,
        "sample_rate": 16000,
        "channels": 1,
        "chunk_size": 1024,
        "max_parallel_jobs": 1,
        "language": "ru",
    }
    if extra:
        base.update(extra)
    p = tmp_path / "config.json"
    p.write_text(json.dumps(base), encoding="utf-8")
    return p


def test_factory_stt_openai_groq_deepgram(tmp_path: Path) -> None:
    cm2 = ConfigManager(_write_config(tmp_path, {"whisper_backend": "openai"}))
    pf2 = ProviderFactory(cm2)
    assert isinstance(pf2.create_transcription_provider(cm2.config), OpenAIWhisperProvider)

    cm3 = ConfigManager(_write_config(tmp_path, {"whisper_backend": "groq", "whisper_model": "whisper-large-v3-turbo"}))
    pf3 = ProviderFactory(cm3)
    assert isinstance(pf3.create_transcription_provider(cm3.config), GroqWhisperProvider)

    cm4 = ConfigManager(_write_config(tmp_path, {"whisper_backend": "deepgram", "whisper_model": "nova-2"}))
    pf4 = ProviderFactory(cm4)
    assert isinstance(pf4.create_transcription_provider(cm4.config), DeepgramTranscriptionProvider)


def test_factory_llm_openai_vs_litellm(tmp_path: Path) -> None:
    cm = ConfigManager(_write_config(tmp_path, {"model_provider": "openai", "llm_enabled": True}))
    pf = ProviderFactory(cm)
    assert isinstance(pf.create_llm_provider(cm.config), OpenAILLMProvider)

    cm2 = ConfigManager(_write_config(tmp_path, {"model_provider": "groq", "llm_model": "llama-3.1-8b-instant"}))
    pf2 = ProviderFactory(cm2)
    assert isinstance(pf2.create_llm_provider(cm2.config), LiteLLMLLMProvider)

    cm3 = ConfigManager(_write_config(tmp_path, {"llm_enabled": False}))
    assert ProviderFactory(cm3).create_llm_provider(cm3.config) is None
