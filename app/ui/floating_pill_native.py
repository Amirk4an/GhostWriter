"""Плавающий pill на AppKit (без Tcl/Tk) — для macOS и Python с устаревшим _tkinter."""

from __future__ import annotations

import logging
import platform
import sys
from queue import Empty
from typing import Any

LOGGER = logging.getLogger(__name__)


def _status_label(status: str) -> str:
    if status == "Recording":
        return "● Запись"
    if status == "Processing":
        return "⏳ Обработка"
    if status == "Error":
        return "✕ Ошибка"
    return "— Готов"


def run_macos_native_pill(
    status_queue: Any,
    app_name: str,
    primary_color: str,
    poll_ms: int = 100,
) -> None:
    """Точка входа для дочернего процесса: только Cocoa, без _tkinter."""
    if sys.platform != "darwin" or platform.system() != "Darwin":
        raise RuntimeError("AppKit pill только для macOS")

    import objc
    from AppKit import (
        NSApplication,
        NSApplicationActivationPolicyRegular,
        NSBackingStoreBuffered,
        NSColor,
        NSFont,
        NSFontAttributeName,
        NSFontWeightMedium,
        NSFontWeightSemibold,
        NSForegroundColorAttributeName,
        NSMakeRect,
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
    from Foundation import NSMutableAttributedString, NSMakeRange, NSObject, NSTimer

    def _hex_to_ns_color(hex_str: str) -> NSColor:
        h = hex_str.strip().lstrip("#")
        if len(h) == 6:
            try:
                r = int(h[0:2], 16) / 255.0
                g = int(h[2:4], 16) / 255.0
                b = int(h[4:6], 16) / 255.0
                return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0)
            except ValueError:
                pass
        return NSColor.colorWithCalibratedWhite_alpha_(0.75, 1.0)

    class _NativePillController(NSObject):
        def init(self):  # noqa: N802
            self = objc.super(_NativePillController, self).init()
            if self is None:
                return None
            self.queue = None
            self.app_name = ""
            self.accent = NSColor.whiteColor()
            self.interval = 0.1
            self.latest: list[Any] = ["Idle", None]
            self.panel: Any = None
            self.line1: Any = None
            self.line2: Any = None
            return self

        def startWithQueue_appName_primaryColor_intervalMs_(  # noqa: N802
            self, queue, app_name, primary_color, interval_ms
        ):
            self.queue = queue
            self.app_name = str(app_name)[:18]
            self.accent = _hex_to_ns_color(str(primary_color))
            self.interval = max(0.05, float(interval_ms) / 1000.0)

            app = NSApplication.sharedApplication()
            # Regular: иначе у процесса без .app bundle окна часто не показываются (Accessory «глотает» UI).
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

            screen = NSScreen.mainScreen()
            if screen is None:
                raise RuntimeError("NSScreen.mainScreen() is nil")
            vf = screen.visibleFrame()
            w, h = 280, 38
            x = vf.origin.x + (vf.size.width - w) / 2
            y = vf.origin.y + 48
            frame = NSMakeRect(x, y, w, h)

            style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
            panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            panel.setFloatingPanel_(True)
            panel.setLevel_(NSPopUpMenuWindowLevel)
            panel.setOpaque_(False)
            panel.setAlphaValue_(1.0)
            bg = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.12, 0.12, 0.14, 0.97)
            panel.setBackgroundColor_(bg)
            panel.setHasShadow_(True)
            panel.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorFullScreenAuxiliary
            )

            content = panel.contentView()
            content.setWantsLayer_(True)
            if content.layer():
                content.layer().setBackgroundColor_(bg.CGColor())
            bounds = content.bounds()
            container = NSView.alloc().initWithFrame_(bounds)
            container.setWantsLayer_(True)
            container.setAutoresizingMask_(18)
            content.addSubview_(container)

            line1 = NSTextField.labelWithString_(" ")
            font1 = NSFont.systemFontOfSize_weight_(12, NSFontWeightSemibold)
            line1.setFont_(font1)
            line1.setFrame_(NSMakeRect(12, 10, bounds.size.width - 24, 20))
            line1.setAutoresizingMask_(18)
            container.addSubview_(line1)

            line2 = NSTextField.wrappingLabelWithString_("")
            line2.setFont_(NSFont.systemFontOfSize_weight_(11, NSFontWeightMedium))
            line2.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(0.72, 1.0))
            line2.setFrame_(NSMakeRect(12, 4, bounds.size.width - 24, 48))
            line2.setAutoresizingMask_(18)
            line2.setHidden_(True)
            container.addSubview_(line2)

            self.panel = panel
            self.line1 = line1
            self.line2 = line2

            self.tick_(None)
            panel.display()
            # PyObjC: у NSPanel часто нет orderFrontRegardless_; пробуем NSWindow, иначе orderFront:.
            try:
                NSWindow.orderFrontRegardless_(panel, None)
            except (AttributeError, TypeError):
                panel.orderFront_(None)
            app.activateIgnoringOtherApps_(True)
            LOGGER.info("Плавающий pill (AppKit) запущен")

            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                self.interval, self, "tick:", None, True
            )
            app.run()

        def tick_(self, timer) -> None:  # noqa: N802
            del timer
            if self.queue is None or self.panel is None or self.line1 is None or self.line2 is None:
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
            title = self.app_name
            sep = "    "
            full = f"{title}{sep}{label}"

            m = NSMutableAttributedString.alloc().initWithString_(full)
            font1 = NSFont.systemFontOfSize_weight_(12, NSFontWeightSemibold)
            m.addAttribute_value_range_(NSFontAttributeName, font1, NSMakeRange(0, len(full)))
            m.addAttribute_value_range_(
                NSForegroundColorAttributeName, NSColor.whiteColor(), NSMakeRange(0, len(full))
            )
            m.addAttribute_value_range_(
                NSForegroundColorAttributeName, self.accent, NSMakeRange(0, len(title))
            )
            self.line1.setAttributedStringValue_(m)

            show_detail = bool(detail) and st_s in ("Recording", "Processing")
            text = (
                (str(detail)[:420] + ("…" if detail and len(str(detail)) > 420 else ""))
                if detail
                else ""
            )
            self.line2.setStringValue_(text)
            self.line2.setHidden_(not show_detail)

            screen = NSScreen.mainScreen()
            if screen is None:
                return
            vf = screen.visibleFrame()
            wide = 420 if show_detail else 280
            tall = 90 if show_detail else 38
            new_frame = NSMakeRect(
                vf.origin.x + (vf.size.width - wide) / 2,
                vf.origin.y + 48,
                wide,
                tall,
            )
            self.panel.setFrame_display_animate_(new_frame, True, False)

            inner = self.panel.contentView().bounds()
            self.line1.setFrame_(
                NSMakeRect(12, inner.size.height - 26, inner.size.width - 24, 22)
            )
            self.line2.setFrame_(NSMakeRect(12, 6, inner.size.width - 24, inner.size.height - 34))

    ctrl = _NativePillController.alloc().init()
    ctrl.startWithQueue_appName_primaryColor_intervalMs_(
        status_queue, app_name, primary_color, poll_ms
    )
