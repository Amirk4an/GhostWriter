"""Минималистичный плавающий виджет (pill) поверх остальных окон."""

from __future__ import annotations

import logging
import math
import threading
from collections.abc import Callable
from multiprocessing.queues import Queue as MPQueue
from queue import Empty
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ui.status_bridge import StatusBridge

LOGGER = logging.getLogger(__name__)

PILL_BLACK = "#000000"
PILL_BORDER = "#FFFFFF"
PILL_CORNER = 22


def _status_label(status: str) -> str:
    """Подпись статуса для pill (англ.)."""
    if status == "Recording":
        return "Recording..."
    if status == "Processing":
        return "Processing..."
    if status == "Error":
        return "Error"
    return "Ready"


def _ctk_pill_main_loop(
    *,
    _app_name: str,
    _primary_color: str,
    poll_ms: int,
    drain_queue: Callable[[], None],
    get_status: Callable[[], tuple[str, Any]],
    command_queue: MPQueue | None = None,
) -> None:
    """
    Общий цикл CustomTkinter для pill: чёрный фон, белая обводка, режимы Ready / Recording / прочее.

    Args:
        _app_name: Имя приложения (резерв для будущих подписей).
        _primary_color: Акцент из конфига (резерв).
        poll_ms: Интервал опроса состояния (мс).
        drain_queue: В начале каждого тика опустошает внешнюю очередь (для MP) или no-op.
        get_status: Возвращает пару (код статуса, detail).
        command_queue: Очередь команд в основной процесс (например открытие дашборда); если ``None``, кнопка не показывается.
    """
    import tkinter as tk

    import customtkinter as ctk

    from app.platform.macos_ctk_dock import bring_app_to_front, hide_dock_icon_for_ctk_root
    from app.ui.ctk_macos_theme import apply_ctk_macos_dark_theme, preferred_ui_font
    from app.ui.pill_ipc import open_dashboard_message

    root = ctk.CTk()
    root.withdraw()
    apply_ctk_macos_dark_theme()
    hide_dock_icon_for_ctk_root()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        LOGGER.debug("pill root: -topmost не поддерживается")
    bring_app_to_front()

    pill = ctk.CTkToplevel(root)
    pill.title("")
    pill.overrideredirect(True)
    pill.attributes("-topmost", True)
    try:
        pill.attributes("-alpha", 1.0)
    except tk.TclError:
        LOGGER.debug("alpha не поддерживается для Toplevel")

    pill.configure(fg_color=PILL_BLACK)
    pill.resizable(False, False)

    shell = ctk.CTkFrame(
        pill,
        fg_color=PILL_BLACK,
        corner_radius=PILL_CORNER,
        border_width=2,
        border_color=PILL_BORDER,
    )
    shell.pack(fill="both", expand=True, padx=0, pady=0)

    def _send_open_dashboard() -> None:
        if command_queue is None:
            return
        bring_app_to_front()
        try:
            command_queue.put_nowait(open_dashboard_message())
        except Exception as err:
            LOGGER.warning("Команда pill не отправлена: %s", err)

    body = ctk.CTkFrame(shell, fg_color="transparent")
    body.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)

    if command_queue is not None:
        gear_col = ctk.CTkFrame(shell, fg_color="transparent", width=36)
        gear_btn = ctk.CTkButton(
            gear_col,
            text="⚙",
            width=28,
            height=28,
            font=preferred_ui_font(14, master=root),
            fg_color=("#2C2C2E", "#2C2C2E"),
            hover_color=("#3D3D40", "#3D3D40"),
            border_width=1,
            border_color=("#48484A", "#48484A"),
            corner_radius=8,
            command=_send_open_dashboard,
        )
        gear_btn.pack(pady=8, padx=(2, 6))
        gear_col.pack(side="right", fill="y")

    gear_extra = 36 if command_queue is not None else 0

    ready_row = ctk.CTkFrame(body, fg_color="transparent")
    ready_txt = ctk.CTkLabel(
        ready_row,
        text="Ready",
        font=preferred_ui_font(13, "bold", master=root),
        text_color="#FFFFFF",
        anchor="center",
    )
    ready_txt.pack(fill="both", expand=True)

    rec_row = ctk.CTkFrame(body, fg_color="transparent")
    pulse_canvas = tk.Canvas(
        rec_row,
        width=40,
        height=40,
        highlightthickness=0,
        bg=PILL_BLACK,
        bd=0,
    )
    pulse_canvas.pack(side="left", padx=(0, 8))
    rec_txt = ctk.CTkLabel(
        rec_row,
        text="Recording...",
        font=preferred_ui_font(13, "bold", master=root),
        text_color="#FFFFFF",
    )
    rec_txt.pack(side="left")

    other_row = ctk.CTkFrame(body, fg_color="transparent")
    other_txt = ctk.CTkLabel(
        other_row,
        text="",
        font=preferred_ui_font(13, "bold", master=root),
        text_color="#FFFFFF",
    )
    other_txt.pack(side="left")

    detail_wrap = ctk.CTkFrame(shell, fg_color="transparent")
    detail_lbl = ctk.CTkLabel(
        detail_wrap,
        text="",
        font=preferred_ui_font(10, master=root),
        text_color="#D1D1D6",
        wraplength=340,
        justify="left",
    )
    detail_lbl.pack(anchor="w", padx=12, pady=(0, 8))

    phase_holder: list[float] = [0.0]
    width_collapsed = 96 + gear_extra
    height_pill = 44

    def place_at_bottom(w: int, h: int) -> None:
        pill.update_idletasks()
        sw = pill.winfo_screenwidth()
        sh = pill.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, sh - h - 48)
        pill.geometry(f"{w}x{h}+{x}+{y}")

    def draw_pulse() -> None:
        pulse_canvas.delete("all")
        phase_holder[0] += 0.42
        t = phase_holder[0]
        cx, cy = 20, 20
        r = 10.0 + 5.0 * math.sin(t)
        pulse_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#834CF5", outline="")
        pulse_canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill="#FF3B30", outline="")

    def show_ready() -> None:
        ready_row.pack(fill="both", expand=True)
        rec_row.pack_forget()
        other_row.pack_forget()
        detail_wrap.pack_forget()

    def show_recording() -> None:
        ready_row.pack_forget()
        rec_row.pack(fill="x", expand=True)
        other_row.pack_forget()
        draw_pulse()
        detail_wrap.pack_forget()

    def show_other(label: str, color: str) -> None:
        ready_row.pack_forget()
        rec_row.pack_forget()
        other_txt.configure(text=label, text_color=color)
        other_row.pack(fill="x", expand=True)

    def poll() -> None:
        drain_queue()
        st, detail = get_status()
        st_s = str(st)
        label = _status_label(st_s)
        show_detail = bool(detail) and (st_s == "Processing" or st_s == "Idle")
        detail_text = (
            (str(detail)[:500] + ("…" if len(str(detail)) > 500 else "")) if detail else ""
        )

        if st_s == "Idle":
            show_ready()
            if show_detail:
                w, h = 360 + gear_extra, 96
            else:
                w, h = width_collapsed, height_pill
        elif st_s == "Recording":
            show_recording()
            w, h = 232 + gear_extra, height_pill
        else:
            color = "#FF6B6B" if st_s == "Error" else "#FFFFFF"
            show_other(label, color)
            w, h = (360 + gear_extra if show_detail else 172 + gear_extra), (96 if show_detail else height_pill)

        if show_detail:
            detail_lbl.configure(text=detail_text)
            detail_wrap.pack(fill="x", expand=True)
        else:
            detail_wrap.pack_forget()

        pill.geometry(f"{w}x{h}")
        place_at_bottom(w, h)

        try:
            pill.update_idletasks()
            pill.lift()
        except tk.TclError:
            pass
        root.after(max(30, poll_ms), poll)

    show_ready()
    place_at_bottom(width_collapsed, height_pill)
    poll()
    LOGGER.info("Плавающий pill (CustomTkinter) запущен")
    root.mainloop()


