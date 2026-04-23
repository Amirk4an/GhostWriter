"""Пайплайн дневника в AppController (без сети)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.core.app_controller import AppController
from app.core.config_manager import ConfigManager
from app.core.interfaces import LLMProvider, OutputAdapter, TranscriptionProvider
from app.core.journal_manager import JournalManager
from app.core.llm_processor import LLMProcessor


class DummyAudio:
    def start_recording(self) -> None:
        return

    def stop_recording(self) -> bytes:
        return b"fake"


class DummySTT(TranscriptionProvider):
    def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        language: str | None = None,
        *,
        on_partial=None,
    ) -> str:
        del audio_bytes, sample_rate, language, on_partial
        return "мысль пользователя"


class JournalJsonProvider(LLMProvider):
    def refine_text(self, raw_text: str, system_prompt: str) -> str:
        del system_prompt
        return raw_text

    def refine_journal_json(self, raw_text: str, system_prompt: str) -> dict:
        del system_prompt
        return {
            "title": "Заг",
            "tags": ["тег1", "тег2"],
            "advice": "Совет",
            "refined_text": raw_text + "!",
        }


class SpyOutput(OutputAdapter):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def output_text(self, text: str, paste_target_app: str | None = None) -> None:
        del paste_target_app
        self.calls.append(text)


def _cfg(tmp_path: Path) -> ConfigManager:
    p = tmp_path / "config.json"
    p.write_text(
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
                "journal_hotkey": "f9",
                "journal_system_prompt": "jp",
            }
        ),
        encoding="utf-8",
    )
    return ConfigManager(p)


def test_journal_job_skips_clipboard_and_writes_db(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    jm = JournalManager(db)
    jm.init_schema()
    out = SpyOutput()
    ctrl = AppController(
        config_manager=_cfg(tmp_path),
        audio_engine=DummyAudio(),
        transcription_provider=DummySTT(),
        llm_processor=LLMProcessor(provider=JournalJsonProvider(), enabled=True),
        output_adapter=out,
        journal_manager=jm,
    )
    ctrl.handle_journal_edge(True, time.perf_counter())
    ctrl.handle_journal_edge(False, time.perf_counter())
    time.sleep(0.15)
    assert out.calls == []
    rows = jm.list_recent(limit=5)
    assert len(rows) == 1
    assert rows[0].title == "Заг"
    assert "мысль" in rows[0].refined_text
