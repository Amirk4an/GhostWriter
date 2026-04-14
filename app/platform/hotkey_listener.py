"""Глобальный слушатель хоткеев: комбинации, dictation edge, command mode."""

from __future__ import annotations

import logging
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from collections.abc import Callable
from typing import TYPE_CHECKING

from pynput import keyboard
from pynput.keyboard import Key, KeyCode, Listener

from app.core.hotkey_spec import MOD_FAMILIES, HotkeySpec, parse_hotkey_spec, token_to_pynput_key
from app.core.interfaces import HotkeyListener

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger(__name__)


def _agent_debug_log(hypothesis_id: str, location: str, message: str, data: dict[str, object]) -> None:
    """Пишет NDJSON-лог отладки без секретов."""
    try:
        _log_path = "/Users/krasikov/projects/ghostwriter/.cursor/debug-edce00.log"
        Path(_log_path).parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {
            "sessionId": "edce00",
            "runId": os.environ.get("GHOST_DEBUG_RUN_ID", "run1"),
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(_log_path, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _key_matches_token(key: object, token: str) -> bool:
    target = token_to_pynput_key(token)
    if isinstance(target, str):
        if isinstance(key, KeyCode):
            ch = (key.char or "").lower()
            return len(target) == 1 and ch == target.lower()
        return False
    return key == target


def _key_in_mod_family(key: object, mod_name: str) -> bool:
    fam = MOD_FAMILIES.get(mod_name)
    if not fam:
        return False
    return key in fam


def _macos_ax_is_trusted(prompt_user: bool = False) -> bool | None:
    """Проверяет права Accessibility; при prompt_user=True просит систему показать диалог доступа."""
    try:
        if os.name != "posix":
            return None
        from ApplicationServices import (  # type: ignore
            AXIsProcessTrusted,
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )

        if prompt_user:
            return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}))
        return bool(AXIsProcessTrusted())
    except Exception:
        return None