def run_floating_pill_loop(
    *,
    status_bridge: "StatusBridge",
    app_name: str,
    primary_color: str,
    poll_ms: int = 50,
) -> None:
    """Блокирующий цикл CustomTkinter в отдельном потоке (как окно настроек)."""

    def drain() -> None:
        return

    def get_state() -> tuple[str, Any]:
        return status_bridge.snapshot()

    _ctk_pill_main_loop(
        _app_name=app_name,
        _primary_color=primary_color,
        poll_ms=poll_ms,
        drain_queue=drain,
        get_status=get_state,
        command_queue=None,
    )


def run_floating_pill_loop_mp(
    status_queue: MPQueue,
    command_queue: MPQueue,
    app_name: str,
    primary_color: str,
    poll_ms: int = 50,
) -> None:
    """Pill в отдельном процессе: на macOS сначала AppKit (без Tk), иначе CustomTkinter."""
    import platform

    if platform.system() == "Darwin":
        try:
            from app.ui.floating_pill_native import run_macos_native_pill

            run_macos_native_pill(status_queue, command_queue, app_name, primary_color, poll_ms)
            return
        except Exception as err:
            LOGGER.warning(
                "Плавающий pill (AppKit) не запустился (%s), переключаемся на CustomTkinter.",
                err,
            )
            _run_floating_pill_loop_ctk_mp(status_queue, command_queue, app_name, primary_color, poll_ms)
            return

    _run_floating_pill_loop_ctk_mp(status_queue, command_queue, app_name, primary_color, poll_ms)


def _run_floating_pill_loop_ctk_mp(
    status_queue: MPQueue,
    command_queue: MPQueue,
    app_name: str,
    primary_color: str,
    poll_ms: int = 50,
) -> None:
    """Pill через CustomTkinter (Tcl/Tk) — fallback если нет Cocoa."""
    latest: list[str | None] = ["Idle", None]

    def drain() -> None:
        try:
            while True:
                st, det = status_queue.get_nowait()
                latest[0] = st
                latest[1] = det
        except Empty:
            pass

    def get_state() -> tuple[str, Any]:
        return str(latest[0]), latest[1]

    _ctk_pill_main_loop(
        _app_name=app_name,
        _primary_color=primary_color,
        poll_ms=poll_ms,
        drain_queue=drain,
        get_status=get_state,
        command_queue=command_queue,
    )


def start_floating_pill_thread(
    *,
    status_bridge: "StatusBridge",
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
