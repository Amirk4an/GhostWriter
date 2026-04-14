"""Модуль захвата и подготовки аудио."""

from __future__ import annotations

import io
import json
import logging
import os
from threading import Lock

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as wav_write
from scipy.signal import resample

LOGGER = logging.getLogger(__name__)


def _agent_debug_log(hypothesis_id: str, location: str, message: str, data: dict[str, object]) -> None:
    """Пишет NDJSON-лог отладки без секретов."""
    try:
        _log_path = "/Users/krasikov/projects/ghostwriter/.cursor/debug-edce00.log"
        os.makedirs(os.path.dirname(_log_path), exist_ok=True)
        payload: dict[str, object] = {
            "sessionId": "edce00",
            "runId": os.environ.get("GHOST_DEBUG_RUN_ID", "run1"),
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(__import__("time").time() * 1000),
        }
        with open(_log_path, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


def resolve_audio_input_device(
    explicit_index: int | None,
    *,
    silence_excluded_ids: set[int] | frozenset[int] | None = None,
) -> int:
    """Возвращает индекс устройства ввода PortAudio или выбрасывает понятную ошибку.

    Args:
        explicit_index: Индекс из config.json или None для авто-выбора.
        silence_excluded_ids: Индексы устройств, которые уже дали нулевой сигнал;
            при авто-выборе они пропускаются (в т.ч. если совпадают с системным default).
    """
    excluded = frozenset(int(x) for x in (silence_excluded_ids or ()))

    if explicit_index is not None:
        idx = int(explicit_index)
        if idx not in excluded:
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
        LOGGER.warning(
            "Микрофон из конфига [%s] ранее дал нулевой сигнал; временно выбираем другой вход",
            idx,
        )

    try:
        default_pair = sd.default.device
        default_in = int(default_pair[0]) if default_pair[0] is not None else -1
    except (OSError, sd.PortAudioError, TypeError, ValueError):
        default_in = -1

    if default_in >= 0 and default_in not in excluded:
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

    input_indices = [i for i, dev in enumerate(devices) if int(dev.get("max_input_channels", 0) or 0) > 0]

    for i in input_indices:
        if i not in excluded:
            LOGGER.warning(
                "Вход по умолчанию недоступен или в списке «тишина»; выбран микрофон: [%s] %s",
                i,
                devices[i].get("name"),
            )
            return int(i)

    if excluded and input_indices and all(i in excluded for i in input_indices):
        LOGGER.warning(
            "Все доступные микрофоны в списке после тишины excluded=%s; сбрасываем фильтр и повторяем выбор",
            sorted(excluded),
        )
        return resolve_audio_input_device(None, silence_excluded_ids=None)

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
        self._runtime_input_device: int | None = input_device
        self._boost_quiet_input = boost_quiet_input
        self._silence_excluded_device_ids: set[int] = set()
        self._active_record_device_id: int | None = None
        self._lock = Lock()
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._is_recording = False
        self._capture_sample_rate: int = sample_rate

    def set_input_device(self, device: int | None) -> None:
        """Задаёт индекс микрофона из конфига (после reload)."""
        self._input_device_explicit = device
        self._runtime_input_device = device
        self._silence_excluded_device_ids.clear()

    def set_boost_quiet_input(self, enabled: bool) -> None:
        self._boost_quiet_input = enabled

    def start_recording(self) -> None:
        """Начинает запись в память."""
        with self._lock:
            if self._is_recording:
                LOGGER.debug("Запись уже активна")
                return

            self._chunks = []
            device_id = resolve_audio_input_device(
                self._runtime_input_device,
                silence_excluded_ids=self._silence_excluded_device_ids,
            )
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
            # region agent log
            _agent_debug_log(
                "H18",
                "audio_engine.py:start_recording",
                "audio capture stream starting",
                {
                    "device_id": int(device_id),
                    "device_name": str(dev_info.get("name", "")),
                    "runtime_input_device": (
                        int(self._runtime_input_device) if self._runtime_input_device is not None else None
                    ),
                    "silence_excluded": sorted(self._silence_excluded_device_ids),
                    "capture_sr": int(native_sr),
                    "target_sr": int(self._sample_rate),
                    "channels": int(self._channels),
                },
            )
            # endregion
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
                self._active_record_device_id = int(device_id)
            except sd.PortAudioError as error:
                self._active_record_device_id = None
                raise RuntimeError(
                    "Не удалось открыть микрофон (PortAudio). Проверьте разрешения и устройство ввода."
                ) from error
            except Exception as error:  # noqa: BLE001
                self._active_record_device_id = None
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
            used_device_id = self._active_record_device_id

            if not self._chunks:
                self._active_record_device_id = None
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
            rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
            # region agent log
            _agent_debug_log(
                "H18",
                "audio_engine.py:stop_recording",
                "audio capture stream stopped",
                {
                    "chunks": len(self._chunks),
                    "samples": int(audio.shape[0]) if hasattr(audio, "shape") else 0,
                    "peak": peak,
                    "rms": rms,
                    "capture_sr": int(capture_sr),
                    "target_sr": int(self._sample_rate),
                },
            )
            # endregion
            if peak >= 1e-6:
                self._silence_excluded_device_ids.clear()
            if peak < 1e-6:
                # Индекс может совпадать с «default» системы — без исключения снова откроется тот же мёртвый вход.
                if used_device_id is not None:
                    self._silence_excluded_device_ids.add(int(used_device_id))
                # region agent log
                _agent_debug_log(
                    "H20",
                    "audio_engine.py:device_fallback",
                    "exclude silent device and prefer another input on next start",
                    {
                        "silent_device_id": int(used_device_id) if used_device_id is not None else None,
                        "from_runtime_device": (
                            int(self._runtime_input_device) if self._runtime_input_device is not None else None
                        ),
                        "from_config_device": (
                            int(self._input_device_explicit) if self._input_device_explicit is not None else None
                        ),
                        "excluded_after": sorted(self._silence_excluded_device_ids),
                    },
                )
                # endregion
                self._runtime_input_device = None
            if peak < 1e-6:
                LOGGER.warning("Запись почти без сигнала (peak=%.2e); проверьте микрофон и уровень ввода", peak)
            pcm_int16 = (audio * 32767).astype(np.int16)

            buffer = io.BytesIO()
            wav_write(buffer, self._sample_rate, pcm_int16)
            self._active_record_device_id = None
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
