"""Модуль захвата и подготовки аудио."""

from __future__ import annotations

import io
import logging
from threading import Lock

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as wav_write
from scipy.signal import resample

LOGGER = logging.getLogger(__name__)


def resolve_audio_input_device(explicit_index: int | None) -> int:
    """Возвращает индекс устройства ввода PortAudio или выбрасывает понятную ошибку."""
    if explicit_index is not None:
        idx = int(explicit_index)
        try:
            info = sd.query_devices(idx)
        except sd.PortAudioError as error:
            raise RuntimeError(
                f"Микрофон с индексом {idx} недоступен. Проверьте audio_input_device в config.json. "
                "Список устройств: в активированном venv выполните python -c \"import sounddevice as s; print(s.query_devices())\""
            ) from error
        if int(info.get("max_input_channels", 0) or 0) <= 0:
            raise RuntimeError(
                f"Устройство [{idx}] «{info.get('name', '?')}» не поддерживает запись (нет входных каналов)."
            )
        LOGGER.debug("Микрофон из конфига: [%s] %s", idx, info.get("name"))
        return idx

    try:
        default_pair = sd.default.device
        default_in = int(default_pair[0]) if default_pair[0] is not None else -1
    except (OSError, sd.PortAudioError, TypeError, ValueError):
        default_in = -1

    if default_in >= 0:
        try:
            info = sd.query_devices(default_in)
            if int(info.get("max_input_channels", 0) or 0) > 0:
                LOGGER.debug("Микрофон по умолчанию: [%s] %s", default_in, info.get("name"))
                return default_in
        except sd.PortAudioError:
            pass

    try:
        devices = sd.query_devices()
    except sd.PortAudioError as error:
        raise RuntimeError(
            "Не удалось получить список аудиоустройств (PortAudio). "
            "Проверьте разрешение «Микрофон» для Terminal/iTerm/Cursor и перезапустите приложение."
        ) from error

    for i, dev in enumerate(devices):
        if int(dev.get("max_input_channels", 0) or 0) > 0:
            LOGGER.warning(
                "Вход по умолчанию недоступен; выбран первый микрофон: [%s] %s",
                i,
                dev.get("name"),
            )
            return int(i)

    raise RuntimeError(
        "Микрофон не найден. На macOS: «Системные настройки → Конфиденциальность и безопасность → Микрофон» "
        "— включите доступ для терминала/IDE. Также проверьте «Звук → Ввод» и при необходимости задайте "
        "audio_input_device в config.json (индекс из списка устройств sounddevice)."
    )


class AudioEngine:
    """Записывает аудио в память в режиме press-to-talk."""

    def __init__(
        self,
        sample_rate: int,
        channels: int,
        chunk_size: int,
        input_device: int | None = None,
        boost_quiet_input: bool = False,
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_size = chunk_size
        self._input_device_explicit = input_device
        self._boost_quiet_input = boost_quiet_input
        self._lock = Lock()
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._is_recording = False
        self._capture_sample_rate: int = sample_rate

    def set_input_device(self, device: int | None) -> None:
        """Задаёт индекс микрофона из конфига (после reload)."""
        self._input_device_explicit = device

    def set_boost_quiet_input(self, enabled: bool) -> None:
        self._boost_quiet_input = enabled

    def start_recording(self) -> None:
        """Начинает запись в память."""
        with self._lock:
            if self._is_recording:
                LOGGER.debug("Запись уже активна")
                return

            self._chunks = []
            device_id = resolve_audio_input_device(self._input_device_explicit)
            dev_info = sd.query_devices(device_id)
            native_sr = int(float(dev_info.get("default_samplerate") or 0))
            if native_sr <= 0:
                native_sr = self._sample_rate
                LOGGER.warning(
                    "У микрофона не указана default_samplerate, запись с %s Гц из конфига",
                    native_sr,
                )
            else:
                LOGGER.debug(
                    "Запись с частотой устройства %s Гц → ресемплинг в %s Гц для Whisper",
                    native_sr,
                    self._sample_rate,
                )
            self._capture_sample_rate = native_sr
            try:
                self._stream = sd.InputStream(
                    device=device_id,
                    samplerate=native_sr,
                    channels=self._channels,
                    blocksize=self._chunk_size,
                    dtype="float32",
                    callback=self._on_audio_callback,
                )
                self._stream.start()
                self._is_recording = True
            except sd.PortAudioError as error:
                raise RuntimeError(
                    "Не удалось открыть микрофон (PortAudio). Проверьте разрешения и устройство ввода."
                ) from error
            except Exception as error:  # noqa: BLE001
                raise RuntimeError("Не удалось начать запись аудио") from error

    def stop_recording(self) -> bytes:
        """Останавливает запись и возвращает WAV-байты."""
        with self._lock:
            if not self._is_recording:
                LOGGER.debug("Остановка вызвана без активной записи")
                return b""

            assert self._stream is not None
            self._stream.stop()
            self._stream.close()
            self._stream = None
            self._is_recording = False

            if not self._chunks:
                return b""

            audio = np.concatenate(self._chunks, axis=0)
            audio = self.noise_suppression(audio)
            if self._boost_quiet_input and audio.size:
                peak = float(np.max(np.abs(audio)))
                if 0 < peak < 0.08:
                    gain = min(8.0, 0.05 / max(peak, 1e-6))
                    audio = np.clip(audio.astype(np.float32) * gain, -1.0, 1.0)
            capture_sr = self._capture_sample_rate
            if capture_sr != self._sample_rate and audio.shape[0] > 0:
                num_target = max(1, int(round(audio.shape[0] * self._sample_rate / capture_sr)))
                audio = resample(audio, num_target, axis=0).astype(np.float32)
            audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
            audio = np.clip(audio, -1.0, 1.0)
            peak = float(np.max(np.abs(audio))) if audio.size else 0.0
            if peak < 1e-6:
                LOGGER.warning("Запись почти без сигнала (peak=%.2e); проверьте микрофон и уровень ввода", peak)
            pcm_int16 = (audio * 32767).astype(np.int16)

            buffer = io.BytesIO()
            wav_write(buffer, self._sample_rate, pcm_int16)
            return buffer.getvalue()

    def get_audio_stream(self) -> sd.InputStream | None:
        """Возвращает объект текущего аудиопотока."""
        return self._stream

    def noise_suppression(self, audio_data: np.ndarray) -> np.ndarray:
        """Хук для будущего шумоподавления."""
        return audio_data

    def _on_audio_callback(self, indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags) -> None:
        del frames, time_info
        if status:
            LOGGER.warning("Проблема аудиопотока: %s", status)
        self._chunks.append(indata.copy())
