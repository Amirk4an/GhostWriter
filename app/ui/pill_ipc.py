"""Константы и форматы межпроцессных команд от pill к основному процессу."""

from __future__ import annotations

from typing import Any

# Действия, которые pill отправляет в ``command_queue`` (multiprocessing.Queue).
ACTION_OPEN_DASHBOARD = "open_dashboard"


def open_dashboard_message() -> dict[str, Any]:
    """Возвращает сообщение для открытия главного дашборда."""
    return {"action": ACTION_OPEN_DASHBOARD}
