"""Настройка политики NSApplication для окон CustomTkinter на macOS."""

from __future__ import annotations

import logging
import platform
import sys

LOGGER = logging.getLogger(__name__)


def bring_app_to_front() -> None:
    """
    Принудительно активирует приложение и выводит его окна поверх остальных.

    Нужна для процессов с ``NSApplicationActivationPolicyAccessory`` (без иконки в Dock):
    иначе после потери фокуса окно CustomTkinter может остаться под стеком других приложений
    без способа вернуть его через Cmd+Tab.
    """
    if sys.platform != "darwin" or platform.system() != "Darwin":
        return
    try:
        from AppKit import NSApplication

        app = NSApplication.sharedApplication()
        try:
            app.unhide_(None)
        except Exception:
            LOGGER.debug("bring_app_to_front: unhide не применился", exc_info=True)
        app.activateIgnoringOtherApps_(True)
    except ImportError as err:
        LOGGER.debug("bring_app_to_front: нет AppKit (%s)", err)
    except Exception:
        LOGGER.debug("bring_app_to_front: сбой активации", exc_info=True)


def hide_dock_icon_for_ctk_root() -> None:
    """
    Переводит общий ``NSApplication`` в режим accessory: без отдельной иконки в Dock.

    CustomTkinter при ``CTk()`` поднимает свой инстанс приложения, который по умолчанию
    ведёт себя как обычное GUI-приложение. Для дочернего процесса дашборда это даёт
    вторую иконку в Dock рядом с треем основного процесса.

    Вызывать **после** ``ctk.CTk()`` (Tk уже создал ``NSApplication``), **до** ``mainloop``.

    На не-macOS или без PyObjC — безопасный no-op.
    """
    if sys.platform != "darwin" or platform.system() != "Darwin":
        return
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

        ns_app = NSApplication.sharedApplication()
        ns_app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        ns_app.activateIgnoringOtherApps_(True)
    except ImportError as err:
        LOGGER.warning("Не удалось скрыть иконку Dock в дашборде (нет AppKit): %s", err)
    except Exception:
        LOGGER.exception("Сбой при установке NSApplicationActivationPolicyAccessory для дашборда")
