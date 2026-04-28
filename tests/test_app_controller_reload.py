"""Перезагрузка конфига и смена провайдеров в AppController."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.app_controller import AppController
from app.core.config_manager import ConfigManager
from app.core.interfaces import LLMProvider, OutputAdapter, TranscriptionProvider
from app.core.llm_processor import LLMProcessor


class _DummyAudio:
    def start_recording(self) -> None:
        return

    def stop_recording(self) -> bytes:
        return b"fake"


class _MarkingSTT(TranscriptionProvider):
    def __init__(self, tag: str) -> None:
        self.tag = tag

    def transcribe(self, audio_bytes: bytes, sample_rate: int, language: str | None = None, *, on_partial=None):
        del audio_bytes, sample_rate, language, on_partial
        return f"stt:{self.tag}"


class _MarkingLLM(LLMProvider):
    def __init__(self, tag: str) -> None:
        self.tag = tag

    def refine_text(self, raw_text: str, system_prompt: str) -> str:
        del system_prompt
        return f"llm:{self.tag}:{raw_text}"

    def refine_journal_json(self, raw_text: str, system_prompt: str) -> dict:
        del system_prompt
        return {"title": "t", "tags": [], "advice": "", "refined_text": raw_text}


class _NullOut(OutputAdapter):
    def output_text(self, text: str, paste_target_app: str | None = None) -> None:
        del text, paste_target_app


@pytest.fixture()
def ctrl_and_path(tmp_path: Path) -> tuple[AppController, Path]:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "app_name": "T",
                "primary_color": "#000",
                "hotkey": "f8",
                "system_prompt": "s",
                "model_provider": "openai",
                "whisper_backend": "openai",
                "whisper_model": "whisper-1",
                "local_whisper_model": "small",
                "llm_model": "gpt-4o-mini",
                "llm_enabled": True,
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024,
                "max_parallel_jobs": 1,
                "language": "ru",
                "hands_free_enabled": False,
            }
        ),
        encoding="utf-8",
    )
    cm = ConfigManager(cfg_path)
    stt = _MarkingSTT("a")
    llm = LLMProcessor(provider=_MarkingLLM("a"), enabled=True, model_provider="openai")
    ctrl = AppController(
        config_manager=cm,
        audio_engine=_DummyAudio(),
        transcription_provider=stt,
        llm_processor=llm,
        output_adapter=_NullOut(),
    )
    return ctrl, cfg_path


def test_reload_config_replaces_providers(monkeypatch: pytest.MonkeyPatch, ctrl_and_path: tuple) -> None:
    ctrl, cfg_path = ctrl_and_path
    created: list[str] = []

    class _FakeFactory:
        def __init__(self, config_manager: ConfigManager) -> None:
            del config_manager

        def create_transcription_provider(self, config):
            created.append(f"stt:{config.whisper_backend}")
            return _MarkingSTT(config.whisper_backend)

        def create_llm_provider(self, config):
            created.append(f"llm:{config.model_provider}")
            return _MarkingLLM(config.model_provider)

    monkeypatch.setattr("app.core.provider_factory.ProviderFactory", _FakeFactory)

    cfg_path.write_text(
        json.dumps(
            {
                "app_name": "T",
                "primary_color": "#000",
                "hotkey": "f8",
                "system_prompt": "s",
                "model_provider": "groq",
                "whisper_backend": "deepgram",
                "whisper_model": "nova-2",
                "local_whisper_model": "small",
                "llm_model": "llama-3.1-8b-instant",
                "llm_enabled": True,
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024,
                "max_parallel_jobs": 1,
                "language": "ru",
                "hands_free_enabled": False,
            }
        ),
        encoding="utf-8",
    )

    ctrl.reload_config()
    assert "stt:deepgram" in created
    assert "llm:groq" in created
    assert getattr(ctrl._transcription_provider, "tag") == "deepgram"
    assert getattr(ctrl._llm_processor._provider, "tag") == "groq"
