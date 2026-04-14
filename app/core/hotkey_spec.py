"""Разбор строки хоткея вида «f8» или «cmd+shift+f8»."""

from __future__ import annotations

from dataclasses import dataclass

from pynput.keyboard import Key


@dataclass(frozen=True)
class HotkeySpec:
    """Модификаторы (имена) и основная клавиша."""

    modifiers: frozenset[str]
    key_token: str


def parse_hotkey_spec(raw: str) -> HotkeySpec:
    """Парсит hotkey: одна клавиша или несколько через +."""
    parts = [p.strip().lower() for p in raw.replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise ValueError("Пустой hotkey")
    if len(parts) == 1:
        return HotkeySpec(frozenset(), parts[0])
    return HotkeySpec(frozenset(parts[:-1]), parts[-1])


def token_to_pynput_key(token: str) -> Key | object:
    """Преобразует токен в объект клавиши pynput."""
    if len(token) == 1:
        return token
    if token.startswith("f") and token[1:].isdigit():
        n = int(token[1:])
        if 1 <= n <= 20:
            return getattr(Key, f"f{n}")
    named = {
        "space": Key.space,
        "tab": Key.tab,
        "enter": Key.enter,
        "return": Key.enter,
        "esc": Key.esc,
        "escape": Key.esc,
        "backspace": Key.backspace,
        "delete": Key.delete,
        "up": Key.up,
        "down": Key.down,
        "left": Key.left,
        "right": Key.right,
        "home": Key.home,
        "end": Key.end,
        "page_up": Key.page_up,
        "page_down": Key.page_down,
        "insert": Key.insert,
    }
    if token in named:
        return named[token]
    raise ValueError(f"Неподдерживаемая клавиша: {token}")


MOD_FAMILIES: dict[str, frozenset[object]] = {
    "cmd": frozenset({Key.cmd, Key.cmd_l, Key.cmd_r}),
    "super": frozenset({Key.cmd, Key.cmd_l, Key.cmd_r}),
    "win": frozenset({Key.cmd, Key.cmd_l, Key.cmd_r}),
    "ctrl": frozenset({Key.ctrl, Key.ctrl_l, Key.ctrl_r}),
    "control": frozenset({Key.ctrl, Key.ctrl_l, Key.ctrl_r}),
    "alt": frozenset({Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr}),
    "option": frozenset({Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr}),
    "shift": frozenset({Key.shift, Key.shift_l, Key.shift_r}),
}
