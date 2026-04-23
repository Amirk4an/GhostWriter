"""Тесты менеджера конфигурации."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config_manager import ConfigManager


def _minimal_config_dict() -> dict:
    return {
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
        "language": "ru",
    }


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


def test_config_enable_history_defaults_true_and_patches(tmp_path: Path) -> None:
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
        "language": "ru",
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(base), encoding="utf-8")
    manager = ConfigManager(config_file)
    assert manager.config.enable_history is True

    manager.patch_enable_history(False)
    assert manager.config.enable_history is False
    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved.get("enable_history") is False


@pytest.fixture
def secrets_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / ".env.secrets"
    monkeypatch.setattr("app.core.config_manager.default_secrets_env_path", lambda **_k: p)
    return p


def test_set_secret_and_peek(tmp_path: Path, secrets_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(ConfigManager, "_local_dotenv_candidates", lambda self: [])
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(_minimal_config_dict()), encoding="utf-8")
    manager = ConfigManager(config_file)
    assert manager.peek_secret("OPENAI_API_KEY") is None
    manager.set_secret("OPENAI_API_KEY", "sk-from-ui")
    assert manager.peek_secret("OPENAI_API_KEY") == "sk-from-ui"
    assert manager.get_secret("OPENAI_API_KEY") == "sk-from-ui"
    manager.set_secret("OPENAI_API_KEY", "")
    assert manager.peek_secret("OPENAI_API_KEY") is None


def test_journal_hotkey_normalized(tmp_path: Path) -> None:
    base = _minimal_config_dict()
    base["journal_hotkey"] = " Alt + F9 "
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(base), encoding="utf-8")
    manager = ConfigManager(config_file)
    assert manager.config.journal_hotkey == "alt+f9"


def test_secret_user_file_over_env(tmp_path: Path, secrets_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ConfigManager, "_local_dotenv_candidates", lambda self: [])
    secrets_path.write_text("OPENAI_API_KEY=from-user-file\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(_minimal_config_dict()), encoding="utf-8")
    manager = ConfigManager(config_file)
    assert manager.peek_secret("OPENAI_API_KEY") == "from-user-file"

