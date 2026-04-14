"""Определение активного приложения на macOS (для вставки текста не в терминал)."""

from __future__ import annotations

import logging
import platform
import subprocess

LOGGER = logging.getLogger(__name__)


def get_macos_frontmost_app_name() -> str | None:
    """Возвращает имя процесса/приложения на переднем плане (как в «tell application …»)."""
    if platform.system() != "Darwin":
        return None
    script = 'tell application "System Events" to return name of first process whose frontmost is true'
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            LOGGER.debug("osascript frontmost: %s", (result.stderr or "").strip())
            return None
        name = (result.stdout or "").strip()
        return name or None
    except (OSError, subprocess.TimeoutExpired) as error:
        LOGGER.debug("Не удалось получить frontmost app: %s", error)
        return None
