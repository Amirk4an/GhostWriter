"""Захват уровня с микрофона: превью в дашборде и (опционально) поток для основного процесса."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd

LOGGER = logging.getLogger(__name__)


def _resolve_dashboard_input_params(
    device: int | None,
    sample_rate: float | None,
) -> tuple[Any, int]:
    """
    Возвращает аргумент ``device`` для ``InputStream`` и частоту дискретизации.

    Args:
        device: Индекс PortAudio или ``None`` (вход по умолчанию).
        sample_rate: Явная частота или ``None`` — взять ``default_samplerate`` устройства.
    """
    if sample_rate is not None:
        sr = int(max(8000, min(int(sample_rate), 96000)))
        return device, sr

    try:
        if device is None:
            di = sd.default.device[0]
            if di is None:
                info = sd.query_devices(kind="input")
            else:
                info = sd.query_devices(int(di), "input")
            raw_sr = float(info.get("default_samplerate") or 48000.0)
            sr = int(max(8000, min(int(raw_sr), 96000)))
            return None, sr
        info = sd.query_devices(int(device), "input")
    except (OSError, sd.PortAudioError, ValueError) as err:
        raise RuntimeError(f"Не удалось запросить устройство ввода: {err}") from err

    raw_sr = float(info.get("default_samplerate") or 48000.0)
    sr = int(max(8000, min(int(raw_sr), 96000)))
    return int(device), sr


class DashboardMicMeter:
    """
    Лёгкий индикатор уровня для процесса дашборда: отдельный ``InputStream``, RMS → 0…1.

    Не используется во время основной диктовки; macOS допускает параллельный захват
    с тем же микрофоном из другого процесса.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._current_level = 0.0
        self._last_error: str | None = None

    def get_level(self) -> float:
        """Возвращает последний нормализованный уровень (0.0–1.0) для UI."""
        with self._lock:
            return float(self._current_level)

    def get_last_error(self) -> str | None:
        """Текст последней ошибки запуска потока или ``None``."""
        with self._lock:
            return self._last_error

    def start_metering(self, device: int | None = None, *, sample_rate: float | None = None) -> None:
        """
        Запускает фоновый входной поток PortAudio.

        Args:
            device: Индекс устройства ввода или ``None`` (системный вход по умолчанию).
            sample_rate: Частота дискретизации или ``None`` — по умолчанию устройства.
        """
        self.stop_metering()
        with self._lock:
            self._last_error = None
        try:
            dev_arg, sr = _resolve_dashboard_input_params(device, sample_rate)
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("MicMeter (дашборд): не удалось определить параметры потока: %s", err)
            with self._lock:
                self._last_error = str(err)[:220]
                self._current_level = 0.0
            return

        try:
            stream = sd.InputStream(
                device=dev_arg,
                channels=1,
                samplerate=sr,
                blocksize=1024,
                dtype="float32",
                callback=self._audio_callback,
            )
            stream.start()
            with self._lock:
                self._stream = stream
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("MicMeter (дашборд): не удалось открыть вход: %s", err)
            with self._lock:
                self._last_error = str(err)[:220]
                self._current_level = 0.0
            return

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        _time: Any,
        status: sd.CallbackFlags,
    ) -> None:
        del frames, _time
        if status:
            LOGGER.debug("MicMeter (дашборд) PortAudio: %s", status)
        mono = indata[:, 0] if indata.ndim > 1 else indata.ravel()
        if mono.size == 0:
            rms = 0.0
        else:
            rms = float(np.sqrt(np.mean(np.square(mono), dtype=np.float64)))
        if rms > 1e-10:
            db = 20.0 * float(np.log10(rms))
            level = (db + 50.0) / 50.0
        else:
            level = 0.0
        level = max(0.0, min(1.0, level))
        with self._lock:
            self._current_level = level

    def stop_metering(self) -> None:
        """Останавливает поток и сбрасывает уровень."""
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                LOGGER.debug("MicMeter (дашборд): остановка потока", exc_info=True)
        with self._lock:
            self._current_level = 0.0


class MicMeterController:
    """Открывает отдельный входной поток и шлёт в UI ``mic_meter_update`` (NDJSON).

    Не используется во время основной диктовки (см. ``peek_resolved_input_device``).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._stream: sd.InputStream | None = None
        self._last_peak = 0.0

    def stop(self) -> None:
        """Останавливает поток превью и освобождает PortAudio."""
        self._stop.set()
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                LOGGER.debug("Остановка mic meter stream", exc_info=True)
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)

    def start(
        self,
        *,
        audio_engine: Any,
        channels: int,
        chunk_size: int,
        push_json: Callable[[dict[str, object]], None],
    ) -> None:
        """Запускает фоновый поток измерения уровня."""
        self.stop()
        self._stop.clear()
        try:
            device_id, native_sr = audio_engine.peek_resolved_input_device()
        except RuntimeError as err:
            push_json({"type": "mic_meter_update", "ok": False, "error": str(err), "peak": 0.0})
            return
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("mic_meter_start")
            push_json({"type": "mic_meter_update", "ok": False, "error": str(err), "peak": 0.0})
            return

        def run_worker(dev: int, sr: int) -> None:
            last_emit = 0.0
            smooth = 0.0
            alpha = 0.35
            stream_local: sd.InputStream | None = None

            def on_audio(indata: np.ndarray, frames: int, _ti: dict, status: sd.CallbackFlags) -> None:
                del frames, _ti
                if status:
                    LOGGER.debug("mic meter PortAudio: %s", status)
                if indata.size:
                    self._last_peak = float(np.max(np.abs(indata)))
                else:
                    self._last_peak = 0.0

            try:
                stream_local = sd.InputStream(
                    device=dev,
                    samplerate=sr,
                    channels=channels,
                    blocksize=chunk_size,
                    dtype="float32",
                    callback=on_audio,
                )
                with self._lock:
                    self._stream = stream_local
                stream_local.start()
                while not self._stop.is_set():
                    time.sleep(0.07)
                    now = time.perf_counter()
                    if now - last_emit < 0.055:
                        continue
                    last_emit = now
                    pk = self._last_peak
                    smooth = alpha * pk + (1.0 - alpha) * smooth
                    push_json(
                        {
                            "type": "mic_meter_update",
                            "ok": True,
                            "peak": float(min(1.0, smooth * 5.0)),
                            "raw_peak": float(pk),
                            "device_id": int(dev),
                        }
                    )
            except Exception as err:  # noqa: BLE001
                LOGGER.exception("mic_meter_worker")
                try:
                    push_json(
                        {
                            "type": "mic_meter_update",
                            "ok": False,
                            "error": str(err)[:220],
                            "peak": 0.0,
                        }
                    )
                except Exception:
                    pass
            finally:
                if stream_local is not None:
                    try:
                        stream_local.stop()
                        stream_local.close()
                    except Exception:
                        pass
                with self._lock:
                    if self._stream is stream_local:
                        self._stream = None

        self._thread = threading.Thread(
            target=run_worker,
            args=(device_id, native_sr),
            name="MicMeter",
            daemon=True,
        )
        self._thread.start()
