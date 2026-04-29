"""Общие настройки CustomTkinter: режим темы и шрифт в духе macOS."""

from __future__ import annotations

import platform
from typing import Any


def apply_ctk_theme(ui_theme: str = "dark") -> None:
    """
    Включает режим темы и базовую палитру CTk.

    На macOS вызывайте **после** первого ``ctk.CTk()`` (или эквивалентного корня Tk),
    иначе возможен ``Tcl_Panic`` в ``TkpInit`` при ``spawn``.
    Импорт ``customtkinter`` выполняется внутри функции, чтобы не трогать Tcl при импорте модуля.
    """
    import customtkinter as ctk

    theme = (ui_theme or "dark").strip().lower()
    if theme not in ("dark", "light", "system"):
        theme = "dark"
    ctk.set_appearance_mode(theme)
    ctk.set_default_color_theme("dark-blue")


def preferred_ui_font(size: int, weight: str = "normal", master: Any | None = None) -> Any:
    """
    Возвращает шрифт интерфейса: на macOS предпочтителен системный стек SF.

    На macOS ``tkinter.font.Font`` без ``master`` создаёт неявный корень Tk и может
    привести к ``Tcl_Panic``; всегда передавайте ``master`` после ``ctk.CTk()``.

    Args:
        size: Кегль в пунктах.
        weight: «normal» или «bold».
        master: Виджет или ``CTk``, у которого уже есть корень Tk (обязательно на Darwin).

    Returns:
        Настроенный ``CTkFont``.
    """
    import tkinter.font as tkfont
    from tkinter import TclError

    import customtkinter as ctk

    if platform.system() == "Darwin" and master is not None:
        families = ("SF Pro Text", ".SF NS Text", "Helvetica Neue")
        for name in families:
            try:
                tkfont.Font(master, family=name, size=size, weight=weight)
                return ctk.CTkFont(family=name, size=size, weight=weight)
            except TclError:
                continue
    return ctk.CTkFont(size=size, weight=weight)
