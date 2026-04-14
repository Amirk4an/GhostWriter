"""Минималистичный плавающий виджет (pill) поверх остальных окон."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from multiprocessing.queues import Queue as MPQueue
from queue import Empty

import customtkinter as ctk

from app.ui.status_bridge import StatusBridge

LOGGER = logging.getLogger(__name__)


def _status_label(status: str) -> str:
    if status == "Recording":
        return "● Запись"
    if status == "Processing":
        return "⏳ Обработка"
    if status == "Error":
        return "✕ Ошибка"
    return "— Готов"


def run_floating_pill_loop(
    *,
    status_bridge: StatusBridge,
    app_name: str,
    primary_color: str,
    poll_ms: int = 100,
) -> None:
    """Блокирующий цикл CustomTkinter в отдельном потоке (как окно настроек)."""
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.withdraw()

    pill = ctk.CTkToplevel(root)
    pill.title("")
    pill.overrideredirect(True)
    pill.attributes("-topmost", True)
    try:
        pill.attributes("-alpha", 0.92)
    except tk.TclError:
        LOGGER.debug("alpha не поддерживается для Toplevel")

    pill.configure(fg_color=("#1a1a1e", "#1a1a1e"))
    pill.resizable(False, False)

    width_collapsed, height_pill = 140, 36
    pill.geometry(f"{width_collapsed}x{height_pill}")

    def place_at_bottom() -> None:
        pill.update_idletasks()
        sw = pill.winfo_screenwidth()
        sh = pill.winfo_screenheight()
        w = pill.winfo_width()
        h = pill.winfo_height()
        x = max(0, (sw - w) // 2)
        y = max(0, sh - h - 48)
        pill.geometry(f"+{x}+{y}")

    frame = ctk.CTkFrame(pill, fg_color="transparent", corner_radius=18)
    frame.pack(fill="both", expand=True, padx=2, pady=2)

    title = ctk.CTkLabel(
        frame,
        text=app_name[:18],
        font=("Arial", 10, "bold"),
        text_color=primary_color,
    )
    title.pack(side="left", padx=(10, 4))

    state_lbl = ctk.CTkLabel(frame, text=_status_label("Idle"), font=("Arial", 11))
    state_lbl.pack(side="left", padx=(0, 10))

    detail_frame = ctk.CTkFrame(pill, fg_color="transparent")
    detail_lbl = ctk.CTkLabel(
        detail_frame,
        text="",
        font=("Arial", 10),
        text_color="#aaaaaa",
        wraplength=360,
        justify="left",
    )
    detail_lbl.pack(anchor="w", padx=12, pady=(0, 8))

    expanded = {"value": False}
    prev_poll_status: list[str | None] = [None]

    def set_collapsed_size() -> None:
        pill.geometry(f"{width_collapsed}x{height_pill}")
        place_at_bottom()

    def expand_ui() -> None:
        if expanded["value"]:
            return
        expanded["value"] = True
        detail_frame.pack(fill="x", expand=True)
        pill.geometry("400x96")
        place_at_bottom()

    def collapse_ui() -> None:
        if not expanded["value"]:
            return
        expanded["value"] = False
        detail_frame.pack_forget()
        set_collapsed_size()

    def on_enter(_event: object | None = None) -> None:
        del _event
        expand_ui()

    def on_leave(_event: object | None = None) -> None:
        del _event
        st, _ = status_bridge.snapshot()
        if st not in ("Recording", "Processing"):
            collapse_ui()

    pill.bind("<Enter>", on_enter)
    pill.bind("<Leave>", on_leave)
    frame.bind("<Enter>", on_enter)
    frame.bind("<Leave>", on_leave)

    def poll() -> None:
        st, detail = status_bridge.snapshot()
        st_s = str(st)
        if prev_poll_status[0] in ("Recording", "Processing") and st_s not in (
            "Recording",
            "Processing",
        ):
            collapse_ui()
        prev_poll_status[0] = st_s
        state_lbl.configure(text=_status_label(st_s))
        if detail:
            detail_lbl.configure(text=detail[:500] + ("…" if len(detail) > 500 else ""))
        else:
            detail_lbl.configure(text="")
        if st_s in ("Recording", "Processing"):
            expand_ui()
        try:
            pill.update_idletasks()
        except tk.TclError:
            pass
        root.after(poll_ms, poll)

    place_at_bottom()
    poll()
    LOGGER.info("Плавающий pill запущен")
    root.mainloop()


def run_floating_pill_loop_mp(
    status_queue: MPQueue,
    app_name: str,
    primary_color: str,
    poll_ms: int = 100,
) -> None:
    """Pill в отдельном процессе: на macOS сначала AppKit (без Tk), иначе CustomTkinter."""
    import platform

    if platform.system() == "Darwin":
        try:
            from app.ui.floating_pill_native import run_macos_native_pill

            run_macos_native_pill(status_queue, app_name, primary_color, poll_ms)
            return
        except Exception as err:
            LOGGER.error(
                "Плавающий pill (AppKit) не запустился: %s. "
                "На macOS fallback на Tk/CustomTkinter отключён — у Apple CLI Python он часто падает в TkpInit.",
                err,
            )
            return

    _run_floating_pill_loop_ctk_mp(status_queue, app_name, primary_color, poll_ms)


def _run_floating_pill_loop_ctk_mp(
    status_queue: MPQueue,
    app_name: str,
    primary_color: str,
    poll_ms: int = 100,
) -> None:
    """Pill через CustomTkinter (Tcl/Tk) — fallback если нет Cocoa."""
    latest: list[str | None] = ["Idle", None]

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.withdraw()

    pill = ctk.CTkToplevel(root)
    pill.title("")
    pill.overrideredirect(True)
    pill.attributes("-topmost", True)
    try:
        pill.attributes("-alpha", 0.92)
    except tk.TclError:
        LOGGER.debug("alpha не поддерживается для Toplevel")

    pill.configure(fg_color=("#1a1a1e", "#1a1a1e"))
    pill.resizable(False, False)

    width_collapsed, height_pill = 140, 36
    pill.geometry(f"{width_collapsed}x{height_pill}")

    def place_at_bottom() -> None:
        pill.update_idletasks()
        sw = pill.winfo_screenwidth()
        sh = pill.winfo_screenheight()
        w = pill.winfo_width()
        h = pill.winfo_height()
        x = max(0, (sw - w) // 2)
        y = max(0, sh - h - 48)
        pill.geometry(f"+{x}+{y}")

    frame = ctk.CTkFrame(pill, fg_color="transparent", corner_radius=18)
    frame.pack(fill="both", expand=True, padx=2, pady=2)

    title = ctk.CTkLabel(
        frame,
        text=app_name[:18],
        font=("Arial", 10, "bold"),
        text_color=primary_color,
    )
    title.pack(side="left", padx=(10, 4))

    state_lbl = ctk.CTkLabel(frame, text=_status_label("Idle"), font=("Arial", 11))
    state_lbl.pack(side="left", padx=(0, 10))

    detail_frame = ctk.CTkFrame(pill, fg_color="transparent")
    detail_lbl = ctk.CTkLabel(
        detail_frame,
        text="",
        font=("Arial", 10),
        text_color="#aaaaaa",
        wraplength=360,
        justify="left",
    )
    detail_lbl.pack(anchor="w", padx=12, pady=(0, 8))

    expanded = {"value": False}
    prev_poll_status: list[str | None] = [None]

    def set_collapsed_size() -> None:
        pill.geometry(f"{width_collapsed}x{height_pill}")
        place_at_bottom()

    def expand_ui() -> None:
        if expanded["value"]:
            return
        expanded["value"] = True
        detail_frame.pack(fill="x", expand=True)
        pill.geometry("400x96")
        place_at_bottom()

    def collapse_ui() -> None:
        if not expanded["value"]:
            return
        expanded["value"] = False
        detail_frame.pack_forget()
        set_collapsed_size()

    def on_enter(_event: object | None = None) -> None:
        del _event
        expand_ui()

    def on_leave(_event: object | None = None) -> None:
        del _event
        st = latest[0]
        if st not in ("Recording", "Processing"):
            collapse_ui()

    pill.bind("<Enter>", on_enter)
    pill.bind("<Leave>", on_leave)
    frame.bind("<Enter>", on_enter)
    frame.bind("<Leave>", on_leave)

    def poll() -> None:
        try:
            while True:
                st, det = status_queue.get_nowait()
                latest[0] = st
                latest[1] = det
        except Empty:
            pass
        st, detail = latest[0], latest[1]
        st_s = str(st)
        if prev_poll_status[0] in ("Recording", "Processing") and st_s not in (
            "Recording",
            "Processing",
        ):
            collapse_ui()
        prev_poll_status[0] = st_s
        state_lbl.configure(text=_status_label(st_s))
        if detail:
            detail_lbl.configure(text=str(detail)[:500] + ("…" if len(str(detail)) > 500 else ""))
        else:
            detail_lbl.configure(text="")
        if st_s in ("Recording", "Processing"):
            expand_ui()
        try:
            pill.update_idletasks()
        except tk.TclError:
            pass
        root.after(poll_ms, poll)

    place_at_bottom()
    poll()
    LOGGER.info("Плавающий pill (отдельный процесс) запущен")
    root.mainloop()


def start_floating_pill_thread(
    *,
    status_bridge: StatusBridge,
    app_name: str,
    primary_color: str,
) -> threading.Thread:
    thread = threading.Thread(
        target=run_floating_pill_loop,
        kwargs={
            "status_bridge": status_bridge,
            "app_name": app_name,
            "primary_color": primary_color,
        },
        daemon=True,
    )
    thread.start()
    return thread
