"""Кроссплатформенное чтение выделенного текста из активного приложения."""

from __future__ import annotations

import platform

from app.platform.macos_ax_selection import get_focused_selected_text as get_focused_selected_text_macos
from app.platform.windows.selection_reader import get_focused_selected_text_windows


def get_focused_selected_text() -> str | None:
    """Возвращает выделенный текст в фокусе для текущей ОС."""
    os_name = platform.system()
    if os_name == "Darwin":
        return get_focused_selected_text_macos()
    if os_name == "Windows":
        return get_focused_selected_text_windows()
    return None
