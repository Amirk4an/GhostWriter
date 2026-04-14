"""Вывод текста через буфер обмена и эмуляцию вставки."""

from __future__ import annotations

import logging
import platform
import subprocess
import time

import pyperclip
from pynput.keyboard import Controller, Key

from app.core.interfaces import OutputAdapter

LOGGER = logging.getLogger(__name__)


class ClipboardOutputController(OutputAdapter):
    """Вставляет текст в активное приложение через clipboard+paste."""

    def __init__(self) -> None:
        self._keyboard = Controller()

    def output_text(self, text: str, paste_target_app: str | None = None) -> None:
        if not text:
            return

        if platform.system() == "Darwin":
            self._copy_to_clipboard_macos(text)
            time.sleep(0.14)
        else:
            pyperclip.copy(text)
            time.sleep(0.1)

        if platform.system() == "Darwin":
            if paste_target_app:
                LOGGER.info("Вставка в приложение с фокусом при записи: %s", paste_target_app)
            ok = self._darwin_activate_and_paste(paste_target_app)
            if not ok:
                LOGGER.warning(
                    "Вставка не удалась (ни pynput, ни запасной osascript). Проверьте Универсальный доступ "
                    "для приложения, из которого запущен Ghost-writer, и автоматизацию для целевых приложений."
                )
            LOGGER.info(
                "Текст в буфере (%d симв.). Если в поле пусто — кликните в поле и Cmd+V.",
                len(text),
            )
            return

        try:
            with self._keyboard.pressed(Key.ctrl):
                self._keyboard.tap("v")
        except Exception as error:  # noqa: BLE001
            LOGGER.warning(
                "Эмуляция Ctrl+V не удалась: %s. Текст остался в буфере — вставьте Ctrl+V вручную.",
                error,
            )

    def _copy_to_clipboard_macos(self, text: str) -> None:
        """Копирует UTF-8 в буфер через pbcopy (надёжнее спецсимволов на macOS)."""
        try:
            subprocess.run(
                ["pbcopy"],
                input=text.encode("utf-8"),
                check=True,
                timeout=10,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            LOGGER.debug("pbcopy не сработал, pyperclip: %s", error)
            pyperclip.copy(text)

    def _run_osascript(self, script: str, argv: list[str]) -> bool:
        cmd = ["/usr/bin/osascript", "-e", script]
        if argv:
            cmd.append("--")
            cmd.extend(argv)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            err = (result.stderr or "").strip()
            out = (result.stdout or "").strip()
            if result.returncode != 0:
                if err or out:
                    LOGGER.warning("osascript stderr: %s", err or out)
                return False
            if err:
                LOGGER.debug("osascript (stderr при коде 0): %s", err)
            return True
        except (OSError, subprocess.TimeoutExpired) as error:
            LOGGER.warning("osascript ошибка: %s", error)
            return False

    def _darwin_activate_and_paste(self, app_name: str | None) -> bool:
        """Активирует цель через AppleScript, затем вставка: key code (System Events), pynput, запасной osascript.

        keystroke внутри tell process в AppleScript даёт код 0 без реальной вставки в Electron (Cursor);
        глобальный key code 9 (Cmd+V) после activate обычно срабатывает.
        """
        if app_name:
            script_activate = (
                "on run argv\n"
                "  set procName to item 1 of argv\n"
                "  tell application procName to activate\n"
                "  delay 0.6\n"
                "end run"
            )
            activated = self._run_osascript(script_activate, [app_name])
            if not activated:
                LOGGER.warning("osascript не смог активировать «%s»", app_name)
        else:
            time.sleep(0.12)

        time.sleep(0.1)
        script_keycode_paste = (
            'tell application "System Events"\n'
            "\tdelay 0.2\n"
            "\tkey code 9 using command down\n"
            "end tell"
        )
        if self._run_osascript(script_keycode_paste, []):
            return True

        try:
            time.sleep(0.05)
            with self._keyboard.pressed(Key.cmd):
                self._keyboard.tap("v")
            return True
        except Exception as error:  # noqa: BLE001
            LOGGER.warning("pynput Cmd+V не удался: %s", error)

        script_global_v = (
            "on run argv\n"
            "  set procName to item 1 of argv\n"
            "  tell application procName to activate\n"
            "  delay 0.7\n"
            '  tell application "System Events" to keystroke "v" using command down\n'
            "end run"
        )
        if app_name:
            return self._run_osascript(script_global_v, [app_name])
        script_se = (
            'tell application "System Events"\n'
            "\tdelay 0.12\n"
            '\tkeystroke "v" using command down\n'
            "end tell"
        )
        return self._run_osascript(script_se, [])
