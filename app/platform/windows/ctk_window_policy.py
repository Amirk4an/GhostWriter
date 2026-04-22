"""Скрытие окна CTk из панели задач и поднятие на передний план (Windows)."""

from __future__ import annotations

import logging
import sys
from typing import Any

LOGGER = logging.getLogger(__name__)

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020


def _user32() -> Any:
    import ctypes

    return ctypes.windll.user32


def apply_dashboard_window_policy(root: Any) -> None:
    """
    Убирает кнопку окна из панели задач (аналог LSUIElement): ``WS_EX_TOOLWINDOW``.

    Вызывать после ``geometry`` / первого ``update_idletasks``, когда HWND уже валиден.
    """
    if sys.platform != "win32":
        return
    try:
        root.update_idletasks()
        hwnd = int(root.winfo_id())
    except Exception:
        LOGGER.debug("apply_dashboard_window_policy: нет HWND", exc_info=True)
        return

    user32 = _user32()
    try:
        get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        style = int(get_long(hwnd, GWL_EXSTYLE))
        new_style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        if new_style != style:
            set_long(hwnd, GWL_EXSTYLE, new_style)
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags)
    except OSError as err:
        LOGGER.debug("apply_dashboard_window_policy: %s", err)


def raise_dashboard_to_front_win32(root: Any) -> None:
    """Активация окна дашборда на Windows (после ``WS_EX_TOOLWINDOW``)."""
    from app.platform.windows.focus import raise_ctk_root_to_front

    raise_ctk_root_to_front(root)
