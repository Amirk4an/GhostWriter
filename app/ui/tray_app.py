"""System tray и окно настроек приложения."""

from __future__ import annotations

import logging
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw
from pystray import Menu, MenuItem

from app.core.config_manager import ConfigManager

LOGGER = logging.getLogger(__name__)


def _tray_status_caption(code: str) -> str:
    """Текст статуса для меню трея (английские подписи по ТЗ)."""
    if code == "Recording":
        return "Recording..."
    if code == "Processing":
        return "Processing..."
    if code == "Error":
        return "Error"
    if code == "Idle":
        return "Ready"
    if code and code.strip() and code not in ("Ready",):
        s = code.strip()
        if len(s) > 100:
            return s[:97] + "…"
        return s
    return "Ready"


def _render_mic_menu_bar_template(size: int) -> Image.Image:
    """
    Рисует монохромную иконку микрофона для template-режима панели меню macOS.

    Args:
        size: Сторона кварата в пикселях (например 44 для Retina).

    Returns:
        Изображение RGBA: силуэт чёрным, фон прозрачный.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    black = (0, 0, 0, 255)
    cx = size // 2
    head_rx = max(3, int(round(size * 0.20)))
    head_top = max(2, int(round(size * 0.08)))
    head_bottom = int(round(size * 0.42))
    draw.ellipse((cx - head_rx, head_top, cx + head_rx, head_bottom), fill=black)

    stem_w = max(2, int(round(size * 0.10)))
    stem_top = head_bottom - max(1, size // 22)
    stem_bottom = int(round(size * 0.58))
    draw.rounded_rectangle(
        (cx - stem_w // 2, stem_top, cx + stem_w // 2, stem_bottom),
        radius=max(1, stem_w // 3),
        fill=black,
    )

    base_w = int(round(size * 0.52))
    base_half = base_w // 2
    base_top = stem_bottom - max(1, size // 28)
    base_bottom = size - max(2, int(round(size * 0.10)))
    draw.rounded_rectangle(
        (cx - base_half, base_top, cx + base_half, base_bottom),
        radius=max(3, int(round(size * 0.12))),
        fill=black,
    )
    return img


class TrayApplication:
    """Управляет иконкой в трее и окном настроек."""

    def __init__(
        self,
        config_manager: ConfigManager,
        status_provider: Callable[[], str],
        on_reload_config: Callable[[], None],
        on_quit: Callable[[], None],
        on_open_dashboard: Optional[Callable[[], None]] = None,
    ) -> None:
        self._config_manager = config_manager
        self._status_provider = status_provider
        self._on_reload_config = on_reload_config
        self._on_quit = on_quit
        self._on_open_dashboard = on_open_dashboard
        self._pystray_icon = None
        self._use_rumps = False

    def run(self) -> None:
        if sys.platform == "darwin":
            try:
                import rumps  # noqa: PLC0415

                self._use_rumps = True
                self._run_rumps(rumps)
                return
            except Exception as err:  # noqa: BLE001
                LOGGER.warning(
                    "Не удалось запустить rumps (%s); интерпретатор: %s. Используется pystray.",
                    err,
                    sys.executable,
                )
                self._use_rumps = False
        self._run_pystray()

    def stop(self) -> None:
        """Останавливает цикл трея (сигнал завершения или выход из меню)."""
        if self._use_rumps:
            try:
                import rumps  # noqa: PLC0415

                rumps.quit_application()
            except Exception:
                LOGGER.debug("Остановка rumps", exc_info=True)
            return
        icon = self._pystray_icon
        if icon is None:
            return
        try:
            icon.stop()
        except Exception:
            LOGGER.debug("Остановка pystray Icon", exc_info=True)

    def _run_rumps(self, rumps: object) -> None:
        cfg = self._config_manager.config
        icon_path: Path | None = None
        try:
            safe = "".join(c if c.isalnum() else "_" for c in cfg.app_name)[:40]
            icon_path = Path(tempfile.gettempdir()) / f"{safe}_ghostwriter_tray_mic.png"
            _render_mic_menu_bar_template(44).save(icon_path, format="PNG")
        except OSError as err:
            LOGGER.error("Не удалось подготовить иконку трея: %s", err)
            icon_path = None

        status_provider = self._status_provider
        on_quit = self._on_quit
        settings_runner = self._settings_window_loop
        open_dashboard = self._on_open_dashboard

        class _MenuBarApp(rumps.App):  # type: ignore[misc, name-defined]
            """Нативное меню macOS через rumps."""

            def __init__(self) -> None:
                icon_kw: dict[str, object] = {"quit_button": None}
                if icon_path is not None and icon_path.exists():
                    icon_kw["icon"] = str(icon_path)
                    icon_kw["template"] = True
                super().__init__(cfg.app_name, **icon_kw)
                self._status_item = rumps.MenuItem(_tray_status_caption(status_provider()), callback=None)
                menu_items: list[object] = [self._status_item, None]
                if open_dashboard is not None:
                    menu_items.append(rumps.MenuItem("Dashboard", callback=self._on_dashboard))
                menu_items.extend(
                    [
                        rumps.MenuItem("Preferences", callback=self._on_preferences),
                        rumps.MenuItem("Quit", callback=self._on_quit_menu),
                    ]
                )
                self.menu = menu_items

            @rumps.timer(0.35)
            def _sync_status(self, _sender: object) -> None:
                self._status_item.title = _tray_status_caption(status_provider())

            def _on_dashboard(self, _sender: object) -> None:
                if open_dashboard is not None:
                    open_dashboard()

            def _on_preferences(self, _sender: object) -> None:
                threading.Thread(target=settings_runner, daemon=True).start()

            def _on_quit_menu(self, _sender: object) -> None:
                on_quit()
                rumps.quit_application()

        app = _MenuBarApp()
        app.run()

    def _run_pystray(self) -> None:
        import pystray  # noqa: PLC0415

        config = self._config_manager.config
        image = _render_mic_menu_bar_template(64).convert("RGBA")

        # pystray на Darwin вызывает колбэк заголовка как f(menu_item) — см. pystray._base.MenuItem.text.
        menu_parts: list[object] = [
            MenuItem(
                lambda *_args: _tray_status_caption(self._status_provider()),
                None,
                enabled=False,
            ),
            Menu.SEPARATOR,
        ]
        if self._on_open_dashboard is not None:
            menu_parts.append(MenuItem("Dashboard", self._open_dashboard_pystray))
        menu_parts.extend(
            [
                MenuItem("Preferences", self._open_settings_pystray),
                MenuItem("Quit", self._quit_pystray),
            ]
        )
        menu = Menu(*menu_parts)
        self._pystray_icon = pystray.Icon(
            name=config.app_name,
            icon=image,
            title=config.app_name,
            menu=menu,
        )
        self._pystray_icon.run()

    def _open_settings_pystray(self, icon: object, item: object) -> None:
        del icon, item
        threading.Thread(target=self._settings_window_loop, daemon=True).start()

    def _open_dashboard_pystray(self, icon: object, item: object) -> None:
        del icon, item
        if self._on_open_dashboard is not None:
            self._on_open_dashboard()

    def _quit_pystray(self, icon: object, item: object) -> None:
        del item
        self._on_quit()
        if hasattr(icon, "stop"):
            icon.stop()

    def _settings_window_loop(self) -> None:
        """Окно настроек (CustomTkinter, тёмная тема macOS)."""
        import customtkinter as ctk

        from app.ui.ctk_macos_theme import apply_ctk_macos_dark_theme, preferred_ui_font

        config = self._config_manager.config

        root = ctk.CTk()
        root.title("Preferences")
        root.geometry("560x400")
        root.configure(fg_color=("#1C1C1E", "#1C1C1E"))
        apply_ctk_macos_dark_theme()

        title_font = preferred_ui_font(17, "bold", master=root)
        body_font = preferred_ui_font(12, master=root)
        small_font = preferred_ui_font(11, master=root)

        pad = 20
        outer = ctk.CTkFrame(
            root,
            fg_color=("#2C2C2E", "#2C2C2E"),
            corner_radius=14,
            border_width=1,
            border_color=("#48484A", "#48484A"),
        )
        outer.pack(fill="both", expand=True, padx=pad, pady=pad)

        title = ctk.CTkLabel(
            outer,
            text=f"{config.app_name}",
            font=title_font,
            text_color=("#F2F2F7", "#F2F2F7"),
        )
        title.pack(anchor="w", padx=18, pady=(18, 4))

        subtitle = ctk.CTkLabel(
            outer,
            text="Preferences",
            font=small_font,
            text_color=("#8E8E93", "#8E8E93"),
        )
        subtitle.pack(anchor="w", padx=18, pady=(0, 12))

        cmd_hk = getattr(config, "command_mode_hotkey", "") or "—"
        pill = getattr(config, "floating_pill_enabled", True)
        config_text = (
            f"Hotkey: {config.hotkey}\n"
            f"Command mode hotkey: {cmd_hk}\n"
            f"Floating pill: {pill}\n"
            f"Whisper backend: {config.whisper_backend}\n"
            f"Whisper model: {config.whisper_model}\n"
            f"LLM model: {config.llm_model}\n"
            f"LLM enabled: {config.llm_enabled}\n"
            f"Status: {_tray_status_caption(self._status_provider())}"
        )
        info_frame = ctk.CTkFrame(outer, fg_color="transparent")
        info_frame.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        info = ctk.CTkLabel(
            info_frame,
            text=config_text,
            font=body_font,
            justify="left",
            text_color=("#E5E5EA", "#E5E5EA"),
        )
        info.pack(anchor="nw", padx=4, pady=4)

        btn_row = ctk.CTkFrame(outer, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 16))

        reload_button = ctk.CTkButton(
            btn_row,
            text="Reload configuration",
            font=body_font,
            height=34,
            corner_radius=10,
            fg_color=("#3A3A3C", "#3A3A3C"),
            hover_color=("#48484A", "#48484A"),
            command=self._on_reload_config,
        )
        reload_button.pack(side="left", padx=(4, 8), pady=4)

        close_button = ctk.CTkButton(
            btn_row,
            text="Close",
            font=body_font,
            height=34,
            corner_radius=10,
            command=root.destroy,
        )
        close_button.pack(side="left", pady=4)

        note = ctk.CTkLabel(
            outer,
            text=(
                "На macOS нужны права Accessibility для глобального hotkey и вставки текста."
            ),
            font=small_font,
            justify="left",
            text_color=("#AEAEB2", "#AEAEB2"),
        )
        note.pack(anchor="w", padx=18, pady=(0, 16))

        root.mainloop()
