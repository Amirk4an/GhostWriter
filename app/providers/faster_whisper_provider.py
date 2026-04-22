"""Локальный провайдер транскрипции через Faster-Whisper."""

from __future__ import annotations

import io
import logging
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np
from faster_whisper import WhisperModel
from scipy.io.wavfile import read as wav_read

from app.core.config_manager import AppConfig
from app.core.interfaces import TranscriptionProvider

LOGGER = logging.getLogger(__name__)


def resolve_faster_whisper_model_path(app_config: AppConfig) -> str:
    """
    Определяет аргумент ``model_size_or_path`` для ``WhisperModel`` с учётом PyInstaller.

    Args:
        app_config: Конфигурация приложения (поля ``local_whisper_*``, ``stt_local``).

    Returns:
        Идентификатор модели для HF-кэша либо абсолютный путь к каталогу весов.
    """
    model_id = str(app_config.local_whisper_model or "").strip()
    if not model_id:
        raise RuntimeError("local_whisper_model в конфиге не задан")

    source = app_config.local_whisper_model_source
    if source == "cache":
        return model_id

    if source == "custom_path":
        resolved = Path(app_config.local_whisper_custom_path).expanduser().resolve()
        if not resolved.is_dir():
            raise FileNotFoundError(f"Каталог модели (custom_path) не найден: {resolved}")
        return str(resolved)

    # bundle
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[2]
    bundle_path = (base / "assets" / "models" / model_id).resolve()
    if not bundle_path.is_dir():
        raise FileNotFoundError(
            f"Модель в бандле не найдена: {bundle_path}. "
            f"Положите веса в assets/models/{model_id}/ или задайте stt_local.model_source: cache."
        )
    return str(bundle_path)


class FasterWhisperProvider(TranscriptionProvider):
    """Транскрибирует аудио локальной моделью Faster-Whisper."""

    def __init__(self, app_config: AppConfig) -> None:
        """
        Args:
            app_config: Конфигурация с параметрами ``stt_local`` и ``local_whisper_model``.
        """
        model_path = resolve_faster_whisper_model_path(app_config)
        device = app_config.local_whisper_device
        compute_type = app_config.local_whisper_compute_type
        LOGGER.info(
            "Инициализация WhisperModel: path=%r device=%s compute_type=%s",
            model_path,
            device,
            compute_type,
        )
        self._model = WhisperModel(
            model_path,
            device=device,
            compute_type=compute_type,
        )
        LOGGER.info("WhisperModel загружена в память.")

    def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        language: str | None = None,
        *,
        on_partial: Callable[[str], None] | None = None,
    ) -> str:
        del sample_rate
        if not audio_bytes:
            return ""

        local_sample_rate, pcm = wav_read(io.BytesIO(audio_bytes))
        audio = self._to_float32(pcm)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        if audio.size == 0 or (peak == 0.0 and rms == 0.0):
            return ""

        segments, _info = self._model.transcribe(
            audio=audio,
            language=language,
            vad_filter=True,
        )
        parts: list[str] = []
        for segment in segments:
            chunk = segment.text.strip()
            if chunk:
                parts.append(chunk)
                if on_partial:
                    on_partial(" ".join(parts).strip())
        return " ".join(parts).strip()

    def _to_float32(self, pcm: Any) -> np.ndarray:
        audio = np.asarray(pcm)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if audio.dtype == np.int16:
            return (audio / 32768.0).astype(np.float32)
        return audio.astype(np.float32)
