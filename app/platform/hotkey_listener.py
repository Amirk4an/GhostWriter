"""Глобальный слушатель хоткеев: комбинации, dictation edge, command mode."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from pynput import keyboard
from pynput.keyboard import Key, KeyCode, Listener

from app.core.hotkey_spec import MOD_FAMILIES, HotkeySpec, parse_hotkey_spec, token_to_pynput_key
from app.core.interfaces import HotkeyListener

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger(__name__)


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
            if self._cmd_spec and self._command_press and self._is_trigger_down_event(key, self._cmd_spec):
                if not self._command_trigger_down:
                    self._command_trigger_down = True
                    self._command_press()
                return

            if self._dictate_edge and self._is_trigger_down_event(key, self._dict_spec):
                if not self._dictate_trigger_down:
                    self._dictate_trigger_down = True
                    self._dictate_edge(True, time.perf_counter())
        except Exception:  # noqa: BLE001
            LOGGER.exception("Ошибка в обработчике нажатия хоткея")

    def _handle_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        try:
            if self._cmd_spec and self._command_release and _key_matches_token(key, self._cmd_spec.key_token):
                if self._command_trigger_down:
                    self._command_trigger_down = False
                    self._command_release()

            if self._dictate_edge and _key_matches_token(key, self._dict_spec.key_token):
                if self._dictate_trigger_down:
                    self._dictate_trigger_down = False
                    self._dictate_edge(False, time.perf_counter())
        except Exception:  # noqa: BLE001
            LOGGER.exception("Ошибка в обработчике отпускания хоткея")
        finally:
            self._pressed.discard(key)
