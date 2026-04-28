"""Перехват комбинации клавиш для полей хоткея (Tk / CustomTkinter)."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from collections.abc import Callable
from typing import Any

LOGGER = logging.getLogger(__name__)

_MODIFIER_KEYSYMS = frozenset(
    {
        "Shift_L",
        "Shift_R",
        "Control_L",
        "Control_R",
        "Alt_L",
        "Alt_R",
        "Meta_L",
        "Meta_R",
        "Super_L",
        "Super_R",
        "Caps_Lock",
        "ISO_Level3_Shift",
    }
)


def tk_keyevent_to_hotkey_string(event: tk.Event[Any]) -> str | None:
    """
    Преобразует KeyPress в строку вида ``cmd+shift+f8`` (нижний регистр).

    ``None`` — событие не образует хоткей (модификатор и т.п.).
    ``""`` — очистить (Escape).
    """
    keysym = getattr(event, "keysym", "") or ""
    if not keysym or keysym in _MODIFIER_KEYSYMS:
        return None
    if keysym in ("Left", "Right", "Up", "Down", "Next", "Prior", "Menu", "Tab"):
        return None

    st = int(getattr(event, "state", 0) or 0)
    parts: list[str] = []

    if sys.platform == "darwin":
        if st & 0x0001:
            parts.append("shift")
        if st & 0x0008:
            parts.append("cmd")
        if st & 0x0004:
            parts.append("ctrl")
        if st & 0x00080000 or st & 0x0010 or st & 0x0080:
            parts.append("alt")
    else:
        if st & 0x0001:
            parts.append("shift")
        if st & 0x0004:
            parts.append("ctrl")
        if st & 0x20000 or st & 0x0008:
            parts.append("alt")
        if st & 0x00040000:
            parts.append("cmd")

    k = keysym.lower()
    if k.startswith("f") and len(k) <= 3 and len(k) > 1 and k[1:].isdigit():
        token = k
    elif len(keysym) == 1:
        token = keysym.lower() if keysym.isalpha() else keysym
    elif keysym in ("Return", "Enter"):
        token = "enter"
    elif keysym == "space":
        token = "space"
    else:
        token = k

    if token in ("escape", "esc"):
        return ""

    return "+".join(parts + [token]) if parts else token


def _is_paste_event(event: tk.Event[Any]) -> bool:
    if (event.keysym or "").lower() != "v":
        return False
    st = int(getattr(event, "state", 0) or 0)
    if sys.platform == "darwin" and (st & 0x0008):
        return True
    return bool(st & 0x0004)


def bind_hotkey_capture(entry: Any, on_change: Callable[[str], None], *, clear_on_escape: bool = True) -> None:
    """
    Перехватывает KeyPress: записывает комбинацию в поле и вызывает ``on_change``, не вставляя печатные символы.

    Вставка из буфера (Ctrl/Cmd+V) не перехватывается.
    """

    def on_key_press(event: tk.Event[Any]) -> str | None:
        if _is_paste_event(event):
            return None
        spec = tk_keyevent_to_hotkey_string(event)
        if spec is None:
            return "break"
        if spec == "" and clear_on_escape:
            on_change("")
            try:
                entry.delete(0, "end")
            except tk.TclError:
                LOGGER.debug("hotkey_capture: delete", exc_info=True)
            return "break"
        if not spec:
            return "break"
        on_change(spec)
        try:
            entry.delete(0, "end")
            entry.insert(0, spec)
        except tk.TclError:
            LOGGER.debug("hotkey_capture: set entry", exc_info=True)
        return "break"

    entry.bind("<KeyPress>", on_key_press, add=True)
