"""
Окно дашборда (CustomTkinter) в отдельном процессе.

Основной хост (``main.py``) запускает дашборд через ``multiprocessing.Process`` с
``target=run_dashboard_process``: дочерний процесс импортирует только этот модуль и
не проходит через точку входа приложения (нет повторного AppController / pill).

Для ручной отладки из консоли по-прежнему можно вызвать
``python3 -m app.ui.dashboard_child_main <путь-к-config.json>``.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from pathlib import Path
from queue import Empty
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from multiprocessing.queues import Queue as MPQueue

LOGGER = logging.getLogger(__name__)

# Команда из родительского процесса: поднять окно дашборда (трей / повторное открытие).
DASHBOARD_FOCUS_RAISE = "raise"


def run_dashboard_process(
    config_path_str: str,
    focus_commands: "MPQueue[Any] | None" = None,
    host_command_queue: "MPQueue[Any] | None" = None,
) -> None:
    """
    Целевая функция ``multiprocessing.Process`` для дашборда: только конфиг, CTk и UI.

    Тяжёлые импорты выполняются внутри функции, чтобы при ``spawn`` не тянуть их
    до фактического старта процесса.

    Args:
        config_path_str: Абсолютный или нормализованный путь к ``config.json``.
        focus_commands: Очередь команд из родительского процесса (например ``raise`` — поднять окно).
        host_command_queue: Очередь в основной процесс (например ``reload_config`` после сохранения настроек).
    """
    from app.core.config_manager import ConfigManager
    from app.core.logging_config import setup_logging

    setup_logging()
    path = (config_path_str or "").strip()
    if not path:
        LOGGER.error("Дашборд: пустой путь к config.json")
        sys.exit(1)

    import customtkinter as ctk

    cfg_path = Path(path).resolve()
    try:
        config_manager = ConfigManager(config_path=cfg_path)
    except Exception:
        LOGGER.exception("Дашборд: не удалось загрузить конфиг %s", cfg_path)
        sys.exit(1)

    from tkinter import TclError

    from app.platform.macos_ctk_dock import bring_app_to_front, hide_dock_icon_for_ctk_root
    from app.ui.ctk_macos_theme import apply_ctk_theme

    root = ctk.CTk()
    apply_ctk_theme(config_manager.config.ui_theme)
    hide_dock_icon_for_ctk_root()
    cfg = config_manager.config
    root.title(f"{cfg.app_name} — Dashboard")
    root.configure(fg_color=("#F5F5F7", "#1C1C1E"))
    root.minsize(900, 600)
    root.geometry("1040x700")

    if sys.platform == "win32":
        from app.platform.windows.ctk_window_policy import apply_dashboard_window_policy

        root.update_idletasks()
        apply_dashboard_window_policy(root)

    def _macos_order_front_app_windows() -> None:
        """Вызывает orderFrontRegardless для видимых окон процесса (в т.ч. окно Tk)."""
        if sys.platform != "darwin" or platform.system() != "Darwin":
            return
        try:
            from AppKit import NSApplication

            app = NSApplication.sharedApplication()
            for w in list(app.windows() or []):
                try:
                    if not w.isVisible():
                        continue
                    w.orderFrontRegardless()
                except Exception:
                    continue
        except ImportError:
            LOGGER.debug("Дашборд: нет AppKit для orderFrontRegardless")
        except Exception:
            LOGGER.debug("Дашборд: orderFrontRegardless", exc_info=True)

    def _raise_dashboard_front() -> None:
        """
        Поднимает окно дашборда без смены NSApplicationActivationPolicy.

        Смена Regular ↔ Accessory на каждом клике ломает Dock (фантомные иконки). Здесь только
        ``activateIgnoringOtherApps`` (через ``bring_app_to_front``), Tk и ``orderFrontRegardless``.
        """
        if sys.platform == "win32":
            from app.platform.windows.ctk_window_policy import raise_dashboard_to_front_win32

            raise_dashboard_to_front_win32(root)
            return

        if platform.system() != "Darwin":
            try:
                root.deiconify()
                root.lift()
                root.focus_force()
            except TclError:
                LOGGER.debug("Дашборд: lift/focus (не macOS)", exc_info=True)
            return

        bring_app_to_front()

        try:
            root.deiconify()
            root.lift()
            root.focus_force()
            root.update_idletasks()
        except TclError:
            LOGGER.debug("Дашборд: Tk deiconify/lift/focus", exc_info=True)

        _macos_order_front_app_windows()

    # Старт окна: без привязки к каждому клику (иначе Dock и WindowServer расходятся с политикой).
    _raise_dashboard_front()
    root.after_idle(_raise_dashboard_front)
    root.after(250, _raise_dashboard_front)

    def _poll_focus_commands() -> None:
        if focus_commands is not None:
            try:
                while True:
                    msg = focus_commands.get_nowait()
                    if msg == DASHBOARD_FOCUS_RAISE:
                        _raise_dashboard_front()
            except Empty:
                pass
            except Exception:
                LOGGER.debug("Дашборд: опрос очереди фокуса", exc_info=True)
        root.after(250, _poll_focus_commands)

    root.after(300, _poll_focus_commands)

    from app.ui.main_dashboard import mount_main_dashboard

    mount_main_dashboard(root, config_manager, host_command_queue=host_command_queue)

    def _on_close() -> None:
        meter = getattr(root, "_gw_mic_meter", None)
        if meter is not None:
            try:
                meter.stop_metering()
            except Exception:
                LOGGER.debug("Дашборд: остановка превью микрофона", exc_info=True)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)
    LOGGER.info("Процесс дашборда запущен (pid=%s)", os.getpid())
    root.mainloop()
    LOGGER.info("Процесс дашборда завершён")


def run_dashboard_app(config_path_str: str) -> None:
    """
    Совместимость с CLI ``dashboard_child_main``: то же поведение, что у процесса.

    Args:
        config_path_str: Путь к ``config.json``.
    """
    run_dashboard_process(config_path_str)