class PynputHotkeyListener(HotkeyListener):
    """Слушатель dictation (press/hold + edge) и опционально command hotkey."""

    def __init__(self, dictation_hotkey: str, command_hotkey: str = "") -> None:
        self._dict_spec = parse_hotkey_spec(dictation_hotkey)
        self._cmd_spec: HotkeySpec | None
        try:
            self._cmd_spec = parse_hotkey_spec(command_hotkey) if command_hotkey.strip() else None
        except ValueError:
            LOGGER.warning("Некорректный command_mode_hotkey, режим команд отключён")
            self._cmd_spec = None

        self._listener: Listener | None = None
        self._pressed: set[object] = set()
        self._dictate_trigger_down = False
        self._command_trigger_down = False

        self._dictate_edge: Callable[[bool, float], None] | None = None
        self._command_press: Callable[[], None] | None = None
        self._command_release: Callable[[], None] | None = None
        self._debug_raw_key_logs_left = 12

    def start(
        self,
        on_press: Callable[[], None] | None = None,
        on_release: Callable[[], None] | None = None,
        *,
        dictate_edge: Callable[[bool, float], None] | None = None,
        command_press: Callable[[], None] | None = None,
        command_release: Callable[[], None] | None = None,
    ) -> None:
        if dictate_edge is not None:
            self._dictate_edge = dictate_edge
        elif on_press is not None and on_release is not None:

            def _wrap_edge(pressed: bool, when: float) -> None:
                del when
                if pressed:
                    on_press()
                else:
                    on_release()

            self._dictate_edge = _wrap_edge
        else:
            raise RuntimeError("Укажите dictate_edge или пару on_press/on_release")

        self._command_press = command_press
        self._command_release = command_release

        self._listener = Listener(on_press=self._handle_press, on_release=self._handle_release)
        self._listener.start()
        LOGGER.info("Глобальный слушатель хоткеев запущен (dictation + command)")
        # region agent log
        _agent_debug_log(
            "H9",
            "hotkey_listener.py:start",
            "listener started",
            {
                "dict_key_token": self._dict_spec.key_token,
                "dict_modifiers": sorted(self._dict_spec.modifiers),
                "has_command_hotkey": self._cmd_spec is not None,
            },
        )
        _agent_debug_log(
            "H15",
            "hotkey_listener.py:start:ax",
            "macOS accessibility trust status",
            {"ax_trusted": _macos_ax_is_trusted(), "pid": os.getpid(), "executable": sys.executable},
        )
        ax_trusted = _macos_ax_is_trusted()
        if ax_trusted is False:
            _agent_debug_log(
                "H15",
                "hotkey_listener.py:start:ax_prompt",
                "requesting macOS accessibility prompt",
                {"pid": os.getpid(), "executable": sys.executable},
            )
            _macos_ax_is_trusted(prompt_user=True)
            try:
                # Открываем нужный раздел настроек, чтобы пользователь сразу выдал доступ правильному бинарнику.
                subprocess.run(
                    ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
                    check=False,
                    timeout=5,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
            _agent_debug_log(
                "H15",
                "hotkey_listener.py:start:ax_after_prompt",
                "macOS accessibility trust status after prompt",
                {"ax_trusted": _macos_ax_is_trusted(), "pid": os.getpid(), "executable": sys.executable},
            )
            LOGGER.warning(
                "Нет разрешения Accessibility для backend-процесса (ghost_backend). "
                "Системные настройки → Конфиденциальность и безопасность → Универсальный доступ: "
                "добавьте/включите именно исполняемый файл ghost_backend из .app (см. лог executable=…)."
            )
        # endregion

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            LOGGER.info("Глобальный слушатель хоткеев остановлен")

    def _mods_satisfied(self, spec: HotkeySpec) -> bool:
        for mod in spec.modifiers:
            fam = MOD_FAMILIES.get(mod)
            if not fam:
                LOGGER.warning("Неизвестный модификатор в hotkey: %s", mod)
                return False
            if not any(m in self._pressed for m in fam):
                return False
        return True

    def _is_trigger_down_event(self, key: object, spec: HotkeySpec) -> bool:
        return _key_matches_token(key, spec.key_token) and self._mods_satisfied(spec)

    def _handle_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        self._pressed.add(key)
        try:
            # region agent log
            if self._debug_raw_key_logs_left > 0:
                self._debug_raw_key_logs_left -= 1
                _agent_debug_log(
                    "H14",
                    "hotkey_listener.py:_handle_press:raw",
                    "raw key press observed",
                    {
                        "key": str(key),
                        "dictation_match": self._is_trigger_down_event(key, self._dict_spec),
                        "pressed_count": len(self._pressed),
                    },
                )
            # endregion
            if self._cmd_spec and self._command_press and self._is_trigger_down_event(key, self._cmd_spec):
                if not self._command_trigger_down:
                    self._command_trigger_down = True
                    self._command_press()
                return

            if self._dictate_edge and self._is_trigger_down_event(key, self._dict_spec):
                if not self._dictate_trigger_down:
                    self._dictate_trigger_down = True
                    # region agent log
                    _agent_debug_log(
                        "H9",
                        "hotkey_listener.py:_handle_press",
                        "dictation hotkey pressed",
                        {"key": str(key)},
                    )
                    # endregion
                    self._dictate_edge(True, time.perf_counter())
        except Exception:  # noqa: BLE001
            LOGGER.exception("Ошибка в обработчике нажатия хоткея")

    def _handle_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        try:
            # region agent log
            if self._debug_raw_key_logs_left > 0:
                _agent_debug_log(
                    "H14",
                    "hotkey_listener.py:_handle_release:raw",
                    "raw key release observed",
                    {"key": str(key), "dictation_key_match": _key_matches_token(key, self._dict_spec.key_token)},
                )
            # endregion
            if self._cmd_spec and self._command_release and _key_matches_token(key, self._cmd_spec.key_token):
                if self._command_trigger_down:
                    self._command_trigger_down = False
                    self._command_release()

            if self._dictate_edge and _key_matches_token(key, self._dict_spec.key_token):
                if self._dictate_trigger_down:
                    self._dictate_trigger_down = False
                    # region agent log
                    _agent_debug_log(
                        "H9",
                        "hotkey_listener.py:_handle_release",
                        "dictation hotkey released",
                        {"key": str(key)},
                    )
                    # endregion
                    self._dictate_edge(False, time.perf_counter())
        except Exception:  # noqa: BLE001
            LOGGER.exception("Ошибка в обработчике отпускания хоткея")
        finally:
            self._pressed.discard(key)
