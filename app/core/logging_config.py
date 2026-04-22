"""Конфигурация логирования приложения."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def _frozen_log_file() -> Path:
    """Путь к файлу лога для собранного приложения (macOS / Windows / прочее)."""
    from app.platform.paths import default_app_support_dir

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "GhostWriter" / "app.log"
    return default_app_support_dir() / "app.log"


def setup_logging() -> None:
    """
    Настраивает логирование: stderr и при запуске из PyInstaller — файл на диске.

    В windowed-сборке вывод в консоль недоступен; файл лежит рядом с пользовательскими
    данными приложения (см. ``app.platform.paths``) или в ``~/Library/Logs/GhostWriter/`` на macOS.
    """
    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    formatter = logging.Formatter(log_format)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    if getattr(sys, "frozen", False):
        log_file = _frozen_log_file()
        log_dir = log_file.parent
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except OSError as err:
            # Не блокируем старт приложения из-за логов.
            print(f"[ghostwriter] Не удалось создать файловый лог: {err}", file=sys.stderr)

    for handler in handlers:
        handler.setFormatter(formatter)

    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
