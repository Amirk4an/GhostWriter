"""System tray и окно настроек приложения."""

from __future__ import annotations

import threading
from typing import Callable

import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw
from pystray import Menu, MenuItem

from app.core.config_manager import ConfigManager


def _status_code_to_ru(code: str) -> str:
    """Переводит внутренний код статуса в подпись для меню трея."""
    if code == "Recording":
        return "Запись"
    if code == "Processing":
        return "Обработка"
    if code == "Error":
        return "Ошибка"
    if code == "Idle":
        return "Ожидание"
    return code


class TrayApplication:
    """Управляет иконкой в трее и окном настроек."""

    def __init__(
        self,
        config_manager: ConfigManager,
        status_provider: Callable[[], str],
        on_reload_config: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._config_manager = config_manager
        self._status_provider = status_provider
        self._on_reload_config = on_reload_config
        self._on_quit = on_quit
        self._icon: pystray.Icon | None = None

    def run(self) -> None:
        config = self._config_manager.config
        image = self._build_icon(config.primary_color)
        menu = Menu(
            MenuItem(
                lambda _: f"Статус: {_status_code_to_ru(self._status_provider())}",
                None,
                enabled=False,
            ),
            MenuItem("Настройки", self._open_settings_window),
            MenuItem("Перезагрузить конфиг", self._reload_config),
            MenuItem("Выход", self._quit),
        )
        self._icon = pystray.Icon(name=config.app_name, icon=image, title=config.app_name, menu=menu)
        self._icon.run()

    def _reload_config(self, icon: pystray.Icon, item: MenuItem) -> None:
        del icon, item
        self._on_reload_config()

    def _quit(self, icon: pystray.Icon, item: MenuItem) -> None:
        del item
        self._on_quit()
        icon.stop()

    def _open_settings_window(self, icon: pystray.Icon, item: MenuItem) -> None:
        del icon, item
        thread = threading.Thread(target=self._settings_window_loop, daemon=True)
        thread.start()

    def _settings_window_loop(self) -> None:
        config = self._config_manager.config
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        root = ctk.CTk()
        root.title(config.app_name)
        root.geometry("520x320")

        title = ctk.CTkLabel(root, text=f"{config.app_name} — настройки", font=("Arial", 18, "bold"))
        title.pack(pady=10)

        cmd_hk = getattr(config, "command_mode_hotkey", "") or "—"
        pill = getattr(config, "floating_pill_enabled", True)
        config_text = (
            f"Горячая клавиша: {config.hotkey}\n"
            f"Режим команд (hotkey): {cmd_hk}\n"
            f"Плавающий индикатор: {pill}\n"
            f"Whisper backend: {config.whisper_backend}\n"
            f"Модель Whisper: {config.whisper_model}\n"
            f"Модель LLM: {config.llm_model}\n"
            f"LLM включён: {config.llm_enabled}\n"
            f"Статус: {_status_code_to_ru(self._status_provider())}"
        )
        info = ctk.CTkLabel(root, text=config_text, justify="left")
        info.pack(pady=12)

        reload_button = ctk.CTkButton(root, text="Перезагрузить конфиг", command=self._on_reload_config)
        reload_button.pack(pady=8)

        note = ctk.CTkLabel(
            root,
            text=(
                "Важно: на macOS требуются Accessibility permissions\n"
                "для глобального hotkey и вставки текста."
            ),
            justify="left",
        )
        note.pack(pady=8)

        close_button = ctk.CTkButton(root, text="Закрыть", command=root.destroy)
        close_button.pack(pady=10)
        root.mainloop()

    def _build_icon(self, color: str) -> Image.Image:
        image = Image.new("RGB", (64, 64), color=color)
        draw = ImageDraw.Draw(image)
        draw.rectangle((18, 18, 46, 46), fill="white")
        return image
