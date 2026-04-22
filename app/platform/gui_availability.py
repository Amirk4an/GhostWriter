"""
Проверки, можно ли безопасно поднимать окна Tk / CustomTkinter.

На macOS процессы с ролью **Background** (launchd без Aqua, часть cron-задач) не имеют
доступа к оконному серверу: ``TkpInit`` часто завершается ``Tcl_Panic``. Системный
Python из **Command Line Tools** (3.9 + Tcl/Tk 8.5) на новых версиях macOS также нестабилен.
"""

from __future__ import annotations

import logging
import os
import sys

LOGGER = logging.getLogger(__name__)

# Явный запрет GUI (cron, launchd без сессии пользователя, CI).
_ENV_HEADLESS = "GHOSTWRITER_HEADLESS"


def skip_tkinter_gui() -> bool:
    """
    Возвращает True, если не следует вызывать ``tkinter`` / CustomTkinter (окна).

    Установите переменную окружения ``GHOSTWRITER_HEADLESS=1`` (или ``true`` / ``yes``)
    для фоновых сценариев без графической сессии.

    Returns:
        ``True``, если GUI нужно отключить.
    """
    raw = (os.environ.get(_ENV_HEADLESS) or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def log_apple_clt_python_warning() -> None:
    """
    Пишет в лог предупреждение, если интерпретатор — из Xcode CLT (слабый Tcl/Tk).

    Рекомендуется Python из Homebrew или python.org с актуальным Tcl/Tk.
    """
    exe = sys.executable or ""
    if "/Library/Developer/CommandLineTools/" in exe.replace("\\", "/"):
        LOGGER.warning(
            "Обнаружен системный/CLT Python (%s). На Apple Silicon + новых macOS для "
            "CustomTkinter надёжнее Homebrew Python (``brew install python@3.12``) и venv.",
            exe,
        )
