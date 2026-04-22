"""Ограничение одного запущенного экземпляра приложения (macOS / Unix / Windows)."""

from __future__ import annotations

import atexit
import logging
import sys
from typing import BinaryIO

LOGGER = logging.getLogger(__name__)

_lock_fp: BinaryIO | None = None
_win_mutex_handle: object | None = None


def _sanitize_mutex_fragment(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.strip()) or "GhostWriter"


def _try_acquire_windows_mutex(support_subdir: str) -> bool:
    """Именованный mutex в сессии пользователя (``Local\\...``)."""
    global _win_mutex_handle
    if _win_mutex_handle is not None:
        return True
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.SetLastError(0)
    tag = _sanitize_mutex_fragment(support_subdir)
    mutex_name = f"Local\\GhostWriter_{tag}"
    handle = kernel32.CreateMutexW(None, False, mutex_name)
    if not handle:
        LOGGER.warning("CreateMutexW не удался (GetLastError=%s)", kernel32.GetLastError())
        return True
    err = kernel32.GetLastError()
    ERROR_ALREADY_EXISTS = 183
    if err == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _win_mutex_handle = handle

    def _release_win() -> None:
        global _win_mutex_handle
        if _win_mutex_handle is not None:
            try:
                kernel32.CloseHandle(_win_mutex_handle)
            except OSError:
                LOGGER.debug("CloseHandle mutex", exc_info=True)
            _win_mutex_handle = None

    atexit.register(_release_win)
    return True


def try_acquire_single_instance_lock(support_subdir: str = "GhostWriter") -> bool:
    """
    Пытается захватить эксклюзивный lock второго экземпляра.

    - macOS / Unix: неблокирующий ``flock`` на файле в каталоге поддержки приложения.
    - Windows: именованный mutex (см. ``_try_acquire_windows_mutex``).

    Args:
        support_subdir: Подкаталог white-label (как у ``default_app_support_dir``).

    Returns:
        ``True``, если экземпляр может продолжать работу; ``False``, если другой экземпляр уже запущен.
    """
    global _lock_fp
    if _lock_fp is not None or _win_mutex_handle is not None:
        return True

    if sys.platform == "win32":
        return _try_acquire_windows_mutex(support_subdir)

    try:
        import fcntl
    except ImportError:
        return True

    from app.platform.paths import default_app_support_dir

    root = default_app_support_dir(support_subdir=support_subdir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        lock_path = root / "single_instance.lock"
        fp = lock_path.open("a+b")
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fp.close()
            return False
        _lock_fp = fp

        def _release() -> None:
            global _lock_fp
            try:
                if _lock_fp is not None:
                    fcntl.flock(_lock_fp.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                if _lock_fp is not None:
                    _lock_fp.close()
            except OSError:
                pass
            _lock_fp = None

        atexit.register(_release)
        return True
    except OSError as err:
        LOGGER.warning("Single-instance lock недоступен: %s", err)
        return True
