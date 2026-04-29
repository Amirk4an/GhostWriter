"""Тесты безопасного чтения выделения на Windows."""

from __future__ import annotations

import pyperclip
import pytest

from app.platform.windows import selection_reader


class _PressedCtx:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


class _FakeKeyboard:
    def __init__(self, clipboard_state: dict[str, str], selected_text: str) -> None:
        self._state = clipboard_state
        self._selected_text = selected_text

    def pressed(self, _key):
        return _PressedCtx()

    def tap(self, key: str) -> None:
        if key == "c":
            self._state["value"] = self._selected_text


def test_windows_selection_reader_restores_text_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"value": "ORIGINAL"}
    copied: list[str] = []

    monkeypatch.setattr(selection_reader.platform, "system", lambda: "Windows")
    monkeypatch.setattr(selection_reader, "Controller", lambda: _FakeKeyboard(state, " SELECTED "))
    monkeypatch.setattr(selection_reader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(selection_reader.pyperclip, "paste", lambda: state["value"])
    monkeypatch.setattr(
        selection_reader.pyperclip,
        "copy",
        lambda value: (copied.append(value), state.__setitem__("value", value)),
    )

    result = selection_reader.get_focused_selected_text_windows()

    assert result == "SELECTED"
    assert copied[-1] == "ORIGINAL"
    assert state["value"] == "ORIGINAL"


def test_windows_selection_reader_clears_when_backup_is_not_text(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"value": "ignored"}
    copied: list[str] = []
    calls = {"paste": 0}

    def fake_paste() -> str:
        calls["paste"] += 1
        if calls["paste"] == 1:
            raise pyperclip.PyperclipException("non-text clipboard")
        return state["value"]

    monkeypatch.setattr(selection_reader.platform, "system", lambda: "Windows")
    monkeypatch.setattr(selection_reader, "Controller", lambda: _FakeKeyboard(state, "SELECTED"))
    monkeypatch.setattr(selection_reader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(selection_reader.pyperclip, "paste", fake_paste)
    monkeypatch.setattr(
        selection_reader.pyperclip,
        "copy",
        lambda value: (copied.append(value), state.__setitem__("value", value)),
    )

    result = selection_reader.get_focused_selected_text_windows()

    assert result == "SELECTED"
    assert copied[-1] == ""
    assert state["value"] == ""
