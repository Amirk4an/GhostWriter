"""Тесты менеджера конфигурации."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config_manager import ConfigManager


def test_config_manager_loads_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "app_name": "Test App",
                "primary_color": "#112233",
                "hotkey": "f8",
                "system_prompt": "test",
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

    assert config.app_name == "Test App"
    assert config.hotkey == "f8"
    assert config.sample_rate == 16000


def test_config_language_auto_is_none(tmp_path: Path) -> None:
    base = {
        "app_name": "T",
        "primary_color": "#000",
        "hotkey": "f8",
        "system_prompt": "s",
        "model_provider": "openai",
        "whisper_backend": "openai",
        "whisper_model": "whisper-1",
        "local_whisper_model": "small",
        "llm_model": "gpt-4o-mini",
        "llm_enabled": False,
        "sample_rate": 16000,
        "channels": 1,
        "chunk_size": 1024,
        "max_parallel_jobs": 1,
        "language": "auto",
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(base), encoding="utf-8")
    manager = ConfigManager(config_file)
    assert manager.config.language is None
