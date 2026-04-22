"""Проверка прав Accessibility (Универсальный доступ) для процесса на macOS."""

from __future__ import annotations

import ctypes
import logging
import os

LOGGER = logging.getLogger(__name__)

_APPLICATION_SERVICES_LIB = (
    "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
)


def _macos_axis_trusted_via_ctypes() -> bool | None:
    """Вызывает AXIsProcessTrusted() из ApplicationServices без PyObjC (нужно для PyInstaller onedir)."""
    try:
        lib = ctypes.CDLL(_APPLICATION_SERVICES_LIB)
        fn = getattr(lib, "AXIsProcessTrusted", None)
        if fn is None:
            return None
        # В заголовках Apple — Boolean (UInt8), не bool в смысле ABI.
        fn.restype = ctypes.c_uint8
        fn.argtypes = []
        return bool(fn())
    except Exception as err:  # noqa: BLE001
        LOGGER.debug("AXIsProcessTrusted (ctypes): %s", err)
        return None


def _macos_axis_trusted_pyobjc() -> bool | None:
    """AXIsProcessTrusted через PyObjC; None при недоступном API."""
    try:
        from ApplicationServices import AXIsProcessTrusted  # type: ignore[import-not-found]

        return bool(AXIsProcessTrusted())
    except Exception as err:  # noqa: BLE001
        LOGGER.debug("AXIsProcessTrusted (PyObjC): %s", err)
        return None


def _merge_ax_trust(py: bool | None, ct: bool | None) -> bool | None:
    """Объединяет два источника: достаточно одного True; два False — False; иначе консервативно False/None."""
    if py is True or ct is True:
        return True
    if py is False and ct is False:
        return False
    if py is None and ct is None:
        return None
    return False


def macos_accessibility_trust_breakdown() -> dict[str, bool | None]:
    """Снимок доверия AX для отладки (PyObjC, ctypes, итог)."""
    if os.name != "posix":
        return {"pyobjc": None, "ctypes": None, "merged": None}
    py = _macos_axis_trusted_pyobjc()
    ct = _macos_axis_trusted_via_ctypes()
    return {"pyobjc": py, "ctypes": ct, "merged": _merge_ax_trust(py, ct)}


def macos_accessibility_is_trusted(prompt_user: bool = False) -> bool | None:
    """Возвращает True, если текущему процессу разрешён контроль UI (AX); None — если проверить нельзя.

    Без prompt: вызываются и PyObjC, и ctypes; True, если хотя бы один источник сообщает True.

    При prompt_user=True система может показать диалог включения доступа (только через PyObjC).

    Args:
        prompt_user: Запросить у системы подсказку/диалог при отсутствии доверия.

    Returns:
        True/False при успешной проверке, None если API недоступен.
    """
    if os.name != "posix":
        return None
    if prompt_user:
        try:
            from ApplicationServices import (  # type: ignore[import-not-found]
                AXIsProcessTrustedWithOptions,
                kAXTrustedCheckOptionPrompt,
            )

            return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}))
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("macos_accessibility_is_trusted prompt (PyObjC): %s", err)
            return None
    py = _macos_axis_trusted_pyobjc()
    ct = _macos_axis_trusted_via_ctypes()
    return _merge_ax_trust(py, ct)
