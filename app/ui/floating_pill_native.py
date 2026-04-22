"""Плавающий pill на AppKit (без Tcl/Tk) — для macOS и Python с устаревшим _tkinter."""

from __future__ import annotations

import logging
import math
import platform
import sys
from queue import Empty
from typing import Any

LOGGER = logging.getLogger(__name__)


def _status_label(status: str) -> str:
    """Подпись статуса для pill (англ.)."""
    if status == "Recording":
        return "Recording..."
    if status == "Processing":
        return "Processing..."
    if status == "Error":
        return "Error"
    return "Ready"


def run_macos_native_pill(
    status_queue: Any,
    command_queue: Any,
    app_name: str,
    primary_color: str,
    poll_ms: int = 50,
) -> None:
    """
    Точка входа для дочернего процесса: только Cocoa, без _tkinter.

    Args:
        status_queue: Очередь статусов от основного процесса.
        command_queue: Очередь команд в основной процесс (например ``open_dashboard``).
        app_name: Имя приложения (резерв для подписей вне режима Ready).
        primary_color: Акцент из конфига (зарезервировано).
        poll_ms: Интервал опроса очереди (мс), не реже 30 мс.
    """
    del primary_color
    if sys.platform != "darwin" or platform.system() != "Darwin":
        raise RuntimeError("AppKit pill только для macOS")

    import objc
    from AppKit import (
        NSApplication,
        NSApplicationActivationPolicyRegular,
        NSBackingStoreBuffered,
        NSColor,
        NSFont,
        NSFontWeightMedium,
        NSFontWeightSemibold,
        NSMakeRect,
        NSButton,
        NSTextAlignmentCenter,
        NSPanel,
        NSPopUpMenuWindowLevel,
        NSScreen,
        NSTextField,
        NSView,
        NSWindow,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowStyleMaskBorderless,
        NSWindowStyleMaskNonactivatingPanel,
    )
    from Foundation import NSMakePoint, NSObject, NSTimer
    from Quartz import CALayer, CATransform3DMakeScale

    class _NativePillController(NSObject):
        def init(self):  # noqa: N802
            self = objc.super(_NativePillController, self).init()
            if self is None:
                return None
            self.queue = None
            self.app_name = ""
            self.interval = 0.05
            self.latest: list[Any] = ["Idle", None]
            self.panel: Any = None
            self._content: Any = None
            self._container: Any = None
            self._ready_label: Any = None
            self._pulse_host: Any = None
            self._pulse_outer: Any = None
            self._pulse_inner: Any = None
            self._status_label_field: Any = None
            self._detail_field: Any = None
            self._gear_button: Any = None
            self.command_queue: Any = None
            self._last_mode: str | None = None
            self._pulse_phase: float = 0.0
            self._gear_reserved = 36.0
            return self

        def gearClicked_(self, sender) -> None:  # noqa: N802
            """Отправляет в основной процесс команду открытия дашборда."""
            del sender
            cq = self.command_queue
            if cq is None:
                return
            try:
                from app.ui.pill_ipc import open_dashboard_message

                cq.put_nowait(open_dashboard_message())
            except Exception:
                LOGGER.exception("Не удалось отправить команду из pill")

        def startWithStatusQueue_commandQueue_appName_primaryColor_intervalMs_(  # noqa: N802
            self, status_queue, command_queue, app_name, primary_color, interval_ms
        ):
            del primary_color
            self.queue = status_queue
            self.command_queue = command_queue
            self.app_name = str(app_name)[:18]
            self.interval = max(0.03, min(0.12, float(interval_ms) / 1000.0))

            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

            screen = NSScreen.mainScreen()
            if screen is None:
                raise RuntimeError("NSScreen.mainScreen() is nil")
            vf = screen.visibleFrame()
            self._gear_reserved = 36.0
            w, h = 96.0 + self._gear_reserved, 42.0
            x = vf.origin.x + (vf.size.width - w) / 2.0
            y = vf.origin.y + 48.0
            frame = NSMakeRect(x, y, w, h)

            style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
            panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            panel.setFloatingPanel_(True)
            panel.setLevel_(NSPopUpMenuWindowLevel)
            panel.setOpaque_(False)
            panel.setAlphaValue_(1.0)
            panel.setBackgroundColor_(NSColor.clearColor())
            panel.setHasShadow_(True)
            panel.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorFullScreenAuxiliary
            )
            # В части сборок PyObjC у NSPanel нет бриджей setCanBecome* — не критично для плавающего UI.
            for _setter_name, _flag in (
                ("setCanBecomeKeyWindow_", False),
                ("setCanBecomeMainWindow_", False),
            ):
                _setter = getattr(panel, _setter_name, None)
                if callable(_setter):
                    try:
                        _setter(_flag)
                    except Exception:
                        LOGGER.debug("Панель: %s не применился", _setter_name, exc_info=True)

            content = panel.contentView()
            content.setWantsLayer_(True)
            cl = content.layer()
            if cl:
                cl.setBackgroundColor_(NSColor.blackColor().CGColor())
                cl.setCornerRadius_(22.0)
                cl.setMasksToBounds_(True)
                cl.setBorderWidth_(1.5)
                cl.setBorderColor_(NSColor.whiteColor().CGColor())

            bounds = content.bounds()
            container = NSView.alloc().initWithFrame_(bounds)
            content.addSubview_(container)

            ready_label = NSTextField.labelWithString_("Ready")
            ready_label.setFont_(NSFont.systemFontOfSize_weight_(13, NSFontWeightSemibold))
            ready_label.setTextColor_(NSColor.whiteColor())
            ready_label.setAlignment_(NSTextAlignmentCenter)
            ready_label.setFrame_(NSMakeRect(8, 10, max(40.0, bounds.size.width - 16), 22))
            ready_label.setHidden_(True)
            container.addSubview_(ready_label)

            pulse_host = NSView.alloc().initWithFrame_(NSMakeRect(10, 5, 32, 32))
            pulse_host.setWantsLayer_(True)
            pulse_host.setHidden_(True)
            container.addSubview_(pulse_host)

            status_label = NSTextField.labelWithString_("Ready")
            status_label.setFont_(NSFont.systemFontOfSize_weight_(13, NSFontWeightSemibold))
            status_label.setTextColor_(NSColor.whiteColor())
            status_label.setFrame_(NSMakeRect(48, 10, 200, 22))
            status_label.setHidden_(True)
            container.addSubview_(status_label)

            detail = NSTextField.wrappingLabelWithString_("")
            detail.setFont_(NSFont.systemFontOfSize_weight_(11, NSFontWeightMedium))
            detail.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(0.78, 1.0))
            detail.setFrame_(NSMakeRect(14, 6, bounds.size.width - 28, 44))
            detail.setAutoresizingMask_(18)
            detail.setHidden_(True)
            container.addSubview_(detail)

            gear = NSButton.buttonWithTitle_target_action_("⚙", self, "gearClicked:")
            gear.setBordered_(False)
            gear.setFont_(NSFont.systemFontOfSize_weight_(15, NSFontWeightSemibold))
            try:
                gear.setContentTintColor_(NSColor.whiteColor())
            except Exception:
                pass
            gear.setFrame_(NSMakeRect(bounds.size.width - 34, 8, 28, 26))
            container.addSubview_(gear)
            self._gear_button = gear

            self.panel = panel
            self._content = content
            self._container = container
            self._ready_label = ready_label
            self._pulse_host = pulse_host
            self._pulse_outer = None
            self._pulse_inner = None
            self._status_label_field = status_label
            self._detail_field = detail

            self.tick_(None)
            panel.display()
            try:
                NSWindow.orderFrontRegardless_(panel, None)
            except (AttributeError, TypeError):
                panel.orderFront_(None)

            LOGGER.info("Плавающий pill (AppKit) запущен")

            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                self.interval, self, "tick:", None, True
            )
            app.run()

        def _clear_pulse_layers(self) -> None:
            host = self._pulse_host
            if host is None:
                return
            L = host.layer()
            if L is None:
                return
            subs = L.sublayers()
            if subs:
                for s in list(subs):
                    s.removeFromSuperlayer()
            self._pulse_outer = None
            self._pulse_inner = None

        def _ensure_pulse_layers(self) -> None:
            if self._pulse_outer is not None:
                return
            host = self._pulse_host
            if host is None:
                return
            host.setWantsLayer_(True)
            L = host.layer()
            if L is None:
                return
            purple = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.52, 0.28, 0.98, 0.92)
            red = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.98, 0.22, 0.22, 1.0)

            outer = CALayer.layer()
            outer.setBounds_(NSMakeRect(0, 0, 26, 26))
            outer.setPosition_(NSMakePoint(16, 16))
            outer.setAnchorPoint_(NSMakePoint(0.5, 0.5))
            outer.setCornerRadius_(13.0)
            outer.setBackgroundColor_(purple.CGColor())

            inner = CALayer.layer()
            inner.setBounds_(NSMakeRect(0, 0, 8, 8))
            inner.setPosition_(NSMakePoint(16, 16))
            inner.setAnchorPoint_(NSMakePoint(0.5, 0.5))
            inner.setCornerRadius_(4.0)
            inner.setBackgroundColor_(red.CGColor())

            L.addSublayer_(outer)
            L.addSublayer_(inner)
            self._pulse_outer = outer
            self._pulse_inner = inner

        def tick_(self, timer) -> None:  # noqa: N802
            del timer
            if self.queue is None or self.panel is None or self._container is None:
                return
            try:
                while True:
                    st, det = self.queue.get_nowait()
                    self.latest = [st, det]
            except Empty:
                pass

            st, detail = self.latest[0], self.latest[1]
            st_s = str(st)
            label = _status_label(st_s)

            show_detail = bool(detail) and st_s == "Processing"
            detail_text = (
                (str(detail)[:420] + ("…" if detail and len(str(detail)) > 420 else ""))
                if detail
                else ""
            )

            if st_s == "Idle":
                mode = "ready"
            elif st_s == "Recording":
                mode = "recording"
            else:
                mode = "other"

            if mode != self._last_mode:
                if mode != "recording":
                    self._clear_pulse_layers()
                    self._pulse_phase = 0.0
                elif mode == "recording":
                    self._ensure_pulse_layers()
                self._last_mode = mode

            gr = self._gear_reserved
            if mode == "ready":
                self._ready_label.setHidden_(False)
                self._pulse_host.setHidden_(True)
                self._status_label_field.setHidden_(True)
                w, h = 96.0 + gr, 42.0
            elif mode == "recording":
                self._ready_label.setHidden_(True)
                self._pulse_host.setHidden_(False)
                self._status_label_field.setHidden_(False)
                self._status_label_field.setStringValue_(label)
                self._status_label_field.setTextColor_(NSColor.whiteColor())
                self._status_label_field.setFrame_(NSMakeRect(46, 10, 170, 22))
                w, h = 228.0 + gr, 42.0
                self._pulse_phase += self.interval * 5.5
                if self._pulse_outer is not None:
                    s = 0.86 + 0.14 * math.sin(self._pulse_phase)
                    op = 0.5 + 0.45 * (0.5 + 0.5 * math.sin(self._pulse_phase + 0.5))
                    self._pulse_outer.setTransform_(CATransform3DMakeScale(s, s, 1.0))
                    self._pulse_outer.setOpacity_(float(op))
            else:
                self._ready_label.setHidden_(True)
                self._pulse_host.setHidden_(True)
                self._status_label_field.setHidden_(False)
                self._status_label_field.setStringValue_(label)
                if st_s == "Error":
                    self._status_label_field.setTextColor_(
                        NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.35, 0.35, 1.0)
                    )
                else:
                    self._status_label_field.setTextColor_(NSColor.whiteColor())
                w, h = (360.0 + gr if show_detail else 168.0 + gr), (88.0 if show_detail else 42.0)

            self._detail_field.setStringValue_(detail_text if show_detail else "")
            self._detail_field.setHidden_(not show_detail)

            screen = NSScreen.mainScreen()
            if screen is None:
                return
            vf = screen.visibleFrame()
            new_frame = NSMakeRect(
                vf.origin.x + (vf.size.width - w) / 2.0,
                vf.origin.y + 48.0,
                w,
                h,
            )
            self.panel.setFrame_display_animate_(new_frame, True, False)

            cv = self.panel.contentView()
            inner = cv.bounds()
            self._container.setFrame_(inner)

            cl = cv.layer()
            if cl:
                cl.setCornerRadius_(22.0)

            if self._gear_button is not None:
                gw, gh = 28.0, 26.0
                gx = max(4.0, inner.size.width - gw - 6.0)
                gy = max(6.0, (inner.size.height - gh) / 2.0)
                self._gear_button.setFrame_(NSMakeRect(gx, gy, gw, gh))

            if mode == "ready":
                pad = 10.0
                right_pad = gr + 4.0
                self._ready_label.setFrame_(
                    NSMakeRect(pad, 10, max(40.0, inner.size.width - pad - right_pad), 22)
                )
            elif mode == "recording":
                self._pulse_host.setFrame_(NSMakeRect(10, 5, 32, 32))
                self._status_label_field.setFrame_(
                    NSMakeRect(46, 10, max(80.0, inner.size.width - 56.0 - gr), 22)
                )
            else:
                self._status_label_field.setFrame_(
                    NSMakeRect(14, 10, max(60.0, inner.size.width - 28.0 - gr), 22)
                )

            self._detail_field.setFrame_(
                NSMakeRect(14, 6, inner.size.width - 28, max(36.0, inner.size.height - 40))
            )

            try:
                NSWindow.orderFrontRegardless_(self.panel, None)
            except (AttributeError, TypeError):
                self.panel.orderFrontRegardless()

    ctrl = _NativePillController.alloc().init()
    ctrl.startWithStatusQueue_commandQueue_appName_primaryColor_intervalMs_(
        status_queue, command_queue, app_name, "", poll_ms
    )
