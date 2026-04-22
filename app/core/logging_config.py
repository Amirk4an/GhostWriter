"""Конфигурация логирования приложения."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Подкаталог в ~/Library/Logs/ для логов собранного .app (имя бандла в PyInstaller — GhostWriter).
_FROZEN_LOG_SUBDIR = "GhostWriter"


def setup_logging() -> None:
    """
    Настраивает логирование: stderr и при запуске из PyInstaller — файл в ~/Library/Logs/.

    В windowed .app вывод в консоль недоступен; файл позволяет смотреть ошибки через
    ``tail -f ~/Library/Logs/GhostWriter/app.log``.
    """
    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    formatter = logging.Formatter(log_format)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    if getattr(sys, "frozen", False):
        log_dir = Path.home() / "Library" / "Logs" / _FROZEN_LOG_SUBDIR
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "app.log"
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except OSError as err:
            # Не блокируем старт приложения из-за логов.
            print(f"[ghostwriter] Не удалось создать файловый лог: {err}", file=sys.stderr)

    for handler in handlers:
        handler.setFormatter(formatter)

    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
