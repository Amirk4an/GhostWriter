"""Список аудиовходов PortAudio для выбора в UI."""

from __future__ import annotations

from typing import Any

import sounddevice as sd


def list_audio_input_devices() -> tuple[list[dict[str, Any]], int | None]:
    """Возвращает список микрофонов и индекс входа по умолчанию.

    Returns:
        Кортеж (устройства, default_in): каждый элемент — index, name, is_default.
    """
    try:
        default_pair = sd.default.device
        default_in_raw = default_pair[0] if default_pair[0] is not None else None
        default_in = int(default_in_raw) if default_in_raw is not None else None
    except (OSError, sd.PortAudioError, TypeError, ValueError):
        default_in = None

    devices = sd.query_devices()
    out: list[dict[str, Any]] = []
    for i, dev in enumerate(devices):
        if int(dev.get("max_input_channels", 0) or 0) <= 0:
            continue
        name = str(dev.get("name", "") or "").strip() or f"Устройство {i}"
        out.append(
            {
                "index": int(i),
                "name": name,
                "is_default": default_in is not None and int(i) == int(default_in),
            }
        )
    return out, default_in


def validate_audio_input_index(index: int) -> None:
    """Проверяет, что индекс указывает на устройство с входом."""
    try:
        info = sd.query_devices(int(index))
    except sd.PortAudioError as err:
        raise ValueError(f"Устройство с индексом {index} недоступно.") from err
    if int(info.get("max_input_channels", 0) or 0) <= 0:
        raise ValueError(f"Устройство [{index}] не поддерживает запись.")
