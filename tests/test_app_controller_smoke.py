"""Smoke-тест пайплайна AppController с mock-объектами."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from app.core.app_controller import AppController
from app.core.config_manager import ConfigManager
from app.core.interfaces import LLMProvider, OutputAdapter, TranscriptionProvider
from app.core.llm_processor import LLMProcessor


class DummyAudioEngine:
    def start_recording(self) -> None:
        return

    def stop_recording(self) -> bytes:
        return b"fake-wav"


class TrackingAudioEngine(DummyAudioEngine):
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    def start_recording(self) -> None:
        self.start_calls += 1

    def stop_recording(self) -> bytes:
        self.stop_calls += 1
        return super().stop_recording()


class DummyTranscriptionProvider(TranscriptionProvider):
    def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        language: str | None = None,
        *,
        on_partial=None,
    ) -> str:
        del audio_bytes, sample_rate, language, on_partial
        return "сырой текст"


class DummyOutputAdapter(OutputAdapter):
    def __init__(self) -> None:
        self.value = ""

    def output_text(self, text: str, paste_target_app: str | None = None) -> None:
        del paste_target_app
        self.value = text


class DummyLLMProvider(LLMProvider):
    def refine_text(self, raw_text: str, system_prompt: str) -> str:
        del system_prompt
        return f"LLM:{raw_text}"

    def refine_journal_json(self, raw_text: str, system_prompt: str) -> dict:
        del raw_text, system_prompt
        return {"title": "", "tags": [], "advice": "", "refined_text": ""}


def _build_config(tmp_path: Path) -> ConfigManager:
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "app_name": "Test App",
                "primary_color": "#112233",
                "hotkey": "f8",
                "system_prompt": "sys",
                "model_provider": "openai",
                "whisper_backend": "openai",
                "whisper_model": "whisper-1",
                "local_whisper_model": "small",
                "llm_model": "gpt-4o-mini",
                "llm_enabled": False,
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024,
                "language": "ru",
                "max_parallel_jobs": 1,
                "hands_free_enabled": False,
            }
        ),
        encoding="utf-8",
    )
    return ConfigManager(config_file)


def test_app_controller_pipeline_smoke(tmp_path: Path) -> None:
    manager = _build_config(tmp_path)
    output = DummyOutputAdapter()
    controller = AppController(
        config_manager=manager,
        audio_engine=DummyAudioEngine(),
        transcription_provider=DummyTranscriptionProvider(),
        llm_processor=LLMProcessor(provider=None, enabled=False),
        output_adapter=output,
    )

    controller.on_hotkey_press()
    controller.on_hotkey_release()
    time.sleep(0.08)

    assert output.value == "сырой текст"


def test_app_controller_command_mode_uses_selection_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = _build_config(tmp_path)
    manager.update_and_save({"llm_enabled": True})
    output = DummyOutputAdapter()
    controller = AppController(
        config_manager=manager,
        audio_engine=DummyAudioEngine(),
        transcription_provider=DummyTranscriptionProvider(),
        llm_processor=LLMProcessor(provider=DummyLLMProvider(), enabled=True),
        output_adapter=output,
    )
    monkeypatch.setattr("app.core.app_controller.get_focused_selected_text", lambda: "выделение")

    controller.on_command_hotkey_press()
    controller.on_command_hotkey_release()
    time.sleep(0.08)

    assert output.value == "LLM:Выделенный текст:\nвыделение\n\nГолосовая команда (распознана):\nсырой текст"


def test_app_controller_command_mode_without_selection_fails_fast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = _build_config(tmp_path)
    manager.update_and_save({"llm_enabled": True})
    output = DummyOutputAdapter()
    audio = TrackingAudioEngine()
    controller = AppController(
        config_manager=manager,
        audio_engine=audio,
        transcription_provider=DummyTranscriptionProvider(),
        llm_processor=LLMProcessor(provider=DummyLLMProvider(), enabled=True),
        output_adapter=output,
    )
    monkeypatch.setattr("app.core.app_controller.get_focused_selected_text", lambda: None)

    controller.on_command_hotkey_press()
    controller.on_command_hotkey_release()
    time.sleep(0.05)

    assert controller.status == "Error"
    assert audio.start_calls == 0
    assert audio.stop_calls == 0
    assert output.value == ""
