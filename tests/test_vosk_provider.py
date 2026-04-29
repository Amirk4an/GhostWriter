"""Тесты локального провайдера Vosk."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.providers.vosk_transcription_provider import resolve_vosk_model_path


def test_resolve_vosk_model_path_from_explicit_path(tmp_path: Path) -> None:
    model_dir = tmp_path / "vosk-model"
    (model_dir / "am").mkdir(parents=True)
    (model_dir / "conf").mkdir(parents=True)
    (model_dir / "conf" / "model.conf").write_text("dummy", encoding="utf-8")
    cfg = SimpleNamespace(vosk_model_path=str(model_dir), whisper_model="unused")
    resolved = resolve_vosk_model_path(cfg)  # type: ignore[arg-type]
    assert resolved == model_dir


def test_resolve_vosk_model_path_raises_for_missing_dir(tmp_path: Path) -> None:
    cfg = SimpleNamespace(vosk_model_path=str(tmp_path / "missing"), whisper_model="unused")
    try:
        resolve_vosk_model_path(cfg)  # type: ignore[arg-type]
    except FileNotFoundError as exc:
        assert "Каталог модели Vosk не найден" in str(exc)
    else:
        raise AssertionError("Ожидался FileNotFoundError")
