"""Тесты разбора строки хоткея."""

from __future__ import annotations

from pynput.keyboard import Key

from app.core.hotkey_spec import parse_hotkey_spec, token_to_pynput_key


def test_parse_single_key() -> None:
    s = parse_hotkey_spec("f8")
    assert s.modifiers == frozenset()
    assert s.key_token == "f8"


def test_parse_combo() -> None:
    s = parse_hotkey_spec("cmd+shift+right")
    assert s.modifiers == frozenset({"cmd", "shift"})
    assert s.key_token == "right"


def test_token_f_key() -> None:
    assert token_to_pynput_key("f8") == Key.f8


def test_token_char() -> None:
    assert token_to_pynput_key("x") == "x"
