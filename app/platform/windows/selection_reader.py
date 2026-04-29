"""Чтение выделенного текста на Windows через Ctrl+C с безопасным восстановлением буфера."""

from __future__ import annotations

import logging
import platform
import time

import pyperclip
from pynput.keyboard import Controller, Key

LOGGER = logging.getLogger(__name__)


def _clear_clipboard_safe() -> None:
    """Пытается очистить буфер обмена; ошибки только логируются."""
    try:
        pyperclip.copy("")
    except pyperclip.PyperclipException:
        LOGGER.warning("Не удалось очистить буфер обмена после command mode на Windows")


def get_focused_selected_text_windows() -> str | None:
    """Возвращает выделенный текст в текущем фокусе на Windows.

    Алгоритм:
    1) читаем текстовый бэкап буфера (если возможно),
    2) отправляем Ctrl+C,
    3) читаем текст из буфера как выделение,
    4) восстанавливаем исходный буфер; если бэкап недоступен — очищаем буфер.
    """
    if platform.system() != "Windows":
        return None

    keyboard = Controller()
    backup_text: str | None = None
    has_text_backup = False

    try:
        backup_text = pyperclip.paste()
        has_text_backup = True
    except pyperclip.PyperclipException:
        LOGGER.info("Буфер до Ctrl+C не текстовый или недоступен; после чтения будет очищен")

    try:
        with keyboard.pressed(Key.ctrl):
            keyboard.tap("c")
    except Exception:  # noqa: BLE001
        LOGGER.exception("Не удалось отправить Ctrl+C для чтения выделения на Windows")
        return None

    # Даём приложению время обновить буфер после Ctrl+C.
    time.sleep(0.12)

    selected_text: str | None = None
    try:
        selected_text = pyperclip.paste()
    except pyperclip.PyperclipException:
        LOGGER.warning("Не удалось прочитать выделение из буфера обмена на Windows")
    finally:
        if has_text_backup:
            try:
                pyperclip.copy(backup_text or "")
            except pyperclip.PyperclipException:
                LOGGER.warning("Не удалось восстановить исходный буфер обмена; очищаем буфер")
                _clear_clipboard_safe()
        else:
            _clear_clipboard_safe()

    text = (selected_text or "").strip()
    return text or None
