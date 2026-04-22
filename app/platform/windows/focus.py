"""Восстановление переднего окна перед эмуляцией ввода (Windows)."""

from __future__ import annotations

import logging
import sys
from typing import Any

LOGGER = logging.getLogger(__name__)


def _user32() -> Any:
    import ctypes

    return ctypes.windll.user32


def _kernel32() -> Any:
    import ctypes

    return ctypes.windll.kernel32


def allow_any_set_foreground_window() -> None:
    """Разрешает другим процессам вызывать SetForegroundWindow (ограниченно)."""
    if sys.platform != "win32":
        return
    try:
        ASFW_ANY = 0xFFFFFFFF
        _user32().AllowSetForegroundWindow(ASFW_ANY)
    except OSError as err:
        LOGGER.debug("AllowSetForegroundWindow: %s", err)


def capture_foreground_hwnd() -> int | None:
    """HWND окна, которое было на переднем плане (до длительной обработки)."""
    if sys.platform != "win32":
        return None
    try:
        h = _user32().GetForegroundWindow()
        return int(h) if h else None
    except OSError as err:
        LOGGER.debug("GetForegroundWindow: %s", err)
        return None


def restore_foreground_hwnd(hwnd: int | None) -> bool:
    """Возвращает передний план указанному окну (часто — поле ввода целевого приложения)."""
    if sys.platform != "win32" or not hwnd:
        return False
    user32 = _user32()
    kernel32 = _kernel32()
    try:
        if not user32.IsWindow(hwnd):
            return False
    except OSError:
        return False

    allow_any_set_foreground_window()

    try:
        fg = user32.GetForegroundWindow()
        cur_tid = kernel32.GetCurrentThreadId()
        remote_tid = 0
        if fg:
            remote_tid = int(user32.GetWindowThreadProcessId(fg, None))

        attached = False
        if remote_tid and remote_tid != cur_tid:
            attached = bool(user32.AttachThreadInput(cur_tid, remote_tid, True))

        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        ok = bool(user32.SetForegroundWindow(hwnd))

        if attached:
            user32.AttachThreadInput(cur_tid, remote_tid, False)
        return ok
    except OSError as err:
        LOGGER.debug("restore_foreground_hwnd: %s", err)
        return False


def raise_ctk_root_to_front(root: Any) -> None:
    """Поднимает окно CustomTkinter/Tk на передний план (HWND из ``winfo_id``)."""
    if sys.platform != "win32":
        return
    try:
        root.deiconify()
        root.lift()
        root.focus_force()
        root.update_idletasks()
    except Exception:
        LOGGER.debug("raise_ctk_root_to_front: Tk lift/focus", exc_info=True)

    try:
        hwnd = int(root.winfo_id())
    except Exception:
        LOGGER.debug("raise_ctk_root_to_front: нет HWND", exc_info=True)
        return

    allow_any_set_foreground_window()
    restore_foreground_hwnd(hwnd)
