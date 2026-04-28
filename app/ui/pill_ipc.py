"""Константы и форматы межпроцессных команд от pill к основному процессу."""

from __future__ import annotations

from typing import Any

# Действия, которые pill отправляет в ``command_queue`` (multiprocessing.Queue).
ACTION_OPEN_DASHBOARD = "open_dashboard"
# Команда дашборда → основной процесс: перечитать config.json и обновить хоткеи.
ACTION_RELOAD_CONFIG = "reload_config"


def open_dashboard_message() -> dict[str, Any]:
    """Возвращает сообщение для открытия главного дашборда."""
    return {"action": ACTION_OPEN_DASHBOARD}


def reload_config_message() -> dict[str, Any]:
    """Сообщение основному процессу: применить конфиг с диска (после сохранения из дашборда)."""
    return {"action": ACTION_RELOAD_CONFIG}
