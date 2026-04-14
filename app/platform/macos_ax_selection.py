"""Чтение выделенного текста через Accessibility (macOS)."""

from __future__ import annotations

import logging
import platform

LOGGER = logging.getLogger(__name__)


def get_focused_selected_text() -> str | None:
    """Возвращает выделенный текст в сфокусированном элементе или None."""
    if platform.system() != "Darwin":
        return None
    try:
        from ApplicationServices import (  # type: ignore[import-untyped]
            AXUIElementCopyAttributeValue,
            AXUIElementCreateSystemWide,
            kAXFocusedUIElementAttribute,
            kAXSelectedTextAttribute,
        )
    except ImportError:
        LOGGER.warning(
            "Для command mode установите: pip install pyobjc-framework-ApplicationServices (macOS)."
        )
        return None

    system = AXUIElementCreateSystemWide()
    err, focused = AXUIElementCopyAttributeValue(system, kAXFocusedUIElementAttribute, None)
    if err != 0 or focused is None:
        LOGGER.debug("AX: нет сфокусированного UI-элемента (код %s)", err)
        return None

    err2, selected = AXUIElementCopyAttributeValue(focused, kAXSelectedTextAttribute, None)
    if err2 != 0 or selected is None:
        LOGGER.debug("AX: у элемента нет выделенного текста")
        return None

    text = str(selected).strip()
    return text or None
