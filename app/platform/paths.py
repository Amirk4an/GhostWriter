"""Единый каталог пользовательских данных приложения (macOS / Windows / прочее)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def default_app_support_dir(*, support_subdir: str = "GhostWriter") -> Path:
    """
    Каталог для ``stats.json``, ``history.db``, ``.env.secrets``, ``single_instance.lock`` и т.п.

    - macOS: ``~/Library/Application Support/<subdir>/``
    - Windows: ``%APPDATA%\\<subdir>\\`` (Roaming)
    - иначе: ``~/.<subdir_lower>/`` (как раньше для Linux и т.д.)

    Каталог не создаётся здесь — вызывающий код делает ``mkdir`` при записи.
    """
    sub = (support_subdir or "GhostWriter").strip() or "GhostWriter"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / sub
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / sub
        return Path.home() / "AppData" / "Roaming" / sub
    safe = sub.lower().replace(" ", "_") or "ghostwriter"
    return Path.home() / f".{safe}"


def single_instance_hint_path(*, support_subdir: str = "GhostWriter") -> Path:
    """Путь для сообщения пользователю при отказе single-instance (файл на Unix, рядом с данными)."""
    return default_app_support_dir(support_subdir=support_subdir) / "single_instance.lock"
