"""Локальный провайдер транскрипции через Vosk."""

from __future__ import annotations

import io
import json
import sys
import wave
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

def _load_vosk_dependencies() -> tuple[type[Any], type[Any]]:
    """Ленивая загрузка зависимостей Vosk только перед транскрипцией."""
    try:
        from vosk import KaldiRecognizer, Model
        return KaldiRecognizer, Model
    except Exception as exc:
        raise RuntimeError(
            "Для backend 'vosk' требуется пакет 'vosk'. Установите зависимость в активное окружение."
        ) from exc

from app.core.interfaces import TranscriptionProvider

if TYPE_CHECKING:
    from app.core.config_manager import AppConfig


def resolve_vosk_model_path(app_config: AppConfig) -> Path:
    """Определяет путь к каталогу модели Vosk."""
    explicit = str(app_config.vosk_model_path or "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        else:
            path = path.resolve()
    else:
        model_id = str(app_config.whisper_model or "").strip() or "vosk-model-small-ru-0.22"
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).resolve().parents[2]
        path = (base / "assets" / "models" / model_id).resolve()

    if not path.is_dir():
        raise FileNotFoundError(f"Каталог модели Vosk не найден: {path}")
    if not (path / "am").is_dir():
        raise FileNotFoundError(f"Каталог Vosk model/am не найден: {path / 'am'}")
    if not (path / "conf" / "model.conf").is_file():
        raise FileNotFoundError(f"Файл Vosk conf/model.conf не найден: {path / 'conf' / 'model.conf'}")
    return path


class VoskTranscriptionProvider(TranscriptionProvider):
    """Транскрибирует WAV локальной моделью Vosk."""

    def __init__(self, app_config: AppConfig) -> None:
        self._model_path = resolve_vosk_model_path(app_config)
        self._kaldi_recognizer_cls: type[Any] | None = None
        self._model: Any | None = None

    def _ensure_runtime_ready(self) -> None:
        """Лениво загружает Vosk только перед реальной транскрипцией."""
        if self._model is not None and self._kaldi_recognizer_cls is not None:
            return
        kaldi_recognizer_cls, model_cls = _load_vosk_dependencies()
        self._kaldi_recognizer_cls = kaldi_recognizer_cls
        self._model = model_cls(str(self._model_path))

    def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        language: str | None = None,
        *,
        on_partial: Callable[[str], None] | None = None,
    ) -> str:
        del language
        if not audio_bytes:
            return ""
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            if wav_file.getnchannels() != 1:
                raise RuntimeError("Vosk поддерживает только mono WAV")
            if wav_file.getsampwidth() != 2:
                raise RuntimeError("Vosk ожидает WAV с глубиной 16 бит (PCM16)")
            wav_rate = wav_file.getframerate()
            pcm = wav_file.readframes(wav_file.getnframes())
        self._ensure_runtime_ready()
        if self._model is None or self._kaldi_recognizer_cls is None:
            raise RuntimeError("Не удалось инициализировать Vosk runtime")
        recognizer = self._kaldi_recognizer_cls(self._model, float(wav_rate or sample_rate))
        recognizer.SetWords(True)
        recognizer.AcceptWaveform(pcm)
        final_payload = json.loads(recognizer.FinalResult())
        text = str(final_payload.get("text", "") or "").strip()
        if text and on_partial:
            on_partial(text)
        return text
