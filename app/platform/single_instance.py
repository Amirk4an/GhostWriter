"""Ограничение одного запущенного экземпляра приложения (macOS / Unix)."""

from __future__ import annotations

import atexit
import logging
import sys
from pathlib import Path
from typing import BinaryIO

LOGGER = logging.getLogger(__name__)

_lock_fp: BinaryIO | None = None


def try_acquire_single_instance_lock(support_subdir: str = "GhostWriter") -> bool:
    """
    Пытается захватить неблокирующую файловую блокировку в ``~/Library/Application Support``.

    Снижает риск двойного запуска `.app` (два процесса, конфликт загрузки HF и т.п.).

    Args:
        support_subdir: Имя каталога в ``Application Support`` (white-label: задайте своё).

    Returns:
        ``True``, если блокировка получена; ``False``, если другой экземпляр уже держит lock.
    """
    global _lock_fp
    if _lock_fp is not None:
        return True
    if sys.platform == "win32":
        return True
    try:
        import fcntl
    except ImportError:
        return True

    root = Path.home() / "Library" / "Application Support" / support_subdir
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
