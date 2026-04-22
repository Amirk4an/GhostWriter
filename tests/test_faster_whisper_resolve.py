"""Тесты разрешения пути к модели faster-whisper."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.core.config_manager import ConfigManager
from app.providers.faster_whisper_provider import resolve_faster_whisper_model_path


def _minimal_raw(**overrides: object) -> dict:
    base = {
        "app_name": "T",
        "primary_color": "#000",
        "hotkey": "f8",
        "system_prompt": "s",
        "model_provider": "openai",
        "whisper_backend": "local",
        "whisper_model": "whisper-1",
        "local_whisper_model": "small",
        "llm_model": "gpt-4o-mini",
        "llm_enabled": False,
        "sample_rate": 16000,
        "channels": 1,
        "chunk_size": 1024,
        "max_parallel_jobs": 1,
    }
    base.update(overrides)
    return base


def test_resolve_cache_returns_model_id(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    p.write_text(json.dumps(_minimal_raw(stt_local={"model_source": "cache"})), encoding="utf-8")
    cfg = ConfigManager(p).config
    assert resolve_faster_whisper_model_path(cfg) == "small"


def test_resolve_custom_path(tmp_path: Path) -> None:
    model_dir = tmp_path / "my_model"
    model_dir.mkdir()
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            _minimal_raw(
                stt_local={
                    "model_source": "custom_path",
                    "custom_model_path": str(model_dir),
                    "device": "cpu",
                    "compute_type": "int8",
                }
            )
        ),
        encoding="utf-8",
    )
    cfg = ConfigManager(p).config
    assert resolve_faster_whisper_model_path(cfg) == str(model_dir.resolve())


def test_resolve_bundle_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    meipass = tmp_path / "bundle_root"
    target = meipass / "assets" / "models" / "small"
    target.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            _minimal_raw(
                local_whisper_model="small",
                stt_local={"model_source": "bundle", "device": "cpu", "compute_type": "int8"},
            )
        ),
        encoding="utf-8",
    )
    cfg = ConfigManager(p).config
    assert resolve_faster_whisper_model_path(cfg) == str(target.resolve())


def test_config_stt_local_invalid_source(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    p.write_text(json.dumps(_minimal_raw(stt_local={"model_source": "invalid"})), encoding="utf-8")
    with pytest.raises(RuntimeError, match="model_source"):
        ConfigManager(p)


def test_config_stt_local_custom_path_missing(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(_minimal_raw(stt_local={"model_source": "custom_path", "custom_model_path": ""})),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="custom_model_path"):
        ConfigManager(p)
